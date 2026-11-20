"""The debug build's marked Visits, copied off a phone into DARTS_DATA (phase-1.md §4, what moved while building C)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from . import DartsMlError

PACKAGE = "com.maksforge.dartsscorer.debug"
REMOTE = "files/marked"
KEPT = (".jpg", ".json")
# run-as starts in the app's data directory; the glob has to expand there, as the app's user.
_LIST = f'cd {REMOTE} 2>/dev/null || exit 0; for f in *; do [ -f "$f" ] && stat -c "%n %s %Y" "$f"; done; true'


@dataclass(frozen=True)
class Remote:
    name: str
    size: int
    mtime: int


def parse_listing(text: str) -> list[Remote]:
    remotes = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0].endswith(KEPT) and fields[1].isdigit() and fields[2].isdigit():
            remotes.append(Remote(fields[0], int(fields[1]), int(fields[2])))
    return sorted(remotes, key=lambda r: r.name)


class Phone:
    def __init__(self, serial: str, package: str = PACKAGE, run: Callable = subprocess.run) -> None:
        self.serial = serial
        self.package = package
        self._run = run

    def _adb(self, *args: str) -> bytes:
        done = self._run(["adb", "-s", self.serial, *args], capture_output=True)
        if done.returncode != 0:
            message = (done.stderr or done.stdout).decode(errors="replace").strip()
            raise DartsMlError(f"adb {' '.join(args)} failed: {message}")
        return done.stdout

    def listing(self) -> list[Remote]:
        out = self._adb("shell", f"run-as {self.package} sh -c '{_LIST}'").decode(errors="replace")
        if "run-as:" in out:
            raise DartsMlError(f"listing {REMOTE} failed: {out.strip()}")
        return parse_listing(out)

    def read(self, name: str) -> bytes:
        return self._adb("exec-out", "run-as", self.package, "cat", f"{REMOTE}/{name}")

    def delete(self, name: str) -> None:
        self._adb("shell", f"run-as {self.package} rm {REMOTE}/{name}")


def local_copies(captures: Path) -> dict[str, Path]:
    if not captures.is_dir():
        return {}
    return {p.name: p for p in captures.glob("*/*") if p.is_file() and p.name.endswith(KEPT)}


def unchanged(remote: Remote, local: Path | None) -> bool:
    if local is None:
        return False
    stat = local.stat()
    return stat.st_size == remote.size and int(stat.st_mtime) == remote.mtime


def to_copy(remotes: Iterable[Remote], copies: dict[str, Path], new_dir: Path) -> list[tuple[Remote, Path]]:
    """A record kept again on the phone replaces its earlier copy where that lies, beside its Photo."""
    return [(r, copies.get(r.name, new_dir / r.name)) for r in remotes if not unchanged(r, copies.get(r.name))]


def pull(phone: Phone, captures: Path, day: str, log: Callable[[str], None], delete_after: bool = False) -> int:
    remotes = phone.listing()
    todo = to_copy(remotes, local_copies(captures), captures / day)
    log(f"{len(remotes)} on the phone, {len(remotes) - len(todo)} here unchanged, {len(todo)} to copy")
    for i, (remote, target) in enumerate(todo, 1):
        log(f"[{i}/{len(todo)}] {remote.name} -> {target.parent.name}/")
        data = phone.read(remote.name)
        if len(data) != remote.size:
            raise DartsMlError(f"{remote.name}: got {len(data)} bytes, the phone listed {remote.size}; "
                               "was it kept again during the pull? Run it again")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        part.write_bytes(data)
        os.utime(part, (remote.mtime, remote.mtime))
        part.replace(target)
    if delete_after:
        here = local_copies(captures)
        gone = [r for r in phone.listing() if unchanged(r, here.get(r.name))]
        for i, remote in enumerate(gone, 1):
            log(f"[{i}/{len(gone)}] deleting {remote.name} on the phone")
            phone.delete(remote.name)
    return len(todo)
