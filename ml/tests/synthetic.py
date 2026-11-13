from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from darts_ml.board import CALIBRATION_POINTS, OUTER_DOUBLE, SEGMENTS, WIRES, board_point, boundary_degrees
from darts_ml.homography import project
from darts_ml.labelme import ENTRY, INFERRED, Shape, write_label
from darts_ml.manifest import Review, ReviewManifest
from darts_ml.paths import DataDir
from darts_ml.review import label_sha256

SIZE = (640, 480)
ANGLE_YAW = {1: 0.0, 2: -40.0, 3: 40.0}


def camera(yaw_deg: float = 0.0, pitch_deg: float = 8.0, distance_mm: float = 1500.0,
           focal_px: float = 1500.0, size=SIZE, shift=(0.0, 0.0)) -> np.ndarray:
    yaw, pitch = np.radians(yaw_deg), np.radians(pitch_deg)
    centre = distance_mm * np.array([np.sin(yaw) * np.cos(pitch), -np.sin(pitch), np.cos(yaw) * np.cos(pitch)])
    forward = -centre / np.linalg.norm(centre)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rotation = np.vstack([right, down, forward])
    translation = -rotation @ centre
    k = np.array([[focal_px, 0, size[0] / 2 + shift[0]], [0, focal_px, size[1] / 2 + shift[1]], [0, 0, 1]])
    h = k @ np.column_stack([rotation[:, 0], rotation[:, 1], translation])
    return h / h[2, 2]


def board_image(to_image: np.ndarray, entries_mm=(), size=SIZE) -> Image.Image:
    image = Image.new("RGB", size, (70, 70, 70))
    draw = ImageDraw.Draw(image)
    disc = [tuple(p) for p in project(to_image, [board_point(225, d) for d in range(0, 360, 2)])]
    draw.polygon(disc, fill=(25, 25, 25))
    for wire in WIRES:
        ring = [tuple(p) for p in project(to_image, [board_point(wire.centre_mm, d) for d in range(0, 361, 2)])]
        draw.line(ring, fill=(200, 200, 200), width=1)
    for index in range(len(SEGMENTS)):
        ends = project(to_image, [board_point(16.65, boundary_degrees(index)), board_point(OUTER_DOUBLE.centre_mm, boundary_degrees(index))])
        draw.line([tuple(p) for p in ends], fill=(200, 200, 200), width=1)
    for x, y in project(to_image, list(entries_mm)) if len(entries_mm) else []:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 0))
    draw.rectangle((0, 0, 20, 10), fill=(255, 255, 0))
    return image


def crossings(to_image: np.ndarray, names=None, noise_px: float = 0.0, seed: int = 0, size=SIZE) -> list[Shape]:
    rng = np.random.default_rng(seed)
    shapes = []
    for point in CALIBRATION_POINTS:
        if names is not None and point.name not in names:
            continue
        x, y = project(to_image, [point.mm])[0] + rng.normal(0, noise_px, 2)
        if 0 <= x < size[0] and 0 <= y < size[1]:
            shapes.append(Shape(point.name, float(x), float(y)))
    return shapes


def entries(to_image: np.ndarray, entries_mm, inferred=()) -> list[Shape]:
    shapes = []
    for index, (x, y) in enumerate(project(to_image, list(entries_mm)) if len(entries_mm) else []):
        flags = {INFERRED: index in inferred}
        shapes.append(Shape(ENTRY, float(x), float(y), flags=flags))
    return shapes


def sheet_text(visits, held_out: bool = False, mismatches=()) -> str:
    lines = [
        'phone = "phone 1"',
        'light = "day"',
        f'set = "{"held-out" if held_out else "training"}"',
        "date = 2026-11-14",
        "",
    ]
    for darts in visits:
        quoted = ", ".join(f'"{d}"' for d in darts)
        lines += ["[[visits]]", f"darts = [{quoted}]", ""]
    for photo, reason in mismatches:
        lines += ["[[mismatches]]", f'photo = "{photo}"', f'reason = "{reason}"', ""]
    return "\n".join(lines)


def jpeg_with_exif(image: Image.Image, path: Path, orientation: int = 1, taken: dt.datetime | None = None,
                   gps: bool = True, quality: int = 93) -> None:
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x010F] = "TestMake"
    exif[0x0110] = "TestPhone"
    if taken is not None:
        exif.get_ifd(0x8769)[0x9003] = taken.strftime("%Y:%m:%d %H:%M:%S")
    if gps:
        location = exif.get_ifd(0x8825)
        location[1] = "N"
        location[2] = (52.0, 13.0, 37.0)
        location[3] = "E"
        location[4] = (21.0, 0.0, 42.0)
    image.save(path, "JPEG", quality=quality, exif=exif.tobytes())


