from __future__ import annotations

import datetime as dt
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tomli_w
from PIL import Image

from . import DartsMlError
from .capture_sessions import PhotoName, load_sheet
from .paths import DataDir

JPEG_START = b"\xff\xd8\xff"
EXIF_IFD = 0x8769
ORIENTATION = 0x0112
MAKE = 0x010F
MODEL = 0x0110
DATE_TIME_ORIGINAL = 0x9003
SUBSEC_TIME_ORIGINAL = 0x9291
TRANSFORMS = {
    1: [],
    2: ["-flip", "horizontal"],
    3: ["-rotate", "180"],
    4: ["-flip", "vertical"],
    5: ["-transpose"],
    6: ["-rotate", "90"],
    7: ["-transverse"],
    8: ["-rotate", "270"],
}
_MARKERS_WITHOUT_LENGTH = {0x01, *range(0xD0, 0xD8)}


class IngestError(DartsMlError):
    pass


@dataclass(frozen=True)
class Shot:
    path: Path
    taken: dt.datetime
    orientation: int
    camera: str


def jpegtran_version(jpegtran: str = "jpegtran") -> str | None:
    if shutil.which(jpegtran) is None:
        return None
    result = subprocess.run([jpegtran, "-version"], capture_output=True, text=True)
    return (result.stderr or result.stdout).strip().splitlines()[0]


def read_shot(path: Path) -> Shot:
    with path.open("rb") as file:
        if file.read(3) != JPEG_START:
            raise IngestError(f"{path.name} is not a JPEG; set the camera to JPEG, not HEIF")
    with Image.open(path) as image:
        exif = image.getexif()
    details = exif.get_ifd(EXIF_IFD)
    taken = details.get(DATE_TIME_ORIGINAL)
    if not taken:
        raise IngestError(f"{path.name} has no EXIF DateTimeOriginal, so its capture order is unknown")
    moment = dt.datetime.strptime(str(taken).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    subsec = str(details.get(SUBSEC_TIME_ORIGINAL) or "").strip("\x00 ")
    if subsec.isdigit():
        moment += dt.timedelta(seconds=float(f"0.{subsec}"))
    orientation = int(exif.get(ORIENTATION, 1))
    if orientation not in TRANSFORMS:
        raise IngestError(f"{path.name} has an unknown EXIF orientation {orientation}")
    camera = " ".join(str(exif.get(tag, "")).strip("\x00 ") for tag in (MAKE, MODEL)).strip()
    return Shot(path, moment, orientation, camera)


def jpegtran_command(shot: Shot, target: Path, jpegtran: str = "jpegtran") -> list[str]:
    transform = TRANSFORMS[shot.orientation]
    trim = ["-trim"] if transform else []
    return [jpegtran, "-copy", "none", *transform, *trim, "-outfile", str(target), str(shot.path)]


def metadata_markers(path: Path) -> list[str]:
    data = path.read_bytes()
    found, offset = [], 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            raise IngestError(f"{path.name}: malformed JPEG marker at byte {offset}")
        marker = data[offset + 1]
        if marker == 0xFF:
            offset += 1
            continue
        if marker == 0xDA:
            break
        if marker in _MARKERS_WITHOUT_LENGTH:
            offset += 2
            continue
        if 0xE1 <= marker <= 0xEF:
            found.append(f"APP{marker - 0xE0}")
        elif marker == 0xFE:
            found.append("COM")
        offset += 2 + int.from_bytes(data[offset + 2 : offset + 4], "big")
    return found


def ingest(data: DataDir, name: str, jpegtran: str = "jpegtran") -> list[PhotoName]:
    if jpegtran_version(jpegtran) is None:
        raise IngestError("jpegtran is not installed; it comes with libjpeg-turbo (libjpeg-turbo-progs)")
    sheet = load_sheet(data.sheet(name))
    if sheet.ingested:
        raise IngestError(f"{data.sheet(name)} already holds an [ingest] table: {name} was ingested")
    target = data.photos(name)
    if target.exists() and any(target.iterdir()):
        raise IngestError(f"{target} already holds Photos; ingest never overwrites")
    shots = _ordered_shots(data.inbox(name))
    names = sheet.photo_names()
    if len(shots) != len(names):
        listing = "\n".join(f"  {s.taken:%Y-%m-%d %H:%M:%S.%f}  {s.path.name}" for s in shots)
        raise IngestError(
            f"{name}: the sheet has {len(sheet.visits)} Visits, so {len(names)} Photos, "
            f"but the inbox holds {len(shots)}. Nothing was ingested. In capture order:\n{listing}"
        )
    staging = target.with_name(f".{name}.ingesting")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for shot, photo in zip(shots, names, strict=True):
        out = staging / f"{photo}.jpg"
        result = subprocess.run(jpegtran_command(shot, out, jpegtran), capture_output=True, text=True)
        if result.returncode != 0:
            raise IngestError(f"jpegtran failed on {shot.path.name}: {result.stderr.strip()}")
        left = metadata_markers(out)
        if left:
            raise IngestError(f"{out.name} still carries {', '.join(left)} after jpegtran -copy none")
    if target.exists():
        target.rmdir()
    staging.rename(target)
    _record_in_sheet(data.sheet(name), shots, names)
    return names


def _ordered_shots(inbox: Path) -> list[Shot]:
    if not inbox.is_dir():
        raise IngestError(f"no inbox at {inbox}; copy the Capture session's files there by USB")
    shots, refused = [], []
    for path in sorted(p for p in inbox.iterdir() if p.is_file()):
        try:
            shots.append(read_shot(path))
        except IngestError as error:
            refused.append(str(error))
    if refused:
        raise IngestError("Nothing was ingested:\n  " + "\n  ".join(refused))
    return sorted(shots, key=lambda shot: (shot.taken, shot.path.name))


def _record_in_sheet(sheet: Path, shots: list[Shot], names: list[PhotoName]) -> None:
    photos = {str(n): {"camera": s.camera, "taken": s.taken} for s, n in zip(shots, names, strict=True)}
    table = tomli_w.dumps({"ingest": {"date": dt.date.today(), "photos": photos}})
    text = sheet.read_text(encoding="utf-8")
    sheet.write_text(text + ("" if text.endswith("\n") else "\n") + "\n" + table, encoding="utf-8")
