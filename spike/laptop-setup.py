#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["rich>=13.9"]
# ///
"""Sets up a second machine for Darts Scorer's M2 work: code, Python envs, DeepDarts, a GPU check."""

import hashlib
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TimeRemainingColumn, TransferSpeedColumn
from rich.prompt import Prompt
from rich.table import Table

os.environ.update(GIT_PAGER="cat", PAGER="cat", GH_PAGER="cat")

REPO = "maks-sredniawa/darts-scorer"
CLONE = Path.home() / "repos" / "maks-sredniawa" / "darts-scorer"
BRANCH = "spike/m2-toolchain"
WORKTREE = CLONE / ".worktrees" / "m2-spike"
DATAPORT = "https://ieee-dataport.org/open-access/deepdarts-dataset"
DEEPDARTS_FILES = {"labels_pkl.zip": 339.84e3, "cropped_images.zip": 3.35e9}
LOG = Path.home() / f"darts-laptop-setup-{datetime.now():%Y%m%d-%H%M}.log"

console = Console(record=True)


def data_dir() -> Path:
    return Path(os.environ.get("DARTS_DATA", "~/darts-scorer-data")).expanduser().resolve()


def save_log() -> None:
    console.save_text(str(LOG), clear=False)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]" + (f"  [dim](in {cwd})[/dim]" if cwd else ""))
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        console.print(line.rstrip("\n"), markup=False, highlight=False)
    code = proc.wait()
    if code and check:
        console.print(f"[red]failed with exit code {code}[/red]")
    save_log()
    return code


def output(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def confirm(phrase: str) -> bool:
    answer = Prompt.ask(f"Type [bold]{phrase}[/bold] to go on, anything else to skip")
    return answer.strip() == phrase


def step_check() -> bool:
    console.rule("[bold]1. Check this machine")
    table = Table("What", "Found", "Fix if missing")
    ok = True

    def row(name, value, fix, required=True):
        nonlocal ok
        if value is None and required:
            ok = False
        table.add_row(name, value or ("[red]missing[/red]" if required else "[yellow]missing[/yellow]"), "" if value else fix)

    row("uv", output(["uv", "--version"]), "curl -LsSf https://astral.sh/uv/install.sh | sh")
    row("git", output(["git", "--version"]), "sudo apt install git")
    gh = output(["gh", "--version"])
    row("gh", gh.splitlines()[0] if gh else None, "sudo apt install gh, then gh auth login")
    gpu = output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    row("NVIDIA GPU", gpu, "no CUDA GPU: training would run on the CPU, far slower")
    row("jpegtran", "yes" if shutil.which("jpegtran") else None, "sudo apt install libjpeg-turbo-progs")
    home_free = shutil.disk_usage(Path.home()).free / 1e9
    row("free disk in ~", f"{home_free:.0f} GB" if home_free >= 15 else None, "DeepDarts needs ~7 GB zipped + unzipped, training more")
    row("Android SDK (optional)", os.environ.get("ANDROID_HOME"), "only for the on-device test", required=False)
    console.print(table)
    console.print("[green]Ready for the next steps.[/green]" if ok else "[red]Fix the red rows, then run step 1 again.[/red]")
    save_log()
    return ok


def step_code() -> bool:
    console.rule("[bold]2. Get the code")
    if not (CLONE / ".git").exists():
        CLONE.parent.mkdir(parents=True, exist_ok=True)
        if run(["git", "clone", f"https://github.com/{REPO}.git", str(CLONE)]):
            return False
    else:
        console.print(f"Clone found at {CLONE}")
    if run(["git", "fetch", "--prune", "origin"], cwd=CLONE):
        return False
    common = Path(output(["git", "-C", str(CLONE), "rev-parse", "--path-format=absolute", "--git-common-dir"]))
    exclude = common / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    lines = exclude.read_text().splitlines() if exclude.exists() else []
    for entry in (".worktrees/", "app/src/androidTest/assets/m2spike/"):
        if entry not in lines:
            with exclude.open("a") as f:
                f.write(entry + "\n")
            console.print(f"added {entry} to {exclude}")
    if WORKTREE.exists():
        return run(["git", "pull", "--ff-only"], cwd=WORKTREE) == 0
    local = output(["git", "-C", str(CLONE), "branch", "--list", BRANCH])
    cmd = ["git", "worktree", "add", str(WORKTREE), BRANCH] if local else ["git", "worktree", "add", "--track", "-b", BRANCH, str(WORKTREE), f"origin/{BRANCH}"]
    return run(cmd, cwd=CLONE) == 0


def step_envs() -> bool:
    console.rule("[bold]3. Python environments")
    if not WORKTREE.exists():
        console.print("[red]Run step 2 first.[/red]")
        return False
    ok = run(["uv", "sync"], cwd=WORKTREE / "ml") == 0
    ok &= run(["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"], cwd=WORKTREE / "ml") == 0
    console.print("[dim]The spike env downloads PyTorch with CUDA, a few GB: this takes a while.[/dim]")
    ok &= run(["uv", "sync"], cwd=WORKTREE / "spike") == 0
    ok &= run(["uv", "run", "python", "-c", "import torch; print('torch', torch.__version__, '| CUDA', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no GPU')"], cwd=WORKTREE / "spike") == 0
    return ok


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Progress("[progress.description]{task.description}", BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(), console=console) as bar:
        task = bar.add_task(f"SHA-256 {path.name}", total=path.stat().st_size)
        with path.open("rb") as f:
            while chunk := f.read(8 << 20):
                digest.update(chunk)
                bar.advance(task, len(chunk))
    return digest.hexdigest()


def unzip(archive: Path, into: Path) -> None:
    with zipfile.ZipFile(archive) as z, Progress("[progress.description]{task.description}", BarColumn(), DownloadColumn(), TimeRemainingColumn(), console=console) as bar:
        members = z.infolist()
        task = bar.add_task(f"unzip {archive.name}", total=sum(m.file_size for m in members))
        for m in members:
            target = (into / m.filename).resolve()
            if into.resolve() not in target.parents and target != into.resolve():
                raise SystemExit(f"refusing {m.filename}: it would land outside {into}")
            z.extract(m, into)
            bar.advance(task, m.file_size)


def step_deepdarts() -> bool:
    console.rule("[bold]4. DeepDarts into DARTS_DATA")
    data = data_dir()
    if CLONE.resolve() in (data, *data.parents):
        console.print(f"[red]DARTS_DATA {data} is inside the repo. Point it outside (ADR-0008).[/red]")
        return False
    target = data / "deepdarts"
    target.mkdir(parents=True, exist_ok=True)
    console.print(f"DARTS_DATA is [bold]{data}[/bold]")
    downloads = Path.home() / "Downloads"
    found = {name: next((p for p in (target / name, downloads / name) if p.exists()), None) for name in DEEPDARTS_FILES}
    missing = [n for n, p in found.items() if p is None]
    if missing:
        console.print(Panel(
            f"Log in at {DATAPORT}\n(free IEEE account), then download into {downloads}:\n\n" + "\n".join(f"  • {n}" for n in missing) +
            "\n\nNot models.zip: it is not used (docs/phase-M1.md §4).", title="Download in your browser"))
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", DATAPORT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not confirm("downloaded"):
            return False
        found = {name: next((p for p in (target / name, downloads / name) if p.exists()), None) for name in DEEPDARTS_FILES}
        still = [n for n, p in found.items() if p is None]
        if still:
            console.print(f"[red]Still not found in {downloads} or {target}: {', '.join(still)}[/red]")
            return False
    table = Table("File", "Where", "Size", "Expected")
    for name, path in found.items():
        size = path.stat().st_size
        table.add_row(name, str(path.parent), f"{size / 1e6:,.1f} MB", f"~{DEEPDARTS_FILES[name] / 1e6:,.1f} MB")
    console.print(table)
    for name, path in found.items():
        if abs(path.stat().st_size - DEEPDARTS_FILES[name]) > 0.05 * DEEPDARTS_FILES[name]:
            console.print(f"[red]{name} is not the expected size: a partial download? Delete it and download again.[/red]")
            return False
    to_move = {n: p for n, p in found.items() if p.parent != target}
    if to_move:
        console.print(f"Moving {', '.join(to_move)} into {target}")
        if not confirm("move them"):
            return False
        for name, path in to_move.items():
            shutil.move(str(path), target / name)
    sums = {name: sha256(target / name) for name in DEEPDARTS_FILES}
    (target / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in sums.items()))
    for n, h in sums.items():
        console.print(f"{h}  {n}")
    console.print(f"[green]Wrote {target / 'SHA256SUMS'}[/green] — checkpoint C records these in R2.")
    if not (target / "labels").exists():
        unzip(target / "labels_pkl.zip", target / "labels")
    console.print("labels/: " + ", ".join(sorted(p.name for p in (target / "labels").rglob("*") if p.is_file())[:10]))
    if not (target / "cropped_images").exists():
        console.print("Unzipping the images takes a few minutes and ~3.4 GB more.")
        if confirm("unzip images"):
            unzip(target / "cropped_images.zip", target)
    save_log()
    return True


