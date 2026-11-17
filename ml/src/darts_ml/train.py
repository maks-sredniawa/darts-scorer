from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch.nn import functional as F

from . import DartsMlError
from .locate import Inference, Speed, figures, locate
from .model import CALIBRATION_OFFSETS, ENTRY_CHANNEL, ENTRY_OFFSETS, HEATMAPS, KeypointNet
from .paths import DataDir
from .training_data import KeypointDataset, deepdarts_samples

FOCAL_ALPHA = 2.0
FOCAL_BETA = 4.0
OFFSET_WEIGHT = 1.0
WARMUP = 10
_RUN_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def loss_terms(output: torch.Tensor, heatmaps, weights, calibration_offsets, calibration_mask, entry_offsets,
               entry_mask, entries: bool = True) -> tuple[torch.Tensor, torch.Tensor]:
    if not entries:
        weights = weights.clone()
        weights[:, ENTRY_CHANNEL] = 0
    predicted = torch.sigmoid(output[:, :HEATMAPS].float()).clamp(1e-4, 1 - 1e-4)
    positive = heatmaps.eq(1).float()
    positive_loss = torch.log(predicted) * (1 - predicted) ** FOCAL_ALPHA * positive
    negative_loss = torch.log(1 - predicted) * predicted**FOCAL_ALPHA * (1 - heatmaps) ** FOCAL_BETA * (1 - positive)
    per_channel = (positive_loss + negative_loss).sum(dim=(2, 3)) * weights
    counted = (positive.sum(dim=(2, 3)) * weights.gt(0)).sum()
    heatmap_loss = -per_channel.sum() / counted.clamp(min=1)
    offset_loss = _offset_loss(output[:, CALIBRATION_OFFSETS], calibration_offsets, calibration_mask)
    if entries:
        offset_loss = offset_loss + _offset_loss(output[:, ENTRY_OFFSETS], entry_offsets, entry_mask)
    return heatmap_loss, offset_loss


