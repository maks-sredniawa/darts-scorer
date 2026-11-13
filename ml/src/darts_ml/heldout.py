from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from . import DartsMlError
from .capture_sessions import PhotoName, load_sheet
from .check import check
from .labelme import label_path
from .manifest import FILE_NAME as REVIEW_FILE
from .paths import DataDir

MANIFEST = Path(__file__).resolve().parents[2] / "splits" / "held-out.toml"


class HeldOutError(DartsMlError):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class FrozenSession:
    sheet: str
    review: str


@dataclass(frozen=True)
class FrozenPhoto:
    photo: str
    label: str


@dataclass(frozen=True)
class HeldOutSet:
    capture_sessions: dict[str, FrozenSession]
    photos: dict[str, FrozenPhoto]

    @classmethod
    def load(cls, path: Path = MANIFEST) -> HeldOutSet:
        if not path.exists():
            raise HeldOutError(f"no frozen Held-out set at {path}; `darts-ml freeze-held-out` writes it (G)")
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            sessions = {n: FrozenSession(e["sheet"], e["review"]) for n, e in raw["capture_sessions"].items()}
            photos = {n: FrozenPhoto(e["photo"], e["label"]) for n, e in raw["photos"].items()}
        except (tomllib.TOMLDecodeError, KeyError, TypeError) as error:
            raise HeldOutError(f"{path}: not a held-out manifest this code can read ({error})") from None
        held = cls(sessions, photos)
        strays = sorted(n for n in photos if PhotoName.parse(n).capture_session not in sessions)
        if strays:
            raise HeldOutError(f"{path}: Photos of Capture sessions the manifest does not freeze: {', '.join(strays)}")
        return held

    def save(self, path: Path = MANIFEST) -> None:
        payload = {
            "capture_sessions": {n: {"sheet": s.sheet, "review": s.review} for n, s in sorted(self.capture_sessions.items())},
            "photos": {n: {"photo": p.photo, "label": p.label} for n, p in sorted(self.photos.items())},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".toml.tmp")
        temporary.write_text(tomli_w.dumps(payload), encoding="utf-8")
        temporary.replace(path)

    def photo_names(self) -> list[PhotoName]:
        return sorted(PhotoName.parse(name) for name in self.photos)

    def refusal(self, photo: PhotoName, sheet_held_out: bool, photo_sha: str | None, label_sha: str | None) -> str | None:
        if sheet_held_out:
            return f"its sheet says {photo.capture_session} is held-out"
        if photo.capture_session in self.capture_sessions:
            return f"{photo.capture_session} is a held-out Capture session"
        if photo_sha is not None and photo_sha in {p.photo for p in self.photos.values()}:
            return "its bytes are a held-out Photo's"
        if label_sha is not None and label_sha in {p.label for p in self.photos.values()}:
            return "its label's bytes are a held-out Photo's label"
        return None


def freeze(data: DataDir) -> HeldOutSet:
    sheets = [load_sheet(path) for path in sorted(data.sheets().glob("*.toml"))]
    held_out = [sheet for sheet in sheets if sheet.held_out]
    if not held_out:
        raise HeldOutError(f"no sheet in {data.sheets()} says set = \"held-out\"")
    unclean = [s.capture_session for s in held_out if not check(data, s.capture_session).clean]
    if unclean:
        raise HeldOutError(f"`darts-ml check` is not clean on {', '.join(unclean)}; the Held-out set freezes only clean")
    sessions, photos = {}, {}
    for sheet in held_out:
        labels = data.labels(sheet.capture_session)
        sessions[sheet.capture_session] = FrozenSession(
            file_sha256(data.sheet(sheet.capture_session)), file_sha256(labels / REVIEW_FILE)
        )
        for photo in map(str, sheet.photo_names()):
            photos[photo] = FrozenPhoto(
                file_sha256(data.photo(sheet.capture_session, photo)), file_sha256(label_path(labels, photo))
            )
    return HeldOutSet(sessions, photos)


def verify(data: DataDir, held: HeldOutSet) -> list[str]:
    problems = []

    def compare(path: Path, expected: str, what: str) -> None:
        if not path.exists():
            problems.append(f"{what}: missing ({path})")
        elif file_sha256(path) != expected:
            problems.append(f"{what}: changed since the freeze ({path})")

    for name, frozen in sorted(held.capture_sessions.items()):
        compare(data.sheet(name), frozen.sheet, f"{name} sheet")
        compare(data.labels(name) / REVIEW_FILE, frozen.review, f"{name} review manifest")
        if data.sheet(name).exists() and file_sha256(data.sheet(name)) == frozen.sheet:
            for photo in map(str, load_sheet(data.sheet(name)).photo_names()):
                if photo not in held.photos:
                    problems.append(f"{photo}: in the {name} sheet, and the manifest does not freeze it")
    for photo in held.photo_names():
        frozen = held.photos[str(photo)]
        compare(data.photo(photo.capture_session, str(photo)), frozen.photo, f"{photo} Photo")
        compare(label_path(data.labels(photo.capture_session), str(photo)), frozen.label, f"{photo} label")
    for path in sorted(data.sheets().glob("*.toml")) if data.sheets().exists() else []:
        if path.stem not in held.capture_sessions and load_sheet(path).held_out:
            problems.append(f"{path.stem}: its sheet says held-out, and the manifest does not freeze it")
    return problems


def verified(data: DataDir, path: Path = MANIFEST) -> HeldOutSet:
    held = HeldOutSet.load(path)
    problems = verify(data, held)
    if problems:
        raise HeldOutError("the Held-out set does not match its frozen manifest:\n" + "\n".join(problems))
    return held
