from __future__ import annotations

import importlib
import json
import math
import pickle
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, OUTER_DOUBLE, board_point
from .heldout import file_sha256
from .homography import fit, project
from .images import open_srgb
from .labelme import ENTRY, Label, Shape
from .overlay import render
from .paths import DataDir

SOURCE = "deepdarts"
PROJECTED = "deepdarts-projected"
LABELS = Path("labels_pkl") / "labels.pkl"
IMAGES = Path("cropped_images") / "800"
RECORDS = "records.jsonl"
COLUMNS = ("img_folder", "img_name", "bbox", "xy")
ORDER = ("do-5-20", "do-17-3", "do-8-11", "do-13-6")
RADIUS_MM = OUTER_DOUBLE.outer_mm
MAX_DARTS = 3

VAL_FOLDERS = frozenset({"d1_02_06_2020", "d1_02_16_2020", "d1_02_22_2020", "d2_02_03_2021", "d2_02_05_2021"})
TEST_FOLDERS = frozenset({
    "d1_03_03_2020", "d1_03_19_2020", "d1_03_23_2020", "d1_03_27_2020", "d1_03_28_2020", "d1_03_30_2020",
    "d1_03_31_2020", "d2_03_03_2020", "d2_02_10_2021", "d2_02_03_2021_2",
})

_DATAPORT_2021 = {
    ("builtins", "slice"),
    ("numpy", "dtype"),
    ("numpy", "ndarray"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "scalar"),
    ("pandas.core.frame", "DataFrame"),
    ("pandas.core.indexes.base", "Index"),
    ("pandas.core.indexes.base", "_new_Index"),
    ("pandas.core.indexes.range", "RangeIndex"),
    ("pandas.core.internals.managers", "BlockManager"),
}
_CURRENT_PATHS = {
    ("numpy._core.multiarray", "_reconstruct"),
    ("numpy._core.multiarray", "scalar"),
    ("pandas", "DataFrame"),
    ("pandas", "Index"),
    ("pandas", "RangeIndex"),
    ("pandas._libs.internals", "_unpickle_block"),
}
ALLOWED = frozenset(_DATAPORT_2021 | _CURRENT_PATHS)
_PLAIN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


class RefusedClass(DartsMlError):
    pass


