from __future__ import annotations

import contextlib
import dataclasses
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from . import DartsMlError
from .augment import framing, letterbox, warp
from .board import CALIBRATION_POINTS, DOUBLE_WIRES, TREBLE_WIRES, score
from .decode import EntryRule, decode, kept_entries, ransac
from .evaluate import PredictedEntry, Share
from .homography import crossing_errors_mm, invert, project
from .model import ENTRY_STRIDE, Heads
from .repeatability import Spread
from .training_data import Sample, framed_targets, normalise

GROUPED_MM = 10.0
MATCH_MM = 3.0
_TREBLE = np.array([p.wire in TREBLE_WIRES for p in CALIBRATION_POINTS])
_DOUBLE = np.array([p.wire in DOUBLE_WIRES for p in CALIBRATION_POINTS])


@dataclass(frozen=True)
class Located:
    to_board: np.ndarray | None
    calibration: dict[str, tuple[float, float]] = field(default_factory=dict)
    entries: tuple[PredictedEntry, ...] = ()

    @property
    def found(self) -> bool:
        return self.to_board is not None


@dataclass(frozen=True)
class Speed:
    bf16: bool = False
    channels_last: bool = False

    def check(self, device: str) -> None:
        if self.bf16 and device == "cpu":
            raise DartsMlError("--bf16 is for the GPU; the CPU runs it slower than float32")

    @property
    def memory(self):
        return torch.channels_last if self.channels_last else torch.contiguous_format

    def autocast(self, device: str):
        return torch.autocast("cuda", dtype=torch.bfloat16) if self.bf16 and device == "cuda" else contextlib.nullcontext()

    def suffix(self) -> str:
        return ("-bf16" if self.bf16 else "") + ("-cl" if self.channels_last else "")


@dataclass(frozen=True)
class Inference:
    model: torch.nn.Module
    device: str
    size: int
    batch: int = 16
    workers: int = 4
    speed: Speed = Speed()
    entries: EntryRule = EntryRule()


class _Framed(torch.utils.data.Dataset):
    def __init__(self, items: list[tuple[Path, np.ndarray]], size: int) -> None:
        self.items = items
        self.size = size

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> torch.Tensor:
        path, matrix = self.items[index]
        with Image.open(path) as photo:
            return normalise(warp(photo.convert("RGB"), matrix, self.size))


def _logits(run: Inference, items: list[tuple[Path, np.ndarray]]):
    loader = torch.utils.data.DataLoader(_Framed(items, run.size), batch_size=run.batch, num_workers=run.workers)
    was_training = run.model.training
    run.model.eval()
    try:
        with torch.no_grad():
            for images in loader:
                count = len(images)
                # A short last batch is a new shape, and MIOpen's fresh kernel search for one can fail (ml/README.md).
                images = torch.cat([images, images[-1:].expand(run.batch - count, *images.shape[1:])])
                with run.speed.autocast(run.device):
                    heads = run.model(images.to(run.device).contiguous(memory_format=run.speed.memory))
                board, entry = (h[:count].float().cpu().numpy() for h in heads)
                yield from (Heads(b, e) for b, e in zip(board, entry, strict=True))
    finally:
        run.model.train(was_training)


def _to_photo(matrix: np.ndarray, peaks) -> np.ndarray:
    back = invert(matrix)
    return project(back, [(p.x, p.y) for p in peaks]) if peaks else np.empty((0, 2))


def _board(matrix: np.ndarray, heads: Heads, rule: EntryRule = EntryRule()) -> Located:
    decoded = decode(heads, entry_threshold=rule.threshold)
    channels = sorted(decoded.calibration)
    pixels = _to_photo(matrix, [decoded.calibration[c] for c in channels])
    calibration = {c: (float(x), float(y)) for c, (x, y) in zip(channels, pixels, strict=True)}
    found = ransac(calibration)
    if found is None:
        return Located(None)
    to_board, inliers = found
    entries = _to_photo(matrix, list(decoded.entries))
    located = Located(
        to_board,
        {CALIBRATION_POINTS[c].name: calibration[c] for c in inliers},
        tuple(PredictedEntry(float(x), float(y), p.low_confidence, p.confidence)
              for p, (x, y) in zip(decoded.entries, entries, strict=True)),
    )
    return refiltered(located, rule)


def refiltered(located: Located, rule: EntryRule) -> Located:
    if not located.found or not located.entries:
        return located
    board_mm = project(located.to_board, [(e.x, e.y) for e in located.entries])
    keep = kept_entries(board_mm, [e.confidence for e in located.entries], rule)
    return dataclasses.replace(located, entries=tuple(located.entries[i] for i in keep))


def locate(run: Inference, photos: list[Path]) -> list[Located]:
    sizes = []
    for path in photos:
        with Image.open(path) as photo:
            sizes.append(photo.size)
    first = [letterbox(size, run.size) for size in sizes]
    boards = [_board(m, logits).to_board for m, logits in zip(first, _logits(run, list(zip(photos, first))), strict=True)]
    second = {i: framing(invert(b), run.size) for i, b in enumerate(boards) if b is not None}
    located = [Located(None) for _ in photos]
    order = sorted(second)
    for i, logits in zip(order, _logits(run, [(photos[i], second[i]) for i in order]), strict=True):
        located[i] = _board(second[i], logits, run.entries)
    return located