STORED_FOR_ORIENTATION = {
    1: None,
    3: Image.Transpose.ROTATE_180,
    6: Image.Transpose.ROTATE_90,
    8: Image.Transpose.ROTATE_270,
}


def as_stored(upright: Image.Image, orientation: int) -> Image.Image:
    transpose = STORED_FOR_ORIENTATION[orientation]
    return upright if transpose is None else upright.transpose(transpose)


class TemporaryData:
    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="darts-ml-test-")
        self.data = DataDir(Path(self._directory.name).resolve())

    def cleanup(self) -> None:
        self._directory.cleanup()

    def write_sheet(self, name: str, visits, **kwargs) -> Path:
        path = self.data.sheet(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sheet_text(visits, **kwargs), encoding="utf-8")
        return path

    def write_photo(self, name: str, photo: str, image: Image.Image) -> Path:
        path = self.data.photo(name, photo)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, "JPEG", quality=90)
        return path

    def write_label(self, name: str, photo: str, shapes, labels: Path | None = None) -> Path:
        directory = labels or self.data.labels(name)
        path = directory / f"{photo}.json"
        write_label(path, self.data.photo(name, photo), SIZE[0], SIZE[1], shapes)
        return path



_MID_RADIUS = {"S": 130.0, "T": 102.0, "D": 165.0}


def dart_mm(token: str, nudge_deg: float = 0.0) -> tuple[float, float]:
    if token == "50":
        return (0.0, 3.0)
    if token == "25":
        return (0.0, 12.0)
    if token == "miss":
        return board_point(200.0, 30.0 + nudge_deg)
    index = SEGMENTS.index(int(token[1:]))
    return board_point(_MID_RADIUS[token[0]], index * 360 / len(SEGMENTS) + nudge_deg)


def session(td: TemporaryData, name: str, visits, held_out: bool = False, mismatches=()) -> dict:
    td.write_sheet(name, [[d for d in visit] for visit in visits], held_out=held_out, mismatches=mismatches)
    truths = {}
    for number, darts in enumerate(visits, start=1):
        in_board = [dart_mm(d.split()[0], nudge_deg=2.0 * i) for i, d in enumerate(darts) if d.split()[0] != "out"]
        for angle in (1, 2, 3):
            photo = f"{name}-v{number:02d}-p{angle}"
            to_image = camera(yaw_deg=ANGLE_YAW[angle] + number, pitch_deg=6.0 + number % 3)
            td.write_photo(name, photo, board_image(to_image, in_board))
            truths[photo] = (to_image, in_board)
    return truths


def pass_one_window(truths: dict, every_crossing: bool = False, seconds: float = 60.0, skip_entries=()):
    from darts_ml.board import HAND_POINTS
    from darts_ml.labelme import write_label as write

    def window(photo_path: Path, labels: Path) -> float:
        to_image, in_board = truths[photo_path.stem]
        names = None if every_crossing else set(HAND_POINTS)
        kept = [mm for i, mm in enumerate(in_board) if (photo_path.stem, i) not in skip_entries]
        shapes = crossings(to_image, names) + entries(to_image, kept)
        write(labels / f"{photo_path.stem}.json", photo_path, SIZE[0], SIZE[1], shapes)
        return seconds

    return window


def idle_window(seconds: float = 30.0):
    return lambda photo_path, labels: seconds


def full_labels(td: TemporaryData, name: str, truths: dict, labels: Path | None = None) -> None:
    for photo, (to_image, in_board) in truths.items():
        td.write_label(name, photo, crossings(to_image) + entries(to_image, in_board), labels)


REVIEW_DAYS = (dt.date(2026, 11, 14), dt.date(2026, 11, 15))


def reviewed_session(td: TemporaryData, name: str, visits, held_out: bool = False, mismatches=(),
                     recorded=None, edit=None) -> dict:
    truths = session(td, name, visits, held_out=held_out, mismatches=mismatches)
    if recorded is not None:
        td.write_sheet(name, recorded, held_out=held_out, mismatches=mismatches)
    manifest = ReviewManifest.load(td.data.labels(name))
    for photo, (to_image, in_board) in truths.items():
        shapes = crossings(to_image) + entries(to_image, in_board)
        if edit:
            shapes = edit(photo, to_image, shapes)
        path = td.write_label(name, photo, shapes)
        manifest.record(photo).reviews = [Review(day, label_sha256(path)) for day in REVIEW_DAYS]
    manifest.save()
    return truths


def without_last_entry_in(target):
    def edit(photo, to_image, shapes):
        if photo != target:
            return shapes
        kept = [s for s in shapes if s.label == ENTRY][:-1]
        return [s for s in shapes if s.label != ENTRY] + kept

    return edit
