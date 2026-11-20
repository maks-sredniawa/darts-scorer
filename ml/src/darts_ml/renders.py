"""Synthetic renders from the owner's darts-render fork, as training records (ml/README.md, *Synthetic renders*)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

from . import DartsMlError
from .board import (CALIBRATION_POINTS, INNER_DOUBLE, INNER_TREBLE, OUTER_DOUBLE, SEGMENT_DEGREES, SEGMENTS,
                    board_point, boundary_degrees, score)
from .homography import fit, invert, project
from .paths import DataDir

RECORDS = "records.jsonl"
MANIFEST = "manifest.json"
SOURCE = "render"
LOOKS = ("default", "owner")
MAX_RESIDUAL_PX = 0.5
_ZONES = {"DB": "50", "SB": "25", "MISS": "miss"}
_FRAME = re.compile(r"[0-9A-Za-z_-]+")


def renderer_mm(name: str) -> tuple[float, float]:
    """Where darts-render puts a keypoint, in board.py's millimetres; its rings are board.py's wire centres."""
    parts = name.split("_")
    try:
        if name == "center":
            return 0.0, 0.0
        if len(parts) == 4 and parts[0] == "double" and parts[1] in ("outer", "inner"):
            index = SEGMENTS.index(int(parts[2]))
            if SEGMENTS[(index + 1) % len(SEGMENTS)] != int(parts[3]):
                raise ValueError
            wire = OUTER_DOUBLE if parts[1] == "outer" else INNER_DOUBLE
            return board_point(wire.centre_mm, boundary_degrees(index))
        if len(parts) == 2 and parts[0] in ("double", "triple"):
            wire = OUTER_DOUBLE if parts[0] == "double" else INNER_TREBLE
            return board_point(wire.centre_mm, SEGMENT_DEGREES * SEGMENTS.index(int(parts[1])))
    except ValueError:
        pass
    raise DartsMlError(f"not a darts-render keypoint: {name!r}; has the renderer's annotation format changed?")


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    residual_px: float
    calibration: tuple[tuple[str, float, float], ...] = ()
    entries: tuple[tuple[float, float, str], ...] = ()
    off_image: int = 0
    zones_differ: int = 0
    refusal: str | None = None


def convert_frame(annotation: dict, max_residual_px: float = MAX_RESIDUAL_PX) -> Frame:
    width, height = (int(v) for v in annotation["camera_params"]["resolution"])
    keypoints = annotation["board_keypoints"]
    source = np.array([renderer_mm(k["name"]) for k in keypoints])
    target = np.array([(k["x"], k["y"]) for k in keypoints], dtype=float)
    to_image = fit(source, target)
    residual = float(np.linalg.norm(project(to_image, source) - target, axis=1).max())
    if not residual <= max_residual_px:
        return Frame(width, height, residual, refusal=f"the {len(keypoints)} keypoints fit one plane only to "
                                                       f"{residual:.2f} px, over {max_residual_px:g} px")
    crossings = project(to_image, [p.mm for p in CALIBRATION_POINTS])
    calibration = tuple((p.name, float(x), float(y)) for p, (x, y) in zip(CALIBRATION_POINTS, crossings, strict=True))
    to_board = invert(to_image)
    entries, off_image, zones_differ = [], 0, 0
    for dart in annotation["darts"]:
        x, y = float(dart["x"]), float(dart["y"])
        if not (0 <= x < width and 0 <= y < height):
            off_image += 1
            continue
        token = str(score(*project(to_board, [(x, y)])[0]))
        zones_differ += token != _ZONES.get(dart["score_zone"], dart["score_zone"])
        entries.append((x, y, token))
    return Frame(width, height, residual, calibration, tuple(entries), off_image, zones_differ)


@dataclass(frozen=True)
class Renderer:
    commit: str
    look: str
    options: dict[str, str] = field(default_factory=dict)


def renderer_commit(clone: Path) -> str:
    def git(*argv: str) -> str:
        return subprocess.run(["git", "-C", str(clone), *argv], capture_output=True, text=True, check=True).stdout.strip()

    try:
        head = git("rev-parse", "HEAD")
        return head + ("-dirty" if git("status", "--porcelain", "--untracked-files=no") else "")
    except (OSError, subprocess.CalledProcessError) as error:
        raise DartsMlError(f"--renderer {clone}: not a git clone of darts-render ({error})") from error


@dataclass(frozen=True)
class Imported:
    folder: Path
    records: int
    darts: int
    refused: tuple[tuple[str, str], ...]
    off_image: int
    zones_differ: int


def import_renders(data: DataDir, source: Path, name: str, renderer: Renderer, max_residual_px: float = MAX_RESIDUAL_PX,
                   log: Callable[[str], None] = lambda line: None, darts_ml_commit: str = "unknown") -> Imported:
    target = data.render_set(name)
    if target.exists():
        raise DartsMlError(f"{target} exists; a render set is never overwritten, so give this one another --set")
    annotations = sorted((source / "annotations").glob("*.json"))
    if not annotations:
        raise DartsMlError(f"no {source / 'annotations'}/*.json; point at the folder the renderer wrote")
    data.renders().mkdir(parents=True, exist_ok=True)
    part = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=data.renders()))
    try:
        imported = _convert_all(source, name, annotations, part, max_residual_px, log)
        records, residuals, refused, darts, off_image, zones_differ = imported
        if not records:
            raise DartsMlError(f"every one of the {len(annotations)} frames was refused, the first because "
                               f"{refused[0][1]}; nothing written")
        (part / RECORDS).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
        manifest = {
            "set": name, "imported": dt.datetime.now().isoformat(timespec="seconds"), "source": str(source),
            "renderer": {"repository": "maks-sredniawa/darts-render", "commit": renderer.commit,
                         "look": renderer.look, "options": renderer.options,
                         "manifest": _json_or_none(source / "manifest.json")},
            "darts_ml_commit": darts_ml_commit, "max_residual_px": max_residual_px,
            "frames": len(annotations), "records": len(records), "darts": darts,
            "darts_off_image": off_image, "zones_differ": zones_differ,
            "residual_px": {"median": float(np.median(residuals)), "max": float(max(residuals))} if residuals else None,
            "refused": [{"frame": frame, "reason": reason} for frame, reason in refused],
        }
        (part / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        part.rename(target)
    except BaseException:
        shutil.rmtree(part, ignore_errors=True)
        raise
    return Imported(target, len(records), darts, tuple(refused), off_image, zones_differ)


def _convert_all(source: Path, name: str, annotations: list[Path], part: Path, max_residual_px: float, log):
    (part / "rgb").mkdir()
    records, residuals, refused = [], [], []
    darts = off_image = zones_differ = 0
    for index, path in enumerate(annotations, 1):
        if index % 100 == 0 or index == len(annotations):
            log(f"[{index}/{len(annotations)}] {path.stem}")
        frame_id = path.stem
        if not _FRAME.fullmatch(frame_id):
            refused.append((frame_id, "not a plain frame name"))
            continue
        annotation = json.loads(path.read_text(encoding="utf-8"))
        image = _image(source, annotation, frame_id)
        if image is None:
            refused.append((frame_id, "its image is missing or lies outside the renderer's folder"))
            continue
        frame = convert_frame(annotation, max_residual_px)
        residuals.append(frame.residual_px)
        if frame.refusal:
            refused.append((frame_id, frame.refusal))
            continue
        with Image.open(image) as opened:
            if opened.size != (frame.width, frame.height):
                refused.append((frame_id, f"the image is {opened.size[0]}×{opened.size[1]}, the annotation says "
                                          f"{frame.width}×{frame.height}"))
                continue
        copy = part / "rgb" / f"{frame_id}.jpg"
        shutil.copyfile(image, copy)
        darts += len(frame.entries)
        off_image += frame.off_image
        zones_differ += frame.zones_differ
        records.append({
            "source": SOURCE, "set": name, "capture_session": f"{SOURCE}-{name}", "frame": frame_id,
            "photo": (PurePosixPath("renders") / name / "rgb" / copy.name).as_posix(),
            "photo_sha256": hashlib.sha256(copy.read_bytes()).hexdigest(),
            "width": frame.width, "height": frame.height,
            "calibration": [{"name": n, "x": x, "y": y, "source": SOURCE} for n, x, y in frame.calibration],
            "entries": [{"x": x, "y": y, "inferred": False} for x, y, _ in frame.entries],
            "scores": [token for _, _, token in frame.entries],
        })
    return records, residuals, refused, darts, off_image, zones_differ


def _image(source: Path, annotation: dict, frame_id: str) -> Path | None:
    relative = PurePosixPath(annotation.get("image_path") or f"rgb/{frame_id}.jpg")
    if relative.is_absolute() or ".." in relative.parts:
        return None
    path = source / relative
    return path if path.is_file() else None


def _json_or_none(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