def _offset_loss(predicted: torch.Tensor, offsets: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    error = F.l1_loss(predicted.float(), offsets, reduction="none").sum(dim=1) * mask
    return error.sum() / mask.sum().clamp(min=1)


def use_tuned_kernels(data: DataDir) -> None:
    # MIOpen ships no tuned kernels for gfx1151; its user database, filled once by a run under
    # MIOPEN_FIND_ENFORCE=SEARCH, makes later runs about 12% faster (phase-M2.md §1).
    os.environ.setdefault("MIOPEN_USER_DB_PATH", str(data.miopen()))
    os.environ.setdefault("MIOPEN_CUSTOM_CACHE_DIR", str(data.miopen() / "cache"))


def resolve_device(choice: str) -> tuple[str, str]:
    gpu = torch.cuda.is_available()
    if choice == "gpu" and not gpu:
        raise DartsMlError("PyTorch sees no GPU; install the ROCm (AMD) or CUDA (NVIDIA) build of PyTorch, or pass --device cpu")
    if choice == "cpu" or not gpu:
        return "cpu", f"CPU, {torch.get_num_threads()} threads"
    backend = f"ROCm {torch.version.hip}" if torch.version.hip else f"CUDA {torch.version.cuda}"
    return "cuda", f"{torch.cuda.get_device_name(0)} ({backend})"


def _step(model, optimiser, batch, device: str, speed: Speed, entries: bool = True) -> tuple[float, float, float]:
    image, *rest = (t.to(device, non_blocking=True) for t in batch)
    with speed.autocast(device):
        output = model(image.contiguous(memory_format=speed.memory))
    heatmap_loss, offset_loss = loss_terms(output, *rest, entries=entries)
    loss = heatmap_loss + OFFSET_WEIGHT * offset_loss
    optimiser.zero_grad(set_to_none=True)
    loss.backward()
    optimiser.step()
    return float(loss.detach()), float(heatmap_loss.detach()), float(offset_loss.detach())


def _model(device: str, speed: Speed) -> torch.nn.Module:
    return KeypointNet().to(device, memory_format=speed.memory)


@dataclass
class Probe:
    device: str
    hardware: str
    size: int
    batch: int
    steps: int
    images_per_second: float
    epoch_minutes: float
    training_photos: int
    losses: list[float]
    bf16: bool = False
    channels_last: bool = False
    commit: str = ""
    miopen: dict[str, str] | None = None


def probe(data: DataDir, choice: str, steps: int = 200, size: int = 512, batch: int = 16, workers: int = 8,
          seed: int = 0, speed: Speed = Speed()) -> Probe:
    if steps <= WARMUP:
        raise DartsMlError(f"--steps {steps} leaves nothing to time after the {WARMUP} warm-up steps; pass more than {WARMUP}")
    device, hardware = resolve_device(choice)
    speed.check(device)
    torch.manual_seed(seed)
    samples = deepdarts_samples(data, "train")
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(KeypointDataset(samples, size), batch_size=batch, shuffle=True,
                                         generator=generator, num_workers=workers, drop_last=True,
                                         persistent_workers=workers > 0)
    if steps > len(loader):
        raise DartsMlError(f"--steps {steps} is more than one epoch, {len(loader)} batches of {batch} from "
                           f"{len(samples)} Photos; pass at most {len(loader)}")
    use_tuned_kernels(data)
    model = _model(device, speed)
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    model.train()
    losses = []
    started = None
    batches = iter(loader)
    for step in range(steps):
        if step == WARMUP:
            _sync(device)
            started = time.perf_counter()
        losses.append(_step(model, optimiser, next(batches), device, speed)[0])
    _sync(device)
    rate = (steps - WARMUP) * batch / (time.perf_counter() - started)
    miopen = {k: v for k, v in sorted(os.environ.items()) if k.startswith("MIOPEN_")}
    return Probe(device, hardware, size, batch, steps, rate, len(samples) / rate / 60, len(samples), losses,
                 speed.bf16, speed.channels_last, commit(), miopen)


def probe_path(data: DataDir, result: Probe, now: dt.datetime) -> Path:
    device = "gpu" if result.device == "cuda" else result.device
    speed = Speed(result.bf16, result.channels_last).suffix()
    return data.runs() / "probes" / f"{device}-{result.size}-{result.batch}-{result.steps}steps{speed}-{now:%Y%m%d-%H%M%S}.json"


def _sync(device: str) -> None:
    if device.startswith("cuda"):
        torch.cuda.synchronize()


def save(result: Probe, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(asdict(result), indent=1))


def commit() -> str:
    here = Path(__file__).parent

    def git(*argv: str) -> str:
        return subprocess.run(["git", "-C", str(here), *argv], capture_output=True, text=True, check=True).stdout.strip()

    try:
        head = git("rev-parse", "--short", "HEAD")
        return head + ("-dirty" if git("status", "--porcelain", "--", str(here.parents[1])) else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


@dataclass(frozen=True)
class RunConfig:
    name: str
    device: str = "auto"
    epochs: int = 30
    size: int = 512
    batch: int = 16
    lr: float = 1e-3
    weight_decay: float = 1e-4
    warmup_steps: int = 500
    workers: int = 8
    seed: int = 0
    augment: bool = True
    board_only: bool = False
    bf16: bool = False
    channels_last: bool = False
    init: str | None = None

    @property
    def speed(self) -> Speed:
        return Speed(self.bf16, self.channels_last)


def run_folder(data: DataDir, name: str, today: dt.date) -> Path:
    if not _RUN_NAME.fullmatch(name):
        raise DartsMlError(f"--name {name!r}: lower-case letters, digits and hyphens, such as board-512")
    return data.runs() / f"{today:%Y-%m-%d}-{name}"


def load_weights(path: Path, device: str) -> torch.nn.Module:
    if not path.exists():
        raise DartsMlError(f"no weights at {path}")
    model = KeypointNet()
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True)["model"])
    return model.to(device)


