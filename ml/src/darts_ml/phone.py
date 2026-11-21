"""Phase 1's gate (phase-1.md §1): the files the Kotlin port is held to, and the run that holds it there."""

from __future__ import annotations

import json
import math
import shutil
import tomllib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image

from . import DartsMlError
from .augment import letterbox, warp
from .board import CALIBRATION_POINTS, SEGMENT_DEGREES, SEGMENTS, WIRES, board_point, boundary_degrees, score
from .decode import ENTRY_THRESHOLD, MIN_INLIERS, decode
from .homography import invert, project
from .images import as_srgb, open_srgb, to_display_p3
from .locate import Located, _board
from .model import BOARD_OFFSETS, CALIBRATION_CHANNELS, ENTRY_HEAT, ENTRY_OFFSETS, Heads
from .training_data import Sample

REPO = Path(__file__).resolve().parents[3]
SCORING_CASES = REPO / "ml" / "tests" / "scoring-cases.toml"
APP_MODEL = REPO / "app" / "src" / "main" / "assets" / "model" / "darts.tflite"
FIXTURES = REPO / "app" / "src" / "test" / "resources" / "scoring"
DISPLAY_P3_SOURCE = REPO / "app" / "src" / "androidTest" / "assets" / "display-p3-red.jpg"
APP_PACKAGE = "com.maksforge.dartsscorer.debug"
TEST_RUNNER = f"{APP_PACKAGE}.test/androidx.test.runner.AndroidJUnitRunner"
TEST_CLASS = "app.dartsscorer.scoring.PhoneParityTest"
DEVICE_DIR = f"/sdcard/Android/data/{APP_PACKAGE}/files/parity"
EXPECTED = "expected.json"
REPORT = "report.txt"
_SIDE_MM = 0.1
_RING_MIDDLES_MM = (58.0, 102.0, 133.0, 164.5, 175.0)
_RADIAL_RADII_MM = (30.0, 102.0, 133.0, 164.5)
_SPARSE_FLOOR = -3.0
_STRIP_PX = 150
_SPARSE_FILL = -30.0
_RNG_POPULATIONS = (8, 9, 12, 20, 33, 47, 61, 79, 80)
PHOTOS_LONG_EDGE = 2048
PHOTOS_QUALITY = 85
_EXIF_ORIENTATION = 0x0112
DISPLAY_P3_PREFIX = "p3__"


def scoring_table(cases_path: Path = SCORING_CASES) -> list[tuple[float, float, str]]:
    """Every segment in the middle of each of its rings and beyond the double, 0.1 mm either side of each ring
    wire and each radial wire, both bulls, then the shared hand-written cases; each with Python's Score."""
    points: list[tuple[float, float]] = [(0.0, 0.0), (0.0, 12.0), (0.0, 200.0)]
    for i in range(len(SEGMENTS)):
        middle = i * SEGMENT_DEGREES
        points += [board_point(r, middle) for r in _RING_MIDDLES_MM]
        points += [board_point(w.centre_mm + side, middle) for w in WIRES for side in (-_SIDE_MM, _SIDE_MM)]
        across = math.radians(boundary_degrees(i))
        for radius in _RADIAL_RADII_MM:
            x, y = board_point(radius, boundary_degrees(i))
            points += [(x + side * math.cos(across), y - side * math.sin(across)) for side in (-_SIDE_MM, _SIDE_MM)]
    cases = tomllib.loads(cases_path.read_text(encoding="utf-8"))["case"]
    points += [(float(c["x"]), float(c["y"])) for c in cases]
    return [(x, y, score(x, y).token) for x, y in points]


def rng_choices() -> list[tuple[int, list[int]]]:
    """One `default_rng(0)`'s `choice(n, 4, replace=False)` across populations, as `ransac` draws them."""
    rng = np.random.default_rng(0)
    return [(n, [int(i) for i in rng.choice(n, 4, replace=False)]) for _ in range(40) for n in _RNG_POPULATIONS]


def warp_cases() -> dict:
    """A small Photo through `warp` three ways: reduced then letterboxed, reduced under a tilt, enlarged."""
    rng = np.random.default_rng(7)
    width, height, size = 45, 31, 24
    pixels = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    photo = Image.fromarray(pixels)
    tilt = np.array([[0.42, 0.06, 2.5], [-0.03, 0.47, 1.0], [0.0011, -0.0007, 1.0]])
    enlarge = np.array([[1.7, 0.1, -20.0], [0.05, 1.6, -9.0], [0.002, 0.001, 1.0]])
    cases = []
    for matrix in (letterbox((width, height), size), tilt, enlarge):
        out = np.asarray(warp(photo, matrix, size))
        cases.append({"matrix": [float(v) for v in matrix.ravel()], "size": size, "expected": out.ravel().tolist()})
    packed = (pixels[..., 0].astype(np.int64) << 16) | (pixels[..., 1].astype(np.int64) << 8) | pixels[..., 2]
    return {"width": width, "height": height, "pixels": packed.ravel().tolist(), "cases": cases}


