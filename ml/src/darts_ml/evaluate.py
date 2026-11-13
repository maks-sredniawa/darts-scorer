from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, DOUBLE_WIRES, TREBLE_WIRES, WIRE_MARGIN_MM, score, wire_distance_mm
from .capture_sessions import ANGLES, PhotoName, Sheet, Visit, load_sheet
from .heldout import MANIFEST, verified
from .homography import crossing_errors_mm, fit, project
from .labelme import Label, label_path, read_label
from .paths import DataDir
from .prefill import SAME_DART_MM, image_to_board
from .repeatability import Spread

LABELS = "labels"


@dataclass(frozen=True)
class Bar:
    board_found: Fraction
    wire_median_mm: float
    wire_p95_mm: float
    visits_exact: Fraction
    visits_counted: int


# The bar for opening phase 1: docs/phase-M1.md §7, decided 2026-11-13 (D1).
BAR = Bar(
    board_found=Fraction(98, 100),
    wire_median_mm=0.5,
    wire_p95_mm=1.0,
    visits_exact=Fraction(80, 100),
    visits_counted=60,
)


class PredictionsError(DartsMlError):
    pass


@dataclass(frozen=True)
class Share:
    hits: int
    total: int

    @property
    def fraction(self) -> Fraction | None:
        return Fraction(self.hits, self.total) if self.total else None

    def __str__(self) -> str:
        if not self.total:
            return "0/0"
        return f"{self.hits}/{self.total} ({100 * self.hits / self.total:.1f}%)"


def board_met(found: Share, treble: Spread | None, double: Spread | None, bar: Bar = BAR) -> bool:
    if found.fraction is None or found.fraction < bar.board_found:
        return False
    return all(
        spread is not None and spread.median_mm <= bar.wire_median_mm and spread.p95_mm <= bar.wire_p95_mm
        for spread in (treble, double)
    )


def visits_met(exact: Share, bar: Bar = BAR) -> bool:
    return exact.total >= bar.visits_counted and exact.fraction is not None and exact.fraction >= bar.visits_exact


@dataclass(frozen=True)
class PredictedEntry:
    x: float
    y: float
    low_confidence: bool = False


@dataclass(frozen=True)
class Prediction:
    calibration: dict[str, tuple[float, float]]
    entries: tuple[PredictedEntry, ...]


def load_predictions(path: Path) -> dict[str, Prediction]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        predictions = {}
        for name, photo in raw["photos"].items():
            PhotoName.parse(name)
            calibration = {point: (float(xy[0]), float(xy[1])) for point, xy in photo.get("calibration", {}).items()}
            unknown = sorted(set(calibration) - set(CALIBRATION_BY_NAME))
            if unknown:
                raise PredictionsError(f"{path}: {name} names no Calibration point: {', '.join(unknown)}")
            entries = tuple(
                PredictedEntry(float(e["x"]), float(e["y"]), bool(e.get("low_confidence", False)))
                for e in photo.get("entries", [])
            )
            predictions[name] = Prediction(calibration, entries)
        return predictions
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise PredictionsError(f"{path}: not a predictions file this code can read ({error})") from None


def labels_as_predictions(labels: dict[str, Label]) -> dict[str, Prediction]:
    return {
        name: Prediction(dict(label.calibration), tuple(PredictedEntry(s.x, s.y) for s in label.entries))
        for name, label in labels.items()
    }


def hidden_in_p1(visit: Visit, p1: Label) -> bool:
    return len(p1.entries) < len(visit.scores_in_board)


@dataclass(frozen=True)
class Predicted:
    to_board: np.ndarray | None
    entries_mm: np.ndarray
    low_confidence: tuple[bool, ...]

    @property
    def found(self) -> bool:
        return self.to_board is not None

    def scores(self) -> Counter:
        return Counter(score(*mm) for mm in self.entries_mm)


