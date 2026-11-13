from __future__ import annotations

import numpy as np

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS
from .capture_sessions import PhotoName, load_sheet
from .homography import fit, invert, project
from .labelme import ENTRY, Label, Shape, label_path, read_label, write_label
from .manifest import ReviewManifest
from .paths import DataDir, Round

SUGGESTED = "suggested by prefill"
SAME_DART_MM = 2.0


class PrefillError(DartsMlError):
    pass


def image_to_board(points: dict[str, tuple[float, float]]) -> np.ndarray:
    names = list(points)
    return fit([points[n] for n in names], [CALIBRATION_BY_NAME[n].mm for n in names])


def inside(label: Label, xy) -> bool:
    return 0 <= xy[0] < label.width and 0 <= xy[1] < label.height


def prefill(data: DataDir, name: str, round_: Round = Round.A) -> list[str]:
    if round_ is Round.C:
        raise PrefillError("round c is labelled without pre-fill: every crossing is clicked by hand")
    sheet = load_sheet(data.sheet(name))
    labels_dir = data.labels(name, round_)
    photos = sheet.photo_names()
    missing = [str(p) for p in photos if not label_path(labels_dir, str(p)).exists()]
    if missing:
        raise PrefillError(f"pass 1 is not finished; no label for: {', '.join(missing)}")
    manifest = ReviewManifest.load(labels_dir)
    labels = {p: read_label(label_path(labels_dir, str(p))) for p in photos}
    hand = {p: manifest.get(str(p)).hand_points or labels[p].calibration for p in photos}
    short = [f"{p} ({len(hand[p])})" for p in photos if len(hand[p]) < 4]
    if short:
        raise PrefillError(f"these labels have fewer than four Hand points: {', '.join(short)}")
    to_board = {p: image_to_board(hand[p]) for p in photos}
    done = []
    for photo in photos:
        if manifest.get(str(photo)).hand_points:
            continue
        label = labels[photo]
        shapes = list(label.shapes)
        shapes += _crossings(label, to_board[photo])
        shapes += _suggestions(photo, photos, labels, to_board)
        write_label(label.path, label.photo_path(), label.width, label.height, shapes)
        manifest.record(str(photo)).hand_points = dict(hand[photo])
        manifest.save()
        done.append(str(photo))
    return done


def _crossings(label: Label, to_board: np.ndarray) -> list[Shape]:
    clicked = label.calibration
    to_image = invert(to_board)
    shapes = []
    for point in CALIBRATION_POINTS:
        if point.name in clicked:
            continue
        xy = project(to_image, [point.mm])[0]
        if inside(label, xy):
            shapes.append(Shape(point.name, float(xy[0]), float(xy[1])))
    return shapes


def _suggestions(photo: PhotoName, photos, labels, to_board) -> list[Shape]:
    label = labels[photo]
    clicked = [s.xy for s in label.entries if s.description != SUGGESTED]
    known = list(project(to_board[photo], clicked)) if clicked else []
    found: list[np.ndarray] = []
    for other in photos:
        if other.visit != photo.visit or other == photo:
            continue
        entries = [s.xy for s in labels[other].entries if s.description != SUGGESTED]
        for mm in project(to_board[other], entries) if entries else []:
            if all(np.linalg.norm(mm - seen) > SAME_DART_MM for seen in [*known, *found]):
                found.append(mm)
    to_image = invert(to_board[photo])
    shapes = []
    for mm in found:
        xy = project(to_image, [mm])[0]
        if inside(label, xy):
            shapes.append(Shape(ENTRY, float(xy[0]), float(xy[1]), description=SUGGESTED))
    return shapes