def sparse(head: np.ndarray, heat: slice, offsets: slice) -> tuple[np.ndarray, dict]:
    """The head with every heat logit at or below _SPARSE_FLOOR lowered to _SPARSE_FILL and every offset away from
    a kept heat cell zeroed: decoding reads the same peaks from it, and it is small enough to commit."""
    default = np.zeros_like(head)
    default[heat] = _SPARSE_FILL
    kept = default.copy()
    mask = head[heat] > _SPARSE_FLOOR
    kept[heat] = np.where(mask, head[heat], _SPARSE_FILL)
    near = mask.any(axis=0)
    kept[offsets] = np.where(near, head[offsets], 0.0)
    cells = np.flatnonzero(kept != default)
    return kept, {"shape": list(head.shape), "heat": [heat.start, heat.stop], "fill": _SPARSE_FILL,
                  "cells": [[int(i), float(kept.flat[i])] for i in cells]}


def located_record(located: Located) -> dict:
    if not located.found:
        return {"found": False, "to_board": None, "calibration": {}, "darts": []}
    mm = project(located.to_board, [(e.x, e.y) for e in located.entries]) if located.entries else []
    return {"found": True, "to_board": [float(v) for v in located.to_board.ravel()],
            "calibration": {name: [float(x), float(y)] for name, (x, y) in located.calibration.items()},
            "darts": [[e.x, e.y, e.confidence, score(*at).token] for e, at in zip(located.entries, mm, strict=True)]}


def heads_case(name: str, matrix: np.ndarray, heads: Heads) -> dict:
    """One Photo's heads, made sparse, with what Python decodes and locates from them."""
    board, board_record = sparse(heads.board, slice(0, CALIBRATION_CHANNELS), BOARD_OFFSETS)
    entry, entry_record = sparse(heads.entry, slice(ENTRY_HEAT, ENTRY_HEAT + 1), ENTRY_OFFSETS)
    reduced = Heads(board, entry)
    decoded = decode(reduced, entry_threshold=ENTRY_THRESHOLD)
    if decoded != decode(heads, entry_threshold=ENTRY_THRESHOLD):
        raise DartsMlError(f"{name}: the sparse heads decode differently from the full ones")
    located = _board(matrix, reduced)
    if located_record(located) != located_record(_board(matrix, heads)):
        raise DartsMlError(f"{name}: the sparse heads locate differently from the full ones")
    return {"name": name, "matrix": [float(v) for v in matrix.ravel()], "board": board_record, "entry": entry_record,
            "calibration": {str(c): [p.x, p.y, p.confidence] for c, p in sorted(decoded.calibration.items())},
            "entries": [[p.x, p.y, p.confidence] for p in decoded.entries],
            "located": located_record(located)}


def heads_from_record(case: dict) -> tuple[np.ndarray, Heads]:
    """A committed `heads-*.json`'s matrix and sparse heads, rebuilt as `heads_case` reduced them."""
    def head(record: dict) -> np.ndarray:
        values = np.zeros(record["shape"], dtype=np.float32)
        values[slice(*record["heat"])] = record["fill"]
        for index, value in record["cells"]:
            values.flat[index] = value
        return values

    return np.array(case["matrix"]).reshape(3, 3), Heads(head(case["board"]), head(case["entry"]))


def write_fixtures(target: Path, heads: list[dict] | None = None) -> list[Path]:
    target.mkdir(parents=True, exist_ok=True)
    written = []
    scores = target / "scores.tsv"
    scores.write_text("x_mm\ty_mm\tscore\n" + "".join(f"{x!r}\t{y!r}\t{t}\n" for x, y, t in scoring_table()),
                      encoding="utf-8")
    written.append(scores)
    for name, content in (("rng.json", [{"population": n, "picked": p} for n, p in rng_choices()]),
                          ("warp.json", warp_cases())):
        (target / name).write_text(json.dumps(content, separators=(",", ":")), encoding="utf-8")
        written.append(target / name)
    for case in heads or []:
        path = target / f"heads-{case['name']}.json"
        path.write_text(json.dumps(case, separators=(",", ":")), encoding="utf-8")
        written.append(path)
    return written