def predicted(prediction: Prediction | None) -> Predicted:
    nothing = Predicted(None, np.empty((0, 2)), ())
    if prediction is None:
        return nothing
    names = list(prediction.calibration)
    try:
        to_board = fit([prediction.calibration[n] for n in names], [CALIBRATION_BY_NAME[n].mm for n in names])
    except DartsMlError:
        return nothing
    entries = [(e.x, e.y) for e in prediction.entries]
    entries_mm = project(to_board, entries) if entries else np.empty((0, 2))
    return Predicted(to_board, entries_mm, tuple(e.low_confidence for e in prediction.entries))


def merged_scores(photos: list[Predicted]) -> Counter:
    darts: list[list[np.ndarray]] = []
    for photo in (p for p in photos if p.found):
        pairs = sorted(
            (float(np.linalg.norm(mm - np.mean(dart, axis=0))), i, j)
            for i, mm in enumerate(photo.entries_mm)
            for j, dart in enumerate(darts)
        )
        taken_entries, taken_darts = set(), set()
        for distance, i, j in pairs:
            if distance <= SAME_DART_MM and i not in taken_entries and j not in taken_darts:
                darts[j].append(photo.entries_mm[i])
                taken_entries.add(i)
                taken_darts.add(j)
        darts += [[mm] for i, mm in enumerate(photo.entries_mm) if i not in taken_entries]
    return Counter(score(*np.mean(dart, axis=0)) for dart in darts)


def triggers(visit: Visit, p1: Predicted) -> list[str]:
    if not p1.found:
        return ["Board not found"]
    raised = []
    if len(p1.entries_mm) < len(visit.darts):
        raised.append("fewer Darts found than thrown")
    if any(p1.low_confidence):
        raised.append("a Dart's confidence is low")
    if any(wire_distance_mm(*mm) <= WIRE_MARGIN_MM for mm in p1.entries_mm):
        raised.append(f"an Entry point within {WIRE_MARGIN_MM:g} mm of a wire")
    return raised


@dataclass
class Evaluation:
    capture_sessions: int
    found: Share
    treble: Spread | None
    double: Spread | None
    b2: Share
    b2_open_p1_mismatches: int
    b2_p2: Share
    b2_p3: Share
    b2_merged: Share
    hidden: int
    hidden_p1_short: Share
    hidden_merged: Share
    darts_right: Share
    wrong_flagged: Share
    flags: Counter = field(default_factory=Counter)
    ignored_predictions: int = 0

    @property
    def board_met(self) -> bool:
        return board_met(self.found, self.treble, self.double)

    @property
    def visits_met(self) -> bool:
        return visits_met(self.b2)

    @property
    def met(self) -> bool:
        return self.board_met and self.visits_met


