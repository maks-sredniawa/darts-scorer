"""A Mounted camera's Capture session, built from the marked Visits `pull-marked` copied off the Player's phone (phase-G.md §2)."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w
from PIL import Image, UnidentifiedImageError

from . import DartsMlError
from .board import Score
from .capture_sessions import GATE, Light, Mount, PhotoName
from .ingest import JPEG_START, ORIENTATION, metadata_markers
from .paths import DataDir, capture_session


class MountedError(DartsMlError):
    pass


@dataclass(frozen=True)
class KeptVisit:
    record: Path
    photo: Path
    kept_at: dt.datetime
    board_found: bool
    darts: tuple[str, ...]


@dataclass
class Built:
    photos: list[PhotoName] = field(default_factory=list)
    left_out: list[tuple[str, str]] = field(default_factory=list)


def read_kept(record: Path) -> KeptVisit:
    raw = json.loads(record.read_text(encoding="utf-8"))
    name = raw["photo"]
    if Path(name).name != name or not name.endswith(".jpg"):
        raise ValueError(f"photo {name!r} is not a plain .jpg name")
    kept_at = dt.datetime.fromisoformat(raw["keptAt"])
    if kept_at.tzinfo is None:
        raise ValueError(f"keptAt {raw['keptAt']!r} names no time zone")
    # A Dart the app filled in as a Miss to make up three was never thrown; the sheet records the thrown ones.
    darts = tuple(str(d["score"]) for d in raw["darts"] if not d.get("filled", False))
    for token in darts:
        Score.parse(token)
    photo = record.parent / name
    _check_photo(photo, (int(raw["width"]), int(raw["height"])))
    return KeptVisit(record, photo, kept_at, bool(raw["boardFound"]), darts)


def _check_photo(photo: Path, recorded: tuple[int, int]) -> None:
    if not photo.is_file():
        raise ValueError(f"its Photo {photo.name} is missing")
    with photo.open("rb") as file:
        if file.read(3) != JPEG_START:
            raise ValueError(f"its Photo {photo.name} is not a JPEG")
    try:
        with Image.open(photo) as image:
            size, orientation = image.size, image.getexif().get(ORIENTATION, 1)
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError(f"its Photo {photo.name} cannot be read ({error})") from error
    if size != recorded:
        raise ValueError(f"its Photo {photo.name} is {size[0]}×{size[1]}, the record says {recorded[0]}×{recorded[1]}")
    if orientation != 1:
        raise ValueError(f"its Photo {photo.name} carries EXIF orientation {orientation}")
    left = metadata_markers(photo)
    if left:
        raise ValueError(f"its Photo {photo.name} carries {', '.join(left)}; a marked Photo holds no metadata")


def claimed(data: DataDir) -> dict[str, str]:
    owners = {}
    for path in sorted(data.sheets().glob("*.toml")) if data.sheets().is_dir() else []:
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise MountedError(f"{path}: {error}") from None
        for entry in raw.get("ingest", {}).get("photos", {}).values():
            if isinstance(entry, dict) and "marked" in entry:
                owners[entry["marked"]] = path.stem
    return owners


def build_mounted(data: DataDir, name: str, day: str, mount: Mount, light: Light, phone: str,
                  kept_from: dt.datetime | None = None, kept_until: dt.datetime | None = None) -> Built:
    name = capture_session(name)
    sheet = data.sheet(name)
    if sheet.exists():
        raise MountedError(f"{sheet} already exists; a Capture session is built once")
    target = data.photos(name)
    if target.exists() and any(target.iterdir()):
        raise MountedError(f"{target} already holds Photos; this step never overwrites")
    if Path(day).name != day or day in ("", ".", ".."):
        raise MountedError(f"--day is one folder under {data.phone_captures()}, such as 2026-11-24, not {day!r}")
    folder = data.phone_captures() / day
    if not folder.is_dir():
        raise MountedError(f"no {folder}; `darts-ml pull-marked` copies the marked Visits there")
    owners = claimed(data)
    built = Built()
    kept, refused = [], []
    for record in sorted(folder.glob("*.json")):
        key = record.relative_to(data.root).as_posix()
        if key in owners:
            built.left_out.append((record.name, f"already in {owners[key]}"))
            continue
        try:
            visit = read_kept(record)
        except (KeyError, TypeError, ValueError) as error:
            refused.append(f"{record.name}: not a marked Visit this step can read ({error})")
            continue
        if (kept_from and visit.kept_at < kept_from) or (kept_until and visit.kept_at >= kept_until):
            built.left_out.append((record.name, f"kept at {visit.kept_at.isoformat()}, outside the window"))
            continue
        kept.append(visit)
    if refused:
        raise MountedError("Nothing was built:\n  " + "\n  ".join(refused))
    if not kept:
        raise MountedError(f"no marked Visit in {folder} to build {name} from")
    kept.sort(key=lambda visit: (visit.kept_at, visit.record.name))
    built.photos = [PhotoName(name, number, 1) for number in range(1, len(kept) + 1)]
    staging = target.with_name(f".{name}.building")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for visit, photo in zip(kept, built.photos, strict=True):
        shutil.copyfile(visit.photo, staging / f"{photo}.jpg")
    if target.exists():
        target.rmdir()
    staging.rename(target)
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_text(tomli_w.dumps(_sheet(data, kept, built.photos, mount, light, phone)), encoding="utf-8")
    return built


def _sheet(data: DataDir, kept: list[KeptVisit], photos: list[PhotoName], mount: Mount, light: Light,
           phone: str) -> dict:
    return {
        "phone": phone,
        "light": light.value,
        "set": GATE,
        "date": kept[0].kept_at.astimezone().date(),
        "mount": {"height_cm": mount.height_cm, "distance_cm": mount.distance_cm, "angle_deg": mount.angle_deg},
        "visits": [{"darts": list(visit.darts)} for visit in kept],
        "ingest": {
            "date": dt.date.today(),
            "photos": {
                str(photo): {
                    "marked": visit.record.relative_to(data.root).as_posix(),
                    "kept_at": visit.kept_at,
                    "board_found": visit.board_found,
                }
                for visit, photo in zip(kept, photos, strict=True)
            },
        },
    }
