from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import DartsMlError

DEFAULT_DATA = "~/darts-scorer-data"
_CAPTURE_SESSION = re.compile(r"s\d{2,3}")


class Round(Enum):
    A = "a"
    B = "b"
    C = "c"


class DataInsideRepo(DartsMlError):
    pass


def repo_roots() -> set[Path]:
    roots = set()
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        root = next((d for d in (start, *start.parents) if (d / ".git").exists()), None)
        if root is not None:
            roots.add(root)
    return roots


def data_root(environ=os.environ) -> Path:
    resolved = Path(environ.get("DARTS_DATA") or DEFAULT_DATA).expanduser().resolve()
    for root in repo_roots():
        if resolved == root or root in resolved.parents:
            raise DataInsideRepo(
                f"DARTS_DATA resolves to {resolved}, inside the repository at {root}.\n"
                "Photos, labels and weights never enter git (ADR-0008), and the .gitignore alone "
                "would let a .toml sheet through.\n"
                f"Point DARTS_DATA at a directory outside the repository, such as {DEFAULT_DATA}."
            )
    return resolved


def capture_session(name: str) -> str:
    if not _CAPTURE_SESSION.fullmatch(name):
        raise DartsMlError(f"not a Capture session name: {name!r}; they run s01, s02, …")
    return name


@dataclass(frozen=True)
class DataDir:
    root: Path

    @classmethod
    def from_environment(cls) -> DataDir:
        return cls(data_root())

    def inbox(self, name: str) -> Path:
        return self.root / "inbox" / capture_session(name)

    def photos(self, name: str) -> Path:
        return self.root / "photos" / capture_session(name)

    def photo(self, name: str, photo: str) -> Path:
        return self.photos(name) / f"{photo}.jpg"

    def labels(self, name: str, round_: Round = Round.A) -> Path:
        if round_ is Round.A:
            return self.root / "labels" / capture_session(name)
        return self.root / "rounds" / capture_session(name) / round_.value

    def sheets(self) -> Path:
        return self.root / "capture-sessions"

    def sheet(self, name: str) -> Path:
        return self.sheets() / f"{capture_session(name)}.toml"

    def overlays(self, name: str, round_: Round = Round.A) -> Path:
        base = self.root / "overlays" / capture_session(name)
        return base if round_ is Round.A else base / round_.value