def evaluate(data: DataDir, predictions: str | Path, manifest: Path = MANIFEST) -> Evaluation:
    held = verified(data, manifest)
    photos = held.photo_names()
    sheets: dict[str, Sheet] = {name: load_sheet(data.sheet(name)) for name in held.capture_sessions}
    labels = {str(p): read_label(label_path(data.labels(p.capture_session), str(p))) for p in photos}
    given = labels_as_predictions(labels) if predictions == LABELS else load_predictions(Path(predictions))
    truth = {name: image_to_board(label.calibration) for name, label in labels.items()}
    found = {str(p): predicted(given.get(str(p))) for p in photos}

    treble, double = [], []
    treble_rows = np.array([p.wire in TREBLE_WIRES for p in CALIBRATION_POINTS])
    double_rows = np.array([p.wire in DOUBLE_WIRES for p in CALIBRATION_POINTS])
    for name, guess in found.items():
        if guess.found:
            errors = crossing_errors_mm(truth[name], guess.to_board)
            treble += list(errors[treble_rows])
            double += list(errors[double_rows])

    tally = Counter()
    flags = Counter()
    for (session, number) in sorted({(p.capture_session, p.visit) for p in photos}):
        sheet = sheets[session]
        visit = sheet.visit(number)
        recorded = Counter(visit.scores_in_board)
        by_angle = {a: found[str(PhotoName(session, number, a))] for a in ANGLES}
        right = {a: by_angle[a].found and by_angle[a].scores() == recorded for a in ANGLES}
        merged_right = any(g.found for g in by_angle.values()) and merged_scores(list(by_angle.values())) == recorded
        p1 = by_angle[1]
        if hidden_in_p1(visit, labels[str(PhotoName(session, number, 1))]):
            tally["hidden"] += 1
            tally["hidden short"] += len(p1.entries_mm) < len(visit.scores_in_board)
            tally["hidden merged"] += merged_right
            continue
        tally["counted"] += 1
        tally["open p1"] += sheet.open_mismatch(PhotoName(session, number, 1)) is not None
        tally["p1"] += right[1]
        tally["p2"] += right[2]
        tally["p3"] += right[3]
        tally["merged"] += merged_right
        tally["darts"] += sum(recorded.values())
        tally["darts right"] += sum((p1.scores() & recorded).values())
        if not right[1]:
            tally["wrong"] += 1
            raised = triggers(visit, p1)
            tally["wrong flagged"] += bool(raised)
            flags.update(raised)

    counted = tally["counted"]
    return Evaluation(
        capture_sessions=len(held.capture_sessions),
        found=Share(sum(g.found for g in found.values()), len(photos)),
        treble=Spread.of(treble),
        double=Spread.of(double),
        b2=Share(tally["p1"], counted),
        b2_open_p1_mismatches=tally["open p1"],
        b2_p2=Share(tally["p2"], counted),
        b2_p3=Share(tally["p3"], counted),
        b2_merged=Share(tally["merged"], counted),
        hidden=tally["hidden"],
        hidden_p1_short=Share(tally["hidden short"], tally["hidden"]),
        hidden_merged=Share(tally["hidden merged"], tally["hidden"]),
        darts_right=Share(tally["darts right"], tally["darts"]),
        wrong_flagged=Share(tally["wrong flagged"], tally["wrong"]),
        flags=flags,
        ignored_predictions=len(set(given) - set(found)),
    )


def report(result: Evaluation, bar: Bar = BAR) -> list[str]:
    def verdict(met: bool) -> str:
        return "met" if met else "NOT met"

    def spread(name: str, value: Spread | None) -> str:
        if value is None:
            return f"  {name:24} no Board found"
        return f"  {name:24} median {value.median_mm:.3f} mm, 95th {value.p95_mm:.3f} mm over {value.count} crossings"

    lines = [
        f"Held-out set: {result.capture_sessions} Capture sessions, {result.found.total} Photos, "
        f"{result.b2.total + result.hidden} Visits, verified against the frozen manifest",
        "",
        f"B1, the Board: {verdict(result.board_met)}  "
        f"(found ≥ {float(bar.board_found):.0%}; each wire row median ≤ {bar.wire_median_mm} mm, 95th ≤ {bar.wire_p95_mm} mm)",
        f"  {'Board found':24} {result.found}",
        spread("treble wires (ti, to)", result.treble),
        spread("double wires (di, do)", result.double),
        "",
        f"B2, the Visits: {verdict(result.visits_met)}  "
        f"(≥ {float(bar.visits_exact):.0%} exactly right from p1, over ≥ {bar.visits_counted} Visits not hidden in p1)",
        f"  {'exactly right from p1':24} {result.b2}",
        f"  {'open mismatch on p1':24} {result.b2_open_p1_mismatches} of the counted Visits",
        "",
        "Reported beside the bar:",
        f"  hidden in p1: {result.hidden} Visits; p1 finds fewer Darts than were in the Board in "
        f"{result.hidden_p1_short}; exactly right from all three merged in {result.hidden_merged}",
        f"  B2 from p2 {result.b2_p2}; from p3 {result.b2_p3}; from all three merged {result.b2_merged}",
        f"  Darts scored right from p1, counted Visits: {result.darts_right}",
        f"  wrong Visits from p1 that a trigger would ask another Angle for: {result.wrong_flagged}",
        *(f"    {name}: {count}" for name, count in sorted(result.flags.items())),
        "  DeepDarts' D2 test set: not read here (checkpoint C)",
    ]
    if result.ignored_predictions:
        lines.append(f"  {result.ignored_predictions} predicted Photos are not in the Held-out set and were ignored")
    lines += ["", f"The bar for opening phase 1: {verdict(result.met)}"]
    return lines