def step_smoke() -> bool:
    console.rule("[bold]5. GPU smoke training (2 minutes, synthetic boards)")
    if not WORKTREE.exists():
        console.print("[red]Run steps 2 and 3 first.[/red]")
        return False
    out = data_dir() / "runs" / f"laptop-smoke-{datetime.now():%Y%m%d-%H%M}"
    console.print(f"Weights and eval go to {out}, outside the repo.")
    ok = run(["uv", "run", "python", "-m", "m2_spike.train", "--minutes", "2", "--eval-images", "100", "--out", str(out)], cwd=WORKTREE / "spike") == 0
    console.print("Compare img_s and the eval with spike/RESULTS.md's 3-minute row from the desktop (~100 img/s on an RTX 3070, 20 cores).")
    return ok


STEPS = {"1": ("Check this machine", step_check), "2": ("Get the code", step_code), "3": ("Python environments", step_envs),
         "4": ("DeepDarts into DARTS_DATA", step_deepdarts), "5": ("GPU smoke training", step_smoke)}


def main() -> None:
    console.print(Panel(f"Darts Scorer — second machine for M2\nclone {CLONE}\nbranch {BRANCH} in {WORKTREE}\nDARTS_DATA {data_dir()}\nlog {LOG}", title="laptop-setup", expand=False))
    while True:
        menu = Table("#", "Step", show_header=False, box=None)
        for key, (title, _) in STEPS.items():
            menu.add_row(key, title)
        menu.add_row("a", "all, in order, stopping at the first failure")
        menu.add_row("q", "quit")
        console.print(menu)
        choice = Prompt.ask("Step", choices=[*STEPS, "a", "q"], default="a")
        if choice == "q":
            break
        if choice == "a":
            for key, (title, fn) in STEPS.items():
                start = time.time()
                if not fn():
                    console.print(f"[red]Stopped at step {key}, {title}.[/red]")
                    break
                console.print(f"[green]step {key} done in {time.time() - start:.0f} s[/green]")
        else:
            STEPS[choice][1]()
        save_log()
    save_log()
    console.print(f"Log saved to {LOG}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        save_log()
        sys.exit(f"\ninterrupted; log saved to {LOG}")
