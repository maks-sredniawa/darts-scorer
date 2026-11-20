#!/usr/bin/env python3
"""Copy the debug build's marked Visits off a phone into $DARTS_DATA/phone-captures/<date>/.

    python3 scripts/pull-marked.py --serial <adb serial> [--delete-after]

Each marked Visit is a Photo and its JSON, kept in the app's `files/marked/` when a Visit with a
result ends (`ui/visit/KeepMarked.kt`, debug only). Files already under any `phone-captures/` date
are skipped. Nothing on the phone is deleted unless --delete-after is given, and then only files
that are now on this computer.
"""

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

PACKAGE = "com.maksforge.dartsscorer.debug"
REMOTE = "files/marked"
DEFAULT_DATA = "~/darts-scorer-data"
KEPT = (".jpg", ".json")


def repo_roots():
    here = Path(__file__).resolve().parent
    roots = {here.parent}
    listed = subprocess.run(
        ["git", "-C", str(here), "worktree", "list", "--porcelain"], capture_output=True, text=True
    )
    if listed.returncode == 0:
        roots |= {Path(line[len("worktree "):]).resolve() for line in listed.stdout.splitlines() if line.startswith("worktree ")}
    return roots


def data_root(environ, roots):
    path = Path(environ.get("DARTS_DATA") or DEFAULT_DATA).expanduser().resolve()
    for root in roots:
        if path == root or root in path.parents:
            raise SystemExit(f"DARTS_DATA resolves to {path}, inside the repository at {root}; point it outside")
    return path


def marked_names(listing):
    return sorted(name for name in listing.split() if name.endswith(KEPT))


def already_pulled(captures):
    return {path.name for path in captures.glob("*/*") if path.is_file()} if captures.is_dir() else set()


def to_pull(names, pulled):
    return [name for name in names if name not in pulled]


def adb(serial, *args, check=True):
    result = subprocess.run(["adb", "-s", serial, *args], capture_output=True)
    if check and result.returncode != 0:
        raise SystemExit(f"adb {' '.join(args)} failed: {(result.stderr or result.stdout).decode(errors='replace').strip()}")
    return result


def list_remote(serial, package):
    result = adb(serial, "exec-out", "run-as", package, "ls", REMOTE, check=False)
    output = (result.stdout + result.stderr).decode(errors="replace")
    if "No such file" in output:
        return []
    if result.returncode != 0 or "run-as:" in output:
        raise SystemExit(f"listing {REMOTE} failed: {output.strip()}")
    return marked_names(output)


def pull(serial, package, name, target):
    data = adb(serial, "exec-out", "run-as", package, "cat", f"{REMOTE}/{name}").stdout
    size = adb(serial, "exec-out", "run-as", package, "stat", "-c", "%s", f"{REMOTE}/{name}").stdout.decode().strip()
    if size != str(len(data)):
        raise SystemExit(f"{name}: got {len(data)} bytes, the phone has {size!r}")
    part = target.with_name(target.name + ".part")
    part.write_bytes(data)
    part.replace(target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serial", required=True, help="the adb serial of the phone to pull from")
    parser.add_argument("--package", default=PACKAGE, help=f"the debug build's applicationId (default {PACKAGE})")
    parser.add_argument("--delete-after", action="store_true", help="delete each file on the phone once it is here")
    args = parser.parse_args(argv)

    captures = data_root(os.environ, repo_roots()) / "phone-captures"
    names = list_remote(args.serial, args.package)
    pulled = already_pulled(captures)
    todo = to_pull(names, pulled)
    target_dir = captures / date.today().isoformat()
    print(f"{len(names)} on the phone, {len(names) - len(todo)} already pulled, {len(todo)} to copy into {target_dir}", file=sys.stderr)
    if todo:
        target_dir.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name}", file=sys.stderr)
        pull(args.serial, args.package, name, target_dir / name)
    if args.delete_after:
        here = already_pulled(captures)
        gone = [name for name in names if name in here]
        for i, name in enumerate(gone, 1):
            print(f"[{i}/{len(gone)}] deleting {name} on the phone", file=sys.stderr)
            adb(args.serial, "shell", "run-as", args.package, "rm", f"{REMOTE}/{name}")
    print(f"done: {len(todo)} copied", file=sys.stderr)


if __name__ == "__main__":
    main()
