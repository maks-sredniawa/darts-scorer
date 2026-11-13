from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .board import CALIBRATION_POINTS
from .capture_sessions import load_sheet
from .homography import crossing_errors_mm, invert, project
from .labelme import Label, label_path, read_label
from .manifest import ReviewManifest
from .paths import DataDir, Round
from .prefill import image_to_board
from .review import is_reviewed

UNDRAGGED_PX = 1.0
VERDICT_1 = (0.25, 0.5)
VERDICT_2_MEDIAN = 0.5


@dataclass(frozen=True)
class Spread:
    count: int
    median_mm: float
    p95_mm: float

    @classmethod
    def of(cls, distances) -> Spread | None:
        if not distances:
            return None
        values = np.asarray(distances)
        return cls(len(values), float(np.median(values)), float(np.percentile(values, 95)))


@dataclass(frozen=True)
class Minutes:
    photos: int
    pass_1: float
    pass_3: float


@dataclass
class Reading:
    spreads: dict[str, Spread | None] = field(default_factory=dict)
    minutes: dict[Round, Minutes] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> int | None:
        both = [self.spreads.get("a–b, all crossings"), self.spreads.get("a–c, all crossings")]
        if any(spread is None for spread in both):
            return None
        median = max(s.median_mm for s in both)
        p95 = max(s.p95_mm for s in both)
        if median <= VERDICT_1[0] and p95 <= VERDICT_1[1]:
            return 1
        return 2 if median <= VERDICT_2_MEDIAN else 3


@dataclass(frozen=True)
class RoundLabels:
    round_: Round
    labels: dict[str, Label]
    manifest: ReviewManifest

    def undragged(self, photo: str) -> set[str]:
        hand = self.manifest.get(photo).hand_points
        if len(hand) < 4:
            return set()
        to_image = invert(image_to_board(hand))
        clicked = self.labels[photo].calibration
        undragged = set()
        for point in CALIBRATION_POINTS:
            if point.name in hand or point.name not in clicked:
                continue
            projected = project(to_image, [point.mm])[0]
            if np.linalg.norm(projected - np.asarray(clicked[point.name])) <= UNDRAGGED_PX:
                undragged.add(point.name)
        return undragged


def repeatability(data: DataDir, name: str) -> Reading:
    sheet = load_sheet(data.sheet(name))
    reading = Reading()
    rounds = {r: _load(data, name, r, sheet.held_out, reading) for r in Round}
    a, b, c = rounds[Round.A], rounds[Round.B], rounds[Round.C]
    all_ab, dragged, undragged = [], [], []
    for photo in sorted(a.labels.keys() & b.labels.keys()):
        errors = dict(zip((p.name for p in CALIBRATION_POINTS), _errors(a.labels[photo], b.labels[photo]), strict=True))
        all_ab += errors.values()
        both = a.labels[photo].calibration.keys() & b.labels[photo].calibration.keys()
        loose = a.undragged(photo) | b.undragged(photo)
        dragged += [errors[n] for n in both if n not in loose]
        undragged += [errors[n] for n in both if n in loose]
    all_ac = []
    for photo in sorted(a.labels.keys() & c.labels.keys()):
        all_ac += list(_errors(a.labels[photo], c.labels[photo]))
    reading.spreads = {
        "a–b, all crossings": Spread.of(all_ab),
        "a–b, dragged in both": Spread.of(dragged),
        "a–b, undragged in either": Spread.of(undragged),
        "a–c, all crossings": Spread.of(all_ac),
    }
    for round_, labels in rounds.items():
        timed = [labels.manifest.get(p) for p in labels.labels if labels.manifest.get(p).label_seconds > 0]
        if timed:
            reading.minutes[round_] = Minutes(
                len(timed),
                float(np.mean([r.label_seconds for r in timed])) / 60,
                float(np.mean([r.review_seconds for r in timed])) / 60,
            )
    return reading


def _errors(first: Label, second: Label) -> np.ndarray:
    return crossing_errors_mm(image_to_board(first.calibration), image_to_board(second.calibration))


def _load(data: DataDir, name: str, round_: Round, held_out: bool, reading: Reading) -> RoundLabels:
    directory = data.labels(name, round_)
    manifest = ReviewManifest.load(directory)
    labels = {}
    for photo in sorted(p.stem for p in directory.glob("*.json")) if directory.exists() else []:
        path = label_path(directory, photo)
        if is_reviewed(manifest.get(photo), path, held_out):
            labels[photo] = read_label(path)
        else:
            reading.skipped.append(f"{photo} (round {round_.value}, not reviewed)")
    return RoundLabels(round_, labels, manifest)
