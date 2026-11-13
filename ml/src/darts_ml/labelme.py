from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, HAND_POINTS
from .capture_sessions import load_sheet
from .manifest import ReviewManifest
from .paths import DataDir, Round

PINNED = "7.9.1"
RESOLVED_AS_OF = "2026-10-26T00:00:00Z"
ENTRY = "entry"
INFERRED = "inferred"
LABELS = (*(point.name for point in CALIBRATION_POINTS), ENTRY)
_UNREACHABLE_PROXY = "http://127.0.0.1:9"


class LabelError(DartsMlError):
    pass


@dataclass(frozen=True)
class Shape:
    label: str
    x: float
    y: float
    shape_type: str = "point"
    flags: dict = field(default_factory=dict)
    description: str = ""

    @property
    def xy(self) -> tuple[float, float]:
        return self.x, self.y

    @property
    def inferred(self) -> bool:
        return bool(self.flags.get(INFERRED))

    def to_json(self) -> dict:
        return {
            "label": self.label,
            "points": [[self.x, self.y]],
            "group_id": None,
            "description": self.description,
            "shape_type": self.shape_type,
            "flags": dict(self.flags),
            "mask": None,
        }


@dataclass(frozen=True)
class Label:
    path: Path
    image_path: str
    width: int
    height: int
    has_image_data: bool
    shapes: tuple[Shape, ...]

    @property
    def calibration(self) -> dict[str, tuple[float, float]]:
        return {s.label: s.xy for s in self.shapes if s.label in CALIBRATION_BY_NAME}

    @property
    def entries(self) -> list[Shape]:
        return [s for s in self.shapes if s.label == ENTRY]

    def photo_path(self) -> Path:
        return (self.path.parent / self.image_path).resolve()


def read_label(path: Path) -> Label:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        shapes = tuple(
            Shape(
                label=s["label"],
                x=float(s["points"][0][0]),
                y=float(s["points"][0][1]),
                shape_type=s.get("shape_type", ""),
                flags=dict(s.get("flags") or {}),
                description=s.get("description") or "",
            )
            for s in raw["shapes"]
        )
        return Label(
            path=path,
            image_path=raw["imagePath"],
            width=int(raw["imageWidth"]),
            height=int(raw["imageHeight"]),
            has_image_data=raw.get("imageData") is not None,
            shapes=shapes,
        )
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        raise LabelError(f"{path}: not a labelme label this code can read ({error})") from None


def write_label(path: Path, photo: Path, width: int, height: int, shapes) -> None:
    payload = {
        "version": PINNED,
        "flags": {},
        "shapes": [shape.to_json() for shape in shapes],
        "imagePath": os.path.relpath(photo, path.parent),
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def label_path(labels: Path, photo: str) -> Path:
    return labels / f"{photo}.json"


def labelme_command(*arguments: str) -> list[str]:
    return ["uvx", "--exclude-newer", RESOLVED_AS_OF, "--from", f"labelme=={PINNED}", "labelme", *arguments]


def window_command(photo: Path, output: Path) -> list[str]:
    return labelme_command(
        str(photo),
        "--output",
        str(output),
        "--config",
        "{with_image_data: false, auto_save: true}",
        "--labels",
        ",".join(LABELS),
        "--no-sort-labels",
        "--validate-label",
        "exact",
        "--label-flags",
        f"{{'^{ENTRY}$': [{INFERRED}]}}",
    )


def offline_environment(environ=os.environ) -> dict[str, str]:
    env = dict(environ)
    env["UV_OFFLINE"] = "1"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env[name] = env[name.lower()] = _UNREACHABLE_PROXY
    env["NO_PROXY"] = env["no_proxy"] = ""
    return env


def fetch() -> None:
    result = subprocess.run(labelme_command("--version"), capture_output=True, text=True)
    if result.returncode != 0:
        raise LabelError(f"could not fetch labelme {PINNED} through uvx:\n{result.stderr.strip()}")


def open_window(photo: Path, output: Path) -> float:
    started = time.monotonic()
    result = subprocess.run(window_command(photo, output), env=offline_environment())
    if result.returncode != 0:
        raise LabelError(f"labelme exited with {result.returncode} on {photo.name}")
    return time.monotonic() - started


def instructions(round_: Round) -> str:
    if round_ is Round.C:
        return "Round c, no pre-fill: click every visible crossing under its name, then the Entry points."
    return (
        f"Click the four Hand points, {', '.join(HAND_POINTS)}, or the nearest visible "
        "outer-double crossing under its own name for one that is covered. Then click every "
        f"Entry point as `{ENTRY}`, flagging `{INFERRED}` one placed where a hidden shaft meets the Board."
    )


def label(data: DataDir, name: str, round_: Round = Round.A, window=open_window, say=print) -> int:
    sheet = load_sheet(data.sheet(name))
    labels = data.labels(name, round_)
    labels.mkdir(parents=True, exist_ok=True)
    manifest = ReviewManifest.load(labels)
    say(instructions(round_))
    opened = 0
    for photo in map(str, sheet.photo_names()):
        target = label_path(labels, photo)
        if target.exists():
            continue
        source = data.photo(name, photo)
        if not source.exists():
            raise LabelError(f"no Photo {source}; run `darts-ml ingest {name}` first")
        seconds = window(source, labels)
        opened += 1
        if not target.exists():
            say(f"{photo}: no label was saved; it opens again next time")
            continue
        manifest.record(photo).label_seconds += seconds
        manifest.save()
    return opened