def write_display_p3_source(target: Path) -> Path:
    """`MediaFilesTest`'s Display P3 source: sRGB red in Display P3's numbers, tagged with `display_p3()`, so the test
    does not depend on whether the device's own encoder embeds a P3 profile (API 26's does not)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    p3 = to_display_p3(Image.new("RGB", (160, 120), (255, 0, 0)))
    p3.save(target, "JPEG", quality=95, icc_profile=p3.info["icc_profile"])
    return target


def as_stored(photo: Path, target: Path) -> tuple[float, float]:
    """`photo` written to `target` as `MediaFiles` writes the `photos` kind: a power-of-two subsample, the long edge
    capped at PHOTOS_LONG_EDGE with a bilinear scale, JPEG at PHOTOS_QUALITY with no metadata; returns the scale on
    each axis. A Photo with an EXIF rotation is refused rather than baked in, since its labels sit on the unrotated
    pixels."""
    with Image.open(photo) as image:
        if image.getexif().get(_EXIF_ORIENTATION, 1) != 1:
            raise DartsMlError(f"{photo} carries an EXIF rotation, and its labels are on the unrotated pixels")
        width, height = image.size
        sample = 1
        while max(width, height) // (sample * 2) >= PHOTOS_LONG_EDGE:
            sample *= 2
        reduced = as_srgb(image).reduce(sample)
    longest = max(reduced.size)
    if longest > PHOTOS_LONG_EDGE:
        ratio = PHOTOS_LONG_EDGE / longest
        reduced = reduced.resize((max(1, int(reduced.width * ratio)), max(1, int(reduced.height * ratio))),
                                 Image.Resampling.BILINEAR)
    target.parent.mkdir(parents=True, exist_ok=True)
    reduced.save(target, "JPEG", quality=PHOTOS_QUALITY)
    return reduced.width / width, reduced.height / height


def as_stored_samples(samples: list[Sample], folder: Path) -> list[Sample]:
    """Each Sample's Photo written through `as_stored` into `folder`, its labels scaled with it (phase-1.md §1)."""
    stored = []
    for i, sample in enumerate(samples):
        sx, sy = as_stored(sample.photo, folder / f"{i:05d}.jpg")
        stored.append(replace(sample, photo=folder / f"{i:05d}.jpg",
                              calibration=tuple((c, x * sx, y * sy, w) for c, x, y, w in sample.calibration),
                              entries=tuple((x * sx, y * sy) for x, y in sample.entries)))
    return stored


