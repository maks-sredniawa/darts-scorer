from __future__ import annotations

import datetime as dt
import re
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import DartsMlError
from .board import Score
from .paths import capture_session

ANGLES = (1, 2, 3)
_PHOTO = re.compile(r"(s\d{2,3})-v(\d{2})-p([123])")


class SheetError(DartsMlError):
    pass


class Light(Enum):
    DAY = "day"
    EVENING = "evening"
    FLASH = "flash"
    HARSH = "harsh"


class Mark(Enum):
    WIRE = "wire"
    HIDDEN = "hidden"
    HIDDEN_P2 = "hidden-p2"
    HIDDEN_P3 = "hidden-p3"
    PLACED = "placed"


HIDDEN_IN = {1: Mark.HIDDEN, 2: Mark.HIDDEN_P2, 3: Mark.HIDDEN_P3}


OUT = "out"


@dataclass(frozen=True)
class RecordedDart:
    score: Score | None
    marks: frozenset[Mark]

    @property
    def in_board(self) -> bool:
        return self.score is not None

    @classmethod
    def parse(cls, text: str) -> RecordedDart:
        first, *rest = text.split()
        try:
            marks = frozenset(Mark(word) for word in rest)
        except ValueError:
            raise SheetError(f"{text!r}: marks are {', '.join(m.value for m in Mark)}") from None
        if first == OUT:
            return cls(None, marks)
        try:
            return cls(Score.parse(first), marks)
        except ValueError as error:
            raise SheetError(f"{text!r}: {error}") from None


@dataclass(frozen=True)
class Visit:
    number: int
    darts: tuple[RecordedDart, ...]

    @property
    def scores_in_board(self) -> list[Score]:
        return [dart.score for dart in self.darts if dart.score is not None]

    def hidden_in(self, angle: int) -> int:
        return sum(HIDDEN_IN[angle] in dart.marks for dart in self.darts if dart.in_board)


@dataclass(frozen=True, order=True)
class PhotoName:
    capture_session: str
    visit: int
    angle: int

    def __str__(self) -> str:
        return f"{self.capture_session}-v{self.visit:02d}-p{self.angle}"

    @classmethod
    def parse(cls, text: str) -> PhotoName:
        match = _PHOTO.fullmatch(text)
        if not match:
            raise SheetError(f"not a Photo name: {text!r}; they read s01-v07-p2")
        return cls(match[1], int(match[2]), int(match[3]))


@dataclass(frozen=True)
class OpenMismatch:
    photo: PhotoName
    reason: str


@dataclass(frozen=True)
class Sheet:
    capture_session: str
    phone: str
    light: Light
    held_out: bool
    date: dt.date
    visits: tuple[Visit, ...]
    mismatches: tuple[OpenMismatch, ...]
    ingested: bool

    def photo_names(self) -> list[PhotoName]:
        return [PhotoName(self.capture_session, v.number, a) for v in self.visits for a in ANGLES]

    def visit(self, number: int) -> Visit:
        return self.visits[number - 1]

    def open_mismatch(self, photo: PhotoName) -> OpenMismatch | None:
        return next((m for m in self.mismatches if m.photo == photo), None)


def load_sheet(path: Path) -> Sheet:
    if not path.exists():
        raise SheetError(f"no sheet at {path}; type it up from the notes taken at the Board")
    name = capture_session(path.stem)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        return _sheet(name, raw)
    except tomllib.TOMLDecodeError as error:
        raise SheetError(f"{path}: {error}") from None
    except KeyError as error:
        raise SheetError(f"{path}: missing {error}") from None
    except (TypeError, ValueError) as error:
        raise SheetError(f"{path}: {error}") from None


def _sheet(name: str, raw: dict) -> Sheet:
    if raw["set"] not in ("training", "held-out"):
        raise SheetError(f"set is training or held-out, not {raw['set']!r}")
    if not isinstance(raw["date"], dt.date):
        raise SheetError("date is a TOML date, such as 2026-11-14")
    visits = tuple(
        Visit(number, tuple(RecordedDart.parse(text) for text in visit["darts"]))
        for number, visit in enumerate(raw["visits"], start=1)
    )
    if not visits:
        raise SheetError("the sheet has no Visits")
    mismatches = tuple(
        OpenMismatch(PhotoName.parse(m["photo"]), str(m["reason"]))
        for m in raw.get("mismatches", [])
    )
    return Sheet(
        capture_session=name,
        phone=str(raw["phone"]),
        light=Light(raw["light"]),
        held_out=raw["set"] == "held-out",
        date=raw["date"],
        visits=visits,
        mismatches=mismatches,
        ingested="ingest" in raw,
    )
