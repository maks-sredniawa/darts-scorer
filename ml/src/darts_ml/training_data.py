from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
import torch
from PIL import Image

from . import DartsMlError
from .augment import photometric, random_matrix, warp
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS
from .capture_sessions import PhotoName
from .deepdarts import ORDER, PROJECTED, RECORDS as DEEPDARTS_RECORDS, SOURCE as DEEPDARTS, deepdarts_mm
from .heldout import HeldOutSet, file_sha256
from .homography import MIN_POINTS, fit, invert, project
from .labelme import label_path
from .model import BOARD_STRIDE, CALIBRATION_CHANNELS, ENTRY_POINT, ENTRY_STRIDE
from .paths import DataDir
from .records import RECORDS as OWNER_RECORDS

PROJECTED_WEIGHT = 0.5
SIGMA_CELLS = 2.0
ENTRY_SIGMA_CELLS = 1.0
RING_INNER_MM = 4.0
RING_OUTER_MM = 20.0
RING_CLEAR_CELLS = 2.0
VALIDATION_SESSIONS = frozenset({"s09", "s14"})
TRAIN, VALIDATION = "train", "validation"
_INDEX = {point.name: i for i, point in enumerate(CALIBRATION_POINTS)}
_BOARD = np.array([p.mm for p in CALIBRATION_POINTS])
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class RefusedRecord(DartsMlError):
    pass


@dataclass(frozen=True)
class Sample:
    photo: Path
    calibration: tuple[tuple[int, float, float, float], ...]
    entries: tuple[tuple[float, float], ...]
    capture_session: str = ""

    def board_to_photo(self) -> np.ndarray:
        return fit(_BOARD[[c for c, *_ in self.calibration]], [(x, y) for _, x, y, _ in self.calibration])


def deepdarts_samples(data: DataDir, split: str) -> list[Sample]:
    if split == "test":
        raise RefusedRecord("DeepDarts' test split is read only for readings, never trained or chosen on (phase-M2.md §3)")
    return _deepdarts(data, split)


def deepdarts_reading_samples(data: DataDir, split: str) -> list[Sample]:
    return _deepdarts(data, split)


def _deepdarts(data: DataDir, split: str) -> list[Sample]:
    path = data.deepdarts() / DEEPDARTS_RECORDS
    if not path.exists():
        raise DartsMlError(f"no {path}; run `darts-ml deepdarts convert` first")
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["split"] == split:
            samples.append(_deepdarts_sample(data.root, record))
    return samples


def _deepdarts_sample(root: Path, record: dict) -> Sample:
    clicked = {c["name"]: (c["x"], c["y"]) for c in record["calibration"] if c["source"] == DEEPDARTS}
    to_image = fit(deepdarts_mm(), [clicked[n] for n in ORDER])
    centres = project(to_image, [CALIBRATION_BY_NAME[n].mm for n in ORDER])
    moved = dict(zip(ORDER, map(tuple, centres), strict=True))
    calibration = []
    for c in record["calibration"]:
        x, y = moved.get(c["name"], (c["x"], c["y"]))
        weight = PROJECTED_WEIGHT if c["source"] == PROJECTED else 1.0
        calibration.append((_INDEX[c["name"]], float(x), float(y), weight))
    entries = tuple((e["x"], e["y"]) for e in record["entries"])
    return Sample(root / record["photo"], tuple(calibration), entries, record.get("capture_session", ""))


def owner_samples(data: DataDir, held: HeldOutSet, split: str) -> list[Sample]:
    if split not in (TRAIN, VALIDATION):
        raise DartsMlError(f"the owner's Photos split into {TRAIN} and {VALIDATION}; the Held-out set is read only by "
                           "`darts-ml evaluate`")
    path = data.build() / OWNER_RECORDS
    if not path.exists():
        raise DartsMlError(f"no {path}; run `darts-ml build` first")
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        photo = PhotoName(record["capture_session"], record["visit"], record["angle"])
        _refuse_held_out(data, held, photo)
        if (photo.capture_session in VALIDATION_SESSIONS) == (split == VALIDATION):
            samples.append(_owner_sample(data.root, record))
    return samples


