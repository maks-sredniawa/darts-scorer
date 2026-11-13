from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, Score, score
from .capture_sessions import ANGLES, Mark, PhotoName, Sheet, Visit, load_sheet
from .homography import MIN_POINTS, fit, project, residuals_mm
from .labelme import ENTRY, INFERRED, LABELS, Label, LabelError, label_path, read_label
from .manifest import ReviewManifest
from .paths import DataDir, Round
from .review import review_problem

RESIDUAL_LIMIT_MM = 1.0
ACROSS_ANGLES_MM = 2.0


@dataclass(frozen=True)
class Finding:
    where: str
    step: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}  [{self.step}]  {self.message}"


@dataclass
class Report:
    capture_session: str
    findings: list[Finding] = field(default_factory=list)
    open_mismatches: list[str] = field(default_factory=list)
    across_angles_mm: list[float] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    def add(self, where, step: str, message: str) -> None:
        self.findings.append(Finding(str(where), step, message))


@dataclass(frozen=True)
class Fitted:
    label: Label
    to_board: np.ndarray

    def entry_mm(self) -> np.ndarray:
        entries = [s.xy for s in self.label.entries]
        return project(self.to_board, entries) if entries else np.empty((0, 2))

    def scores(self) -> list[Score]:
        return [score(*mm) for mm in self.entry_mm()]


def check(data: DataDir, name: str, round_: Round = Round.A) -> Report:
    sheet = load_sheet(data.sheet(name))
    labels_dir = data.labels(name, round_)
    manifest = ReviewManifest.load(labels_dir)
    report = Report(name)
    _lint_sheet(sheet, report)
    fitted: dict[PhotoName, Fitted] = {}
    for photo in sheet.photo_names():
        path = label_path(labels_dir, str(photo))
        if not path.exists():
            report.add(photo, "lint", "no label")
            continue
        try:
            label = read_label(path)
        except LabelError as error:
            report.add(photo, "lint", str(error))
            continue
        _lint(photo, label, sheet, data, report)
        problem = review_problem(manifest.get(str(photo)), path, sheet.held_out)
        if problem:
            report.add(photo, "lint", problem)
        to_board = _fit(photo, label, report) if len(label.calibration) >= MIN_POINTS else None
        if to_board is not None:
            fitted[photo] = Fitted(label, to_board)
    for mismatch in sheet.mismatches:
        report.open_mismatches.append(f"{mismatch.photo}  {mismatch.reason}")
    for photo, fit_ in fitted.items():
        _score(photo, fit_, sheet, report)
    for visit in sheet.visits:
        _hidden_in_p1(sheet, visit.number, fitted, report)
        _across_angles(sheet, visit.number, fitted, report)
    return report


def _lint_sheet(sheet: Sheet, report: Report) -> None:
    if not sheet.held_out:
        return
    for visit in sheet.visits:
        if any(Mark.PLACED in dart.marks for dart in visit.darts):
            report.add(f"{sheet.capture_session} Visit {visit.number}", "lint", "a held-out Visit has a placed Dart")


def _lint(photo: PhotoName, label: Label, sheet: Sheet, data: DataDir, report: Report) -> None:
    names = Counter(s.label for s in label.shapes)
    unknown = sorted(n for n in names if n not in LABELS)
    if unknown:
        report.add(photo, "lint", f"labels not in the list: {', '.join(unknown)}")
    doubled = sorted(n for n, k in names.items() if k > 1 and n != ENTRY)
    if doubled:
        report.add(photo, "lint", f"labelled twice: {', '.join(doubled)}")
    not_points = sorted({s.label for s in label.shapes if s.shape_type != "point"})
    if not_points:
        report.add(photo, "lint", f"not drawn as points: {', '.join(not_points)}")
    flagged = sorted({s.label for s in label.shapes if s.inferred and s.label != ENTRY})
    if flagged:
        report.add(photo, "lint", f"`{INFERRED}` belongs on Entry points only: {', '.join(flagged)}")
    if len(label.calibration) < MIN_POINTS:
        report.add(photo, "lint", f"{len(label.calibration)} Calibration points; at least {MIN_POINTS} are needed")
    if label.has_image_data:
        report.add(photo, "lint", "the label embeds the image; it must hold no image data")
    photo_file = data.photo(sheet.capture_session, str(photo))
    if not photo_file.exists():
        report.add(photo, "lint", f"no Photo at {photo_file}")
    else:
        with Image.open(photo_file) as image:
            if image.size != (label.width, label.height):
                report.add(photo, "lint", f"label is {label.width}×{label.height}, the Photo {image.size[0]}×{image.size[1]}")
    in_board = len(sheet.visit(photo.visit).scores_in_board)
    if len(label.entries) > in_board:
        report.add(photo, "lint", f"{len(label.entries)} Entry points, but {in_board} Darts were in the Board")