def train(data: DataDir, config: RunConfig, today: dt.date | None = None, log=None) -> Path:
    log = log or sys.stderr
    folder = run_folder(data, config.name, today or dt.date.today())
    if folder.exists():
        raise DartsMlError(f"{folder} exists; a run is never overwritten, so give this one another --name")
    use_tuned_kernels(data)
    device, hardware = resolve_device(config.device)
    config.speed.check(device)
    torch.manual_seed(config.seed)
    training = deepdarts_samples(data, "train")
    validation = deepdarts_samples(data, "val")
    loader = torch.utils.data.DataLoader(
        KeypointDataset(training, config.size, augment=config.augment), batch_size=config.batch, shuffle=True,
        generator=torch.Generator().manual_seed(config.seed), num_workers=config.workers, drop_last=True,
        persistent_workers=config.workers > 0)
    if not len(loader):
        raise DartsMlError(f"{len(training)} training Photos make no batch of {config.batch}")
    if config.init:
        model = load_weights(data.runs() / config.init / "best.pt", device).to(memory_format=config.speed.memory)
    else:
        model = _model(device, config.speed)
    optimiser = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    total = config.epochs * len(loader)
    schedule = torch.optim.lr_scheduler.LambdaLR(optimiser, lambda step: _rate(step, config.warmup_steps, total))
    inference = Inference(model, device, config.size, config.batch, config.workers, config.speed)

    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({
        **asdict(config), "device_used": device, "hardware": hardware, "commit": commit(),
        "torch": torch.__version__, "training_photos": len(training), "validation_photos": len(validation),
        "validation": "DeepDarts val", "started": dt.datetime.now().isoformat(timespec="seconds"),
    }, indent=1), encoding="utf-8")
    best = None
    step = 0
    with (folder / "losses.jsonl").open("w", encoding="utf-8") as losses, \
         (folder / "epochs.jsonl").open("w", encoding="utf-8") as epochs:
        for epoch in range(1, config.epochs + 1):
            started = time.perf_counter()
            model.train()
            running = []
            for batch in loader:
                loss, heatmap, offset = _step(model, optimiser, batch, device, config.speed, not config.board_only)
                schedule.step()
                step += 1
                running.append(loss)
                losses.write(json.dumps({"step": step, "epoch": epoch, "loss": loss, "heatmap": heatmap,
                                         "offset": offset, "lr": schedule.get_last_lr()[0]}) + "\n")
                if step % 100 == 0:
                    losses.flush()
                    print(f"[epoch {epoch}/{config.epochs}] step {step}/{total} loss {loss:.4f}", file=log, flush=True)
            trained = time.perf_counter() - started
            print(f"[epoch {epoch}/{config.epochs}] validating on {len(validation)} DeepDarts val Photos ...",
                  file=log, flush=True)
            reading = figures(validation, locate(inference, [s.photo for s in validation]))
            key = reading.key(config.board_only)
            chosen = best is None or key > best[1]
            _save_weights(model, epoch, folder / "last.pt")
            if chosen:
                best = (epoch, key)
                _save_weights(model, epoch, folder / "best.pt")
            epochs.write(json.dumps({"epoch": epoch, "mean_loss": sum(running) / len(running),
                                     "train_seconds": trained, "validate_seconds": time.perf_counter() - started - trained,
                                     "best": chosen, "figures": reading.as_dict()}) + "\n")
            epochs.flush()
            for line in reading.lines():
                print(f"[epoch {epoch}/{config.epochs}] {line}", file=log, flush=True)
    return folder


def _rate(step: int, warmup: int, total: int) -> float:
    if step < warmup:
        return (step + 1) / warmup
    return 0.5 * (1 + math.cos(math.pi * min(1.0, (step - warmup) / max(1, total - warmup))))


def _save_weights(model: torch.nn.Module, epoch: int, path: Path) -> None:
    temporary = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "epoch": epoch}, temporary)
    temporary.replace(path)
