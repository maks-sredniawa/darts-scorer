from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
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


def repo_roots(starts=None) -> set[Path]:
    roots = set()
    for start in starts or (Path(__file__).resolve(), Path.cwd().resolve()):
        top = next((d for d in (start, *start.parents) if (d / ".git").exists()), None)
        if top is not None:
            roots |= {top, *_worktrees(_common_dir(top))}
    return roots


def _common_dir(top: Path) -> Path:
    git = top / ".git"
    if git.is_dir():
        return git.resolve()
    own = (top / git.read_text(encoding="utf-8").removeprefix("gitdir:").strip()).resolve()
    common = own / "commondir"
    return (own / common.read_text(encoding="utf-8").strip()).resolve() if common.is_file() else own


def _worktrees(common: Path) -> set[Path]:
    linked = (common / "worktrees").glob("*/gitdir")
    return {common.parent, *(Path(g.read_text(encoding="utf-8").strip()).resolve().parent for g in linked)}


def refuse_inside_repo(path: Path, roots, what: str) -> Path:
    resolved = path.expanduser().resolve()
    for root in roots:
        if resolved == root or root in resolved.parents:
            raise DataInsideRepo(
                f"{what} resolves to {resolved}, inside the repository at {root}.\n"
                "Photos, labels and weights never enter git (ADR-0008), and the .gitignore alone "
                "would let a .toml sheet through.\n"
                f"Point DARTS_DATA at a directory outside the repository, such as {DEFAULT_DATA}, "
                "with no symlink under it leading back in."
            )
    return resolved


def data_root(environ=os.environ, roots=None) -> Path:
    path = Path(environ.get("DARTS_DATA") or DEFAULT_DATA)
    return refuse_inside_repo(path, repo_roots() if roots is None else roots, "DARTS_DATA")


def capture_session(name: str) -> str:
    if not _CAPTURE_SESSION.fullmatch(name):
        raise DartsMlError(f"not a Capture session name: {name!r}; they run s01, s02, …")
    return name


@dataclass(frozen=True)
class DataDir:
    root: Path
    roots: frozenset[Path] = field(default_factory=lambda: frozenset(repo_roots()), compare=False, repr=False)

    @classmethod
    def from_environment(cls) -> DataDir:
        roots = frozenset(repo_roots())
        return cls(data_root(roots=roots), roots)

    def inbox(self, name: str) -> Path:
        return self._fenced(self.root / "inbox" / capture_session(name))

    def photos(self, name: str) -> Path:
        return self._fenced(self.root / "photos" / capture_session(name))

    def photo(self, name: str, photo: str) -> Path:
        return self._fenced(self.photos(name) / f"{photo}.jpg")

    def labels(self, name: str, round_: Round = Round.A) -> Path:
        if round_ is Round.A:
            return self._fenced(self.root / "labels" / capture_session(name))
        return self._fenced(self.root / "rounds" / capture_session(name) / round_.value)

    def sheets(self) -> Path:
        return self._fenced(self.root / "capture-sessions")

    def sheet(self, name: str) -> Path:
        return self._fenced(self.sheets() / f"{capture_session(name)}.toml")

    def overlays(self, name: str, round_: Round = Round.A) -> Path:
        base = self.root / "overlays" / capture_session(name)
        return self._fenced(base if round_ is Round.A else base / round_.value)

    def build(self) -> Path:
        return self._fenced(self.root / "build")

    def _fenced(self, path: Path) -> Path:
        refuse_inside_repo(path, self.roots, f"{path.relative_to(self.root)} under DARTS_DATA")
        return path