def picked(samples: list, count: int) -> list:
    """`count` Photos spread evenly through the split in its recorded order, the same ones every time."""
    if not 0 < count <= len(samples):
        raise DartsMlError(f"asked for {count} Photos of {len(samples)}")
    return [samples[i * len(samples) // count] for i in range(count)]


def display_p3_copies(sources: list[tuple[str, Path]], folder: Path, count: int) -> list[tuple[str, Path]]:
    """`count` of the sources, spread as `picked` spreads them, rewritten as the same scene in Display P3's numbers
    and tagged with its profile, as a Xiaomi stores a Photo: the gate then also reads a colour-profiled Photo."""
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    copies = []
    for name, photo in picked(sources, min(count, len(sources))):
        target = folder / f"{DISPLAY_P3_PREFIX}{name}"
        p3 = to_display_p3(open_srgb(photo))
        p3.save(target, "JPEG", quality=95, icc_profile=p3.info["icc_profile"])
        copies.append((target.name, target))
    return copies


def device_name(sample) -> str:
    return f"{sample.capture_session}__{Path(sample.photo).stem}.jpg"


def expected_record(name: str, located: Located) -> dict:
    record = {"name": name, **located_record(located)}
    record["crossings_px"] = ([[float(x), float(y)] for x, y in
                               project(invert(located.to_board), [p.mm for p in CALIBRATION_POINTS])]
                              if located.found else [])
    return record


def same_model(run_model: Path, app_model: Path = APP_MODEL) -> None:
    if not app_model.exists():
        raise DartsMlError(f"no model in the app at {app_model}")
    if app_model.read_bytes() != run_model.read_bytes():
        raise DartsMlError(f"{app_model} is not {run_model}: the gate compares the model the app ships")


def run_parity(device, sources: list[tuple[str, Path]], folder: Path, run: str,
               locate_written: Callable[[list[Path]], list[Located]], say: Callable[[str], None]) -> str:
    """Push the Photos, have the phone write each through MediaFiles, locate the written files here, push that
    back, and have the phone compare its own pipeline against it; returns the phone's report."""
    for sub in ("source", "written"):
        shutil.rmtree(folder / sub, ignore_errors=True)
    (folder / "source").mkdir(parents=True)
    # shell makes these 2770 shell:ext_data_rw, which an API 36 app can neither list nor write into; a+rwx keeps the
    # setgid bit, so what the app writes stays in ext_data_rw and `adb pull` can read it.
    device.shell(f"rm -rf {DEVICE_DIR} && mkdir -p {DEVICE_DIR}/source && chmod a+rwx {DEVICE_DIR} {DEVICE_DIR}/source")
    say(f"pushing {len(sources)} Photos to {DEVICE_DIR}/source ...")
    for name, photo in sources:
        shutil.copyfile(photo, folder / "source" / name)
    device.adb("push", *[str(folder / "source" / name) for name, _ in sources], f"{DEVICE_DIR}/source/")
    say("the phone writes each through MediaFiles ...")
    _instrument(device, "writesEachPhotoThroughMediaFiles")
    device.adb("pull", f"{DEVICE_DIR}/written", str(folder))
    written = sorted((folder / "written").glob("*.jpg"))
    if [p.name for p in written] != sorted(name for name, _ in sources):
        raise DartsMlError(f"the phone wrote {len(written)} of {len(sources)} Photos; see `adb logcat`")
    say(f"locating the {len(written)} written Photos in Python ...")
    located = locate_written(written)
    expected = {"run": run, "photos": [expected_record(p.name, found) for p, found in zip(written, located, strict=True)]}
    (folder / EXPECTED).write_text(json.dumps(expected, indent=1), encoding="utf-8")
    device.push(folder / EXPECTED, f"{DEVICE_DIR}/{EXPECTED}")
    say("the phone runs its own pipeline on them and compares ...")
    output = _instrument(device, "matchesPythonOnEachPhoto", check=False)
    device.adb("pull", f"{DEVICE_DIR}/{REPORT}", str(folder / REPORT))
    report = (folder / REPORT).read_text(encoding="utf-8")
    return report + ("" if "OK (1 test)" in output else "\n" + output)


def _instrument(device, method: str, check: bool = True) -> str:
    output = device.shell(f"am instrument -w -e class {TEST_CLASS}#{method} {TEST_RUNNER}")
    if check and "OK (1 test)" not in output:
        raise DartsMlError(f"{method} did not pass:\n{output}")
    return output


def chosen_heads(samples: list, run, folder: Path) -> list[dict]:
    """The decoding fixtures: a Photo with no Board (a strip off one side, enough Calibration points for RANSAC to
    run and fail on), one whose kept Darts include two in one
    bed, and one with three Darts in three beds; each Board-found one at its second pass, as `locate` reads it."""
    from .augment import framing
    from .locate import _logits

    def heads(photo: Path, matrix: np.ndarray) -> Heads:
        return next(iter(_logits(run, [(photo, matrix)])))

    def second_pass(photo: Path) -> tuple[np.ndarray, Heads] | None:
        with Image.open(photo) as image:
            first = letterbox(image.size, run.size)
        board = _board(first, heads(photo, first)).to_board
        if board is None:
            return None
        second = framing(invert(board), run.size)
        return second, heads(photo, second)

    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for sample in samples:
        strip = folder / "strip.jpg"
        image = open_srgb(sample.photo)
        image.crop((0, 0, _STRIP_PX, image.height)).save(strip, quality=95)
        first = letterbox((_STRIP_PX, image.height), run.size)
        read = heads(strip, first)
        if len(decode(read).calibration) >= MIN_INLIERS and not _board(first, read).found:
            cases.append(heads_case("no-board", first, read))
            break
    if not cases:
        raise DartsMlError(f"no val Photo's left {_STRIP_PX} px gave {MIN_INLIERS} Calibration points and no Board")
    wanted = {"two-in-one-bed": lambda tokens: len(tokens) > len(set(tokens)),
              "three-beds": lambda tokens: len(tokens) == 3 == len(set(tokens))}
    for sample in samples:
        if not wanted:
            break
        read = second_pass(sample.photo)
        if read is None:
            continue
        case = heads_case(f"{sample.capture_session}__{Path(sample.photo).stem}", *read)
        tokens = [d[3] for d in case["located"]["darts"]]
        for kind, fits in list(wanted.items()):
            if fits(tokens):
                case["name"] = kind
                cases.append(case)
                del wanted[kind]
                break
    if wanted:
        raise DartsMlError(f"no Photo found for {', '.join(wanted)}")
    return cases