class _Restricted(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if (module, name) not in ALLOWED:
            raise RefusedClass(
                f"the pickle asks for {module}.{name}, which is not one of the {len(ALLOWED)} pandas and NumPy "
                "classes a DataFrame of DeepDarts' labels needs. Look at the file; don't widen the list "
                "(phase-M1.md §4)."
            )
        if module.startswith("numpy.core."):
            module = "numpy._core." + module.removeprefix("numpy.core.")
        return getattr(importlib.import_module(module), name)


def load_labels(path: Path):
    with path.open("rb") as file:
        frame = _Restricted(file).load()
    missing = [c for c in COLUMNS if c not in getattr(frame, "columns", ())]
    if missing:
        raise DartsMlError(f"{path} is not DeepDarts' label table: no column {', '.join(missing)}")
    return frame


def deepdarts_mm() -> list[tuple[float, float]]:
    return [board_point(RADIUS_MM, CALIBRATION_BY_NAME[n].degrees) for n in ORDER]


def split_of(folder: str) -> str:
    if folder in TEST_FOLDERS:
        return "test"
    return "val" if folder in VAL_FOLDERS else "train"


@dataclass
class Converted:
    records: int = 0
    splits: dict[str, int] = field(default_factory=dict)
    capture_sessions: set[str] = field(default_factory=set)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    rows: int = 0


def convert(data: DataDir) -> Converted:
    root = data.deepdarts()
    frame = load_labels(root / LABELS)
    converted = Converted(rows=len(frame))
    lines = []
    for folder, name, bbox, xy in zip(*(frame[c] for c in COLUMNS), strict=True):
        where = f"{folder}/{name}"
        try:
            record = _record(root, data.root, str(folder), str(name), bbox, xy)
        except DartsMlError as error:
            converted.skipped.append((where, str(error)))
            continue
        lines.append(json.dumps(record, sort_keys=True))
        converted.splits[record["split"]] = converted.splits.get(record["split"], 0) + 1
        converted.capture_sessions.add(record["capture_session"])
    target = root / RECORDS
    temporary = target.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    temporary.replace(target)
    converted.records = len(lines)
    return converted


def _record(root: Path, data_root: Path, folder: str, name: str, bbox, xy) -> dict:
    if not (_PLAIN_NAME.fullmatch(folder) and _PLAIN_NAME.fullmatch(name)):
        raise DartsMlError("the folder or file name is not a plain name")
    points = _points(xy)
    crop = _crop(bbox)
    photo = root / IMAGES / folder / name
    if not photo.is_file():
        raise DartsMlError("no Photo")
    try:
        with Image.open(photo) as image:
            width, height = image.size
    except OSError as error:
        raise DartsMlError(f"the Photo cannot be read: {error}") from None
    pixels = [(x * width, y * height) for x, y in points]
    clicked = dict(zip(ORDER, pixels[:len(ORDER)], strict=True))
    to_image = fit(deepdarts_mm(), list(clicked.values()))
    calibration = []
    for point in CALIBRATION_POINTS:
        if point.name in clicked:
            (x, y), source = clicked[point.name], SOURCE
        else:
            (x, y), source = project(to_image, [point.mm])[0], PROJECTED
        calibration.append({"name": point.name, "x": float(x), "y": float(y), "source": source})
    return {
        "source": SOURCE,
        "capture_session": folder,
        "split": split_of(folder),
        "photo": photo.relative_to(data_root).as_posix(),
        "width": width,
        "height": height,
        "crop": crop,
        "calibration": calibration,
        "photo_sha256": file_sha256(photo),
        "entries": [{"x": x, "y": y, "inferred": False} for x, y in pixels[len(ORDER):]],
    }


def _crop(bbox) -> list[int]:
    try:
        crop = [float(v) for v in bbox]
    except (TypeError, ValueError):
        crop = []
    if len(crop) != 4 or not all(math.isfinite(v) and v == int(v) for v in crop):
        raise DartsMlError("bbox is not four whole numbers")
    return [int(v) for v in crop]


def _points(xy) -> list[tuple[float, float]]:
    try:
        points = [(float(x), float(y)) for x, y in xy]
    except (TypeError, ValueError) as error:
        raise DartsMlError(f"xy is not a list of points: {error}") from None
    if not len(ORDER) <= len(points) <= len(ORDER) + MAX_DARTS:
        raise DartsMlError(f"{len(points)} points; a row holds the four Calibration points and up to {MAX_DARTS} Darts")
    if not all(math.isfinite(v) for point in points for v in point):
        raise DartsMlError("a point is not a finite number")
    return points


def read_records(data: DataDir) -> list[dict]:
    path = data.deepdarts() / RECORDS
    if not path.exists():
        raise DartsMlError(f"no {path}; run `darts-ml deepdarts convert` first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def overlay_sample(data: DataDir, count: int, seed: int = 0) -> list[str]:
    records = read_records(data)
    chosen = random.Random(seed).sample(records, min(count, len(records)))
    target = data.deepdarts_overlays()
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for record in chosen:
        shapes = [Shape(c["name"], c["x"], c["y"]) for c in record["calibration"] if c["source"] == SOURCE]
        shapes += [Shape(ENTRY, e["x"], e["y"]) for e in record["entries"]]
        label = Label(Path(), record["photo"], record["width"], record["height"], False, tuple(shapes))
        clicked = label.calibration
        to_board = fit([clicked[n] for n in ORDER], deepdarts_mm())
        rendered = render(open_srgb(data.root / record["photo"]), label, to_board)
        name = f"{record['capture_session']}-{Path(record['photo']).stem}.jpg"
        rendered.save(target / name, quality=85)
        written.append(name)
    return written