def _refuse_held_out(data: DataDir, held: HeldOutSet, photo: PhotoName) -> None:
    photo_file = data.photo(photo.capture_session, str(photo))
    label_file = label_path(data.labels(photo.capture_session), str(photo))
    reason = held.refusal(photo, False, file_sha256(photo_file) if photo_file.exists() else None,
                          file_sha256(label_file) if label_file.exists() else None)
    if reason:
        raise RefusedRecord(f"{photo} is in {OWNER_RECORDS} and {reason}; nothing trains or chooses on the "
                            "Held-out set (phase-M2.md §3). Rebuild the records with `darts-ml build`")


def _owner_sample(root: Path, record: dict) -> Sample:
    calibration = tuple((_INDEX[c["name"]], float(c["x"]), float(c["y"]), 1.0) for c in record["calibration"])
    entries = tuple((e["x"], e["y"]) for e in record["entries"] if not e["inferred"])
    return Sample(root / record["photo"], calibration, entries, record["capture_session"])


def normalise(image: Image.Image) -> torch.Tensor:
    pixels = (np.asarray(image, dtype=np.float32) / 255.0 - _MEAN) / _STD
    return torch.from_numpy(pixels.transpose(2, 0, 1).copy())


class Targets(NamedTuple):
    board_heat: np.ndarray
    board_weights: np.ndarray
    board_offsets: np.ndarray
    board_mask: np.ndarray
    entry_heat: np.ndarray
    entry_offsets: np.ndarray
    entry_mask: np.ndarray
    ring: np.ndarray


def targets(points_px, size: int, entry_stride: int = ENTRY_STRIDE, to_board: np.ndarray | None = None,
            ring_mm: tuple[float, float] = (RING_INNER_MM, RING_OUTER_MM)) -> Targets:
    """to_board maps input pixels to Board mm; without it the ring is empty."""
    cells, entry_cells = size // BOARD_STRIDE, size // entry_stride
    board_heat = np.zeros((CALIBRATION_CHANNELS, cells, cells), dtype=np.float32)
    board_weights = np.ones(CALIBRATION_CHANNELS, dtype=np.float32)
    board_offsets = np.zeros((2, cells, cells), dtype=np.float32)
    board_mask = np.zeros((cells, cells), dtype=np.float32)
    entry_heat = np.zeros((entry_cells, entry_cells), dtype=np.float32)
    entry_offsets = np.zeros((2, entry_cells, entry_cells), dtype=np.float32)
    entry_mask = np.zeros((entry_cells, entry_cells), dtype=np.float32)
    entries = []
    for channel, x, y, weight in points_px:
        entry = channel == ENTRY_POINT
        if entry:
            entries.append((x, y))
            stride, grid, heat, offsets, mask = entry_stride, entry_cells, entry_heat, entry_offsets, entry_mask
        else:
            board_weights[channel] = weight
            stride, grid, heat, offsets, mask = BOARD_STRIDE, cells, board_heat[channel], board_offsets, board_mask
        cx, cy = x / stride, y / stride
        if not (0 <= cx < grid and 0 <= cy < grid):
            continue
        _splat(heat, cx, cy, ENTRY_SIGMA_CELLS if entry else SIGMA_CELLS)
        ix, iy = int(cx), int(cy)
        offsets[:, iy, ix] = (cx - ix, cy - iy)
        mask[iy, ix] = 1.0
    ring = ring_mask(entries, entry_cells, entry_stride, to_board, ring_mm)
    return Targets(board_heat, board_weights, board_offsets, board_mask, entry_heat, entry_offsets, entry_mask, ring)