@dataclass(frozen=True)
class Figures:
    found: Share
    treble: Spread | None
    double: Spread | None
    exact: Share
    darts_right: Share
    grouped: Share
    exact_by_folder: dict[str, Share]
    total_by_folder: dict[str, Share] = field(default_factory=dict)

    def key(self, board_only: bool) -> tuple[float, float]:
        found = float(self.found.fraction or 0)
        if board_only:
            worst = max((s.median_mm for s in (self.treble, self.double) if s), default=float("inf"))
            return found, -worst
        return float(self.exact.fraction or 0), found

    def as_dict(self) -> dict:
        def share(s: Share) -> list[int]:
            return [s.hits, s.total]

        def spread(s: Spread | None):
            return None if s is None else {"count": s.count, "median_mm": s.median_mm, "p95_mm": s.p95_mm}

        return {"found": share(self.found), "treble": spread(self.treble), "double": spread(self.double),
                "exact": share(self.exact), "darts_right": share(self.darts_right), "grouped": share(self.grouped),
                "exact_by_folder": {k: share(v) for k, v in sorted(self.exact_by_folder.items())},
                "total_by_folder": {k: share(v) for k, v in sorted(self.total_by_folder.items())}}

    def lines(self) -> list[str]:
        def spread(s: Spread | None) -> str:
            return "no Board found" if s is None else f"median {s.median_mm:.3f} mm, 95th {s.p95_mm:.3f} mm"

        lines = [f"Board found {self.found}; treble wires {spread(self.treble)}; double wires {spread(self.double)}",
                 f"Photos scored exactly right {self.exact}; Darts right {self.darts_right}; "
                 f"pairs under {GROUPED_MM:g} mm found as two {self.grouped}"]
        lines += [f"  {folder}: exactly right {share}; Visit total right, the DeepDarts paper's way, "
                  f"{self.total_by_folder.get(folder, Share(0, 0))}"
                  for folder, share in sorted(self.exact_by_folder.items())]
        return lines


def _points(scores: Counter) -> int:
    return sum(s.value * n for s, n in scores.items())


def figures(samples: list[Sample], located: list[Located]) -> Figures:
    tally = Counter()
    treble, double = [], []
    by_folder: dict[str, Counter] = {}
    for sample, guess in zip(samples, located, strict=True):
        truth = invert(sample.board_to_photo())
        truth_mm = project(truth, list(sample.entries)) if sample.entries else np.empty((0, 2))
        guess_mm = (project(guess.to_board, [(e.x, e.y) for e in guess.entries])
                    if guess.found and guess.entries else np.empty((0, 2)))
        recorded = Counter(score(*mm) for mm in truth_mm)
        folder = by_folder.setdefault(sample.capture_session.split("_")[0], Counter()) if sample.capture_session else Counter()
        tally["photos"] += 1
        folder["photos"] += 1
        tally["darts"] += sum(recorded.values())
        pairs = _close_pairs(truth_mm)
        tally["pairs"] += len(pairs)
        if not guess.found:
            continue
        tally["found"] += 1
        errors = crossing_errors_mm(truth, guess.to_board)
        treble += list(errors[_TREBLE])
        double += list(errors[_DOUBLE])
        given = Counter(score(*mm) for mm in guess_mm)
        tally["exact"] += given == recorded
        folder["exact"] += given == recorded
        folder["total"] += _points(given) == _points(recorded)
        tally["darts right"] += sum((given & recorded).values())
        matched = _matched(truth_mm, guess_mm)
        tally["pairs two"] += sum(a in matched and b in matched for a, b in pairs)
    return Figures(
        found=Share(tally["found"], tally["photos"]),
        treble=Spread.of(treble),
        double=Spread.of(double),
        exact=Share(tally["exact"], tally["photos"]),
        darts_right=Share(tally["darts right"], tally["darts"]),
        grouped=Share(tally["pairs two"], tally["pairs"]),
        exact_by_folder={k: Share(v["exact"], v["photos"]) for k, v in by_folder.items()},
        total_by_folder={k: Share(v["total"], v["photos"]) for k, v in by_folder.items()},
    )


def _close_pairs(mm: np.ndarray) -> list[tuple[int, int]]:
    return [(a, b) for a in range(len(mm)) for b in range(a + 1, len(mm))
            if np.linalg.norm(mm[a] - mm[b]) < GROUPED_MM]


def _matched(truth: np.ndarray, guess: np.ndarray) -> set[int]:
    return {i for i, _, _ in matched_pairs(truth, guess)}


def matched_pairs(first: np.ndarray, second: np.ndarray) -> list[tuple[int, int, float]]:
    """Each point of `first` paired with the nearest free one of `second` within MATCH_MM, closest pairs first."""
    pairs = sorted((float(np.linalg.norm(a - b)), i, j) for i, a in enumerate(first) for j, b in enumerate(second))
    taken_first, taken_second, kept = set(), set(), []
    for distance, i, j in pairs:
        if distance <= MATCH_MM and i not in taken_first and j not in taken_second:
            taken_first.add(i)
            taken_second.add(j)
            kept.append((i, j, distance))
    return kept


def located_from_targets(sample: Sample, size: int, entry_stride: int = ENTRY_STRIDE) -> Located:
    matrix = framing(sample.board_to_photo(), size)
    made = framed_targets(sample, matrix, size, entry_stride)
    board = np.concatenate([_logit(made.board_heat), made.board_offsets])
    entry = np.concatenate([_logit(made.entry_heat[None]), made.entry_offsets])
    return _board(matrix, Heads(board, entry))


def _logit(heat: np.ndarray) -> np.ndarray:
    clipped = np.clip(heat, 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))