def _fit(photo: PhotoName, label: Label, report: Report) -> np.ndarray | None:
    names = list(label.calibration)
    pixels = [label.calibration[n] for n in names]
    board = [CALIBRATION_BY_NAME[n].mm for n in names]
    try:
        to_board = fit(pixels, board)
    except DartsMlError as error:
        report.add(photo, "fit", str(error))
        return None
    for name_, residual in zip(names, residuals_mm(to_board, pixels, board), strict=True):
        if residual > RESIDUAL_LIMIT_MM:
            report.add(photo, "fit", f"{name_} is {residual:.2f} mm off the label homography: a misclick, or lens distortion")
    return to_board


def _score(photo: PhotoName, fitted: Fitted, sheet: Sheet, report: Report) -> None:
    if sheet.open_mismatch(photo):
        return
    visit = sheet.visit(photo.visit)
    recorded = Counter(visit.scores_in_board)
    found = Counter(fitted.scores())
    extra = found - recorded
    if extra:
        report.add(
            photo,
            "score",
            f"labels score {_tokens(found)}, the sheet records {_tokens(recorded)}: {_tokens(extra)} not recorded",
        )
    if photo.angle != 1:
        _missing_beyond_hidden(photo, fitted, visit, report)


def _missing_beyond_hidden(photo: PhotoName, fitted: Fitted, visit: Visit, report: Report) -> None:
    in_board = len(visit.scores_in_board)
    labelled = len(fitted.label.entries)
    hidden = visit.hidden_in(photo.angle)
    if in_board - labelled > hidden:
        report.add(
            photo,
            "score",
            f"{labelled} Entry points for the {in_board} Darts in the Board, and the sheet marks {hidden} hidden in p{photo.angle}",
        )


def _hidden_in_p1(sheet: Sheet, visit_number: int, fitted, report: Report) -> None:
    p1 = PhotoName(sheet.capture_session, visit_number, 1)
    if p1 not in fitted:
        return
    visit = sheet.visit(visit_number)
    missing = len(visit.scores_in_board) - len(fitted[p1].label.entries)
    if missing != visit.hidden_in(1) and not sheet.open_mismatch(p1):
        report.add(
            p1,
            "hidden",
            f"p1's label is missing {missing} of the Darts in the Board, the sheet marks {visit.hidden_in(1)} hidden",
        )


def _across_angles(sheet: Sheet, visit_number: int, fitted, report: Report) -> None:
    photos = [PhotoName(sheet.capture_session, visit_number, a) for a in ANGLES]
    for first, second in itertools.combinations([p for p in photos if p in fitted], 2):
        for distance in _matched_distances(fitted[first].entry_mm(), fitted[second].entry_mm()):
            report.across_angles_mm.append(distance)
            excused = sheet.open_mismatch(first) or sheet.open_mismatch(second)
            if distance > ACROSS_ANGLES_MM and not excused:
                report.add(
                    f"{sheet.capture_session} Visit {visit_number}",
                    "angles",
                    f"a Dart's Entry points in p{first.angle} and p{second.angle} are {distance:.1f} mm apart",
                )


def _matched_distances(first: np.ndarray, second: np.ndarray) -> list[float]:
    if len(first) > len(second):
        first, second = second, first
    if len(first) == 0:
        return []
    best = min(
        (np.linalg.norm(first - second[list(chosen)], axis=1) for chosen in itertools.permutations(range(len(second)), len(first))),
        key=lambda distances: distances.sum(),
    )
    return [float(d) for d in best]


def _tokens(scores: Counter) -> str:
    return " ".join(sorted(s.token for s in scores.elements())) or "nothing"