def ring_mask(entries_px, cells: int, stride: int, to_board: np.ndarray | None,
              ring_mm: tuple[float, float]) -> np.ndarray:
    """The Entry cells whose false peaks cost more: between ring_mm[0] and ring_mm[1] of Board from a labelled
    Entry point, where its own barrel and flight show, but never within ring_mm[0] or RING_CLEAR_CELLS of any."""
    ring = np.zeros((cells, cells), dtype=np.float32)
    if not entries_px or to_board is None:
        return ring
    inner, outer = ring_mm
    entries_px = np.asarray(entries_px, dtype=float)
    to_board = to_board * np.sign((np.column_stack([entries_px, np.ones(len(entries_px))]) @ to_board.T)[0, 2])
    ys, xs = np.mgrid[0:cells, 0:cells]
    pixels = np.column_stack([(xs.ravel() + 0.5) * stride, (ys.ravel() + 0.5) * stride, np.ones(cells * cells)])
    mapped = pixels @ to_board.T
    # Cells past the Board plane's horizon map to w <= 0, and their projection lands anywhere, near a Dart too.
    ahead = mapped[:, 2] > 0
    board = mapped[:, :2] / np.where(ahead, mapped[:, 2], 1.0)[:, None]
    entries_mm = project(to_board, entries_px)
    mm = np.linalg.norm(board[:, None, :] - entries_mm[None, :, :], axis=2)
    entry_cells = np.floor(entries_px / stride)
    apart = np.hypot(xs.ravel()[:, None] - entry_cells[None, :, 0], ys.ravel()[:, None] - entry_cells[None, :, 1])
    near = ((mm >= inner) & (mm <= outer)).any(axis=1)
    clear = (mm >= inner).all(axis=1) & (apart >= RING_CLEAR_CELLS).all(axis=1)
    ring.ravel()[:] = near & clear & ahead
    return ring


class KeypointDataset(torch.utils.data.Dataset):
    def __init__(self, samples: list[Sample], size: int, augment: bool = False, entry_stride: int = ENTRY_STRIDE,
                 ring_mm: tuple[float, float] = (RING_INNER_MM, RING_OUTER_MM)) -> None:
        self.samples = samples
        self.size = size
        self.augment = augment
        self.entry_stride = entry_stride
        self.ring_mm = ring_mm

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, Targets]:
        sample = self.samples[index]
        to_photo = sample.board_to_photo() if len(sample.calibration) >= MIN_POINTS else None
        with Image.open(sample.photo) as photo:
            photo = photo.convert("RGB")
            if self.augment:
                rng = np.random.default_rng(int(torch.randint(0, 2**62, ())))
                matrix = random_matrix(to_photo, self.size, rng)
                image = photometric(warp(photo, matrix, self.size), rng)
            else:
                matrix = np.diag([self.size / photo.width, self.size / photo.height, 1.0])
                image = photo.resize((self.size, self.size), Image.BILINEAR)
        made = framed_targets(sample, matrix, self.size, self.entry_stride, self.ring_mm, to_photo)
        return normalise(image), Targets(*map(torch.from_numpy, made))


def framed_targets(sample: Sample, matrix: np.ndarray, size: int, entry_stride: int = ENTRY_STRIDE,
                   ring_mm: tuple[float, float] = (RING_INNER_MM, RING_OUTER_MM),
                   to_photo: np.ndarray | None = None) -> Targets:
    """The targets of a sample whose Photo the matrix maps onto a size × size input; to_photo, the sample's
    Board-to-Photo homography, places the ring, and without it the ring is empty."""
    points = [(channel, x, y, w) for channel, x, y, w in sample.calibration]
    points += [(ENTRY_POINT, x, y, 1.0) for x, y in sample.entries]
    moved = project(matrix, [(x, y) for _, x, y, _ in points]) if points else []
    return targets([(c, x, y, w) for (c, _, _, w), (x, y) in zip(points, moved, strict=True)], size, entry_stride,
                   None if to_photo is None else invert(matrix @ to_photo), ring_mm)


def _splat(heatmap: np.ndarray, cx: float, cy: float, sigma: float) -> None:
    cells = heatmap.shape[0]
    radius = int(3 * sigma)
    ix, iy = int(cx), int(cy)
    x0, x1 = max(0, ix - radius), min(cells, ix + radius + 1)
    y0, y1 = max(0, iy - radius), min(cells, iy + radius + 1)
    xs = np.arange(x0, x1) - ix
    ys = np.arange(y0, y1) - iy
    patch = np.exp(-(xs[None, :] ** 2 + ys[:, None] ** 2) / (2 * sigma**2))
    np.maximum(heatmap[y0:y1, x0:x1], patch, out=heatmap[y0:y1, x0:x1])
