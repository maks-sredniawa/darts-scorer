from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import time
from collections.abc import Collection
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch.nn import functional as F

from . import DartsMlError
from .locate import Inference, Speed, figures, locate
from .model import (BOARD_OFFSETS, CALIBRATION_CHANNELS, ENTRY_HEAT, ENTRY_OFFSETS, ENTRY_STRIDE, Heads,
                    KeypointNet, load_matching, stride_of_weights)
from .paths import DataDir
from .renders import MANIFEST as RENDER_MANIFEST
from .training_data import (PUBLIC_MANIFEST, RING_INNER_MM, RING_OUTER_MM, KeypointDataset, Sample, Targets,
                            deepdarts_samples, public_samples, public_split, render_samples, render_split)

FOCAL_ALPHA = 2.0
FOCAL_BETA = 4.0
OFFSET_WEIGHT = 1.0
RING_WEIGHT = 4.0
WARMUP = 10
RENDER_WEIGHT = 0.5
PUBLIC_WEIGHT = 0.3
_PUBLIC_PROVENANCE = ("title", "author", "url", "licence", "licence_url", "mirror", "records", "credit")
_RUN_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def loss_terms(heads: Heads, target: Targets, entries: bool = True,
               ring_weight: float = RING_WEIGHT) -> tuple[torch.Tensor, torch.Tensor]:
    positive, negative, counted = _focal(heads.board[:, :CALIBRATION_CHANNELS], target.board_heat,
                                         target.board_weights[:, :, None, None])
    if entries:
        entry_positive, entry_negative, entry_counted = _focal(heads.entry[:, ENTRY_HEAT], target.entry_heat,
                                                               1 + ring_weight * target.ring)
        positive, negative, counted = positive + entry_positive, negative + entry_negative, counted + entry_counted
    heatmap_loss = -(positive + negative) / counted.clamp(min=1)
    offset_loss = _offset_loss(heads.board[:, BOARD_OFFSETS], target.board_offsets, target.board_mask)
    if entries:
        offset_loss = offset_loss + _offset_loss(heads.entry[:, ENTRY_OFFSETS], target.entry_offsets, target.entry_mask)
    return heatmap_loss, offset_loss


def _focal(logits: torch.Tensor, heat: torch.Tensor, weight: torch.Tensor):
    """weight scales every cell's term: a Calibration channel's weight, or 1 + the ring's, which is 0 on positives."""
    predicted = torch.sigmoid(logits.float()).clamp(1e-4, 1 - 1e-4)
    positive = heat.eq(1).float()
    positive_loss = torch.log(predicted) * (1 - predicted) ** FOCAL_ALPHA * positive
    negative_loss = torch.log(1 - predicted) * predicted**FOCAL_ALPHA * (1 - heat) ** FOCAL_BETA * (1 - positive)
    return positive_loss.mul(weight).sum(), negative_loss.mul(weight).sum(), (positive * weight.gt(0)).sum()


def _offset_loss(predicted: torch.Tensor, offsets: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    error = F.l1_loss(predicted.float(), offsets, reduction="none").sum(dim=1) * mask
    return error.sum() / mask.sum().clamp(min=1)


def use_tuned_kernels(data: DataDir) -> None:
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


def _step(model, optimiser, batch, device: str, speed: Speed, entries: bool = True,
          ring_weight: float = RING_WEIGHT) -> tuple[float, float, float]:
    image, target = batch
    target = Targets(*(t.to(device, non_blocking=True) for t in target))
    with speed.autocast(device):
        heads = model(image.to(device, non_blocking=True).contiguous(memory_format=speed.memory))
    heatmap_loss, offset_loss = loss_terms(heads, target, entries, ring_weight)
    loss = heatmap_loss + OFFSET_WEIGHT * offset_loss
    optimiser.zero_grad(set_to_none=True)
    loss.backward()
    optimiser.step()
    return float(loss.detach()), float(heatmap_loss.detach()), float(offset_loss.detach())


def _model(device: str, speed: Speed, entry_stride: int = ENTRY_STRIDE) -> torch.nn.Module:
    return KeypointNet(entry_stride).to(device, memory_format=speed.memory)


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
    entry_stride: int = ENTRY_STRIDE
    ring_weight: float = RING_WEIGHT


def probe(data: DataDir, choice: str, steps: int = 200, size: int = 512, batch: int = 16, workers: int = 8,
          seed: int = 0, speed: Speed = Speed(), entry_stride: int = ENTRY_STRIDE,
          ring_weight: float = RING_WEIGHT) -> Probe:
    if steps <= WARMUP:
        raise DartsMlError(f"--steps {steps} leaves nothing to time after the {WARMUP} warm-up steps; pass more than {WARMUP}")
    device, hardware = resolve_device(choice)
    speed.check(device)
    torch.manual_seed(seed)
    samples = deepdarts_samples(data, "train")
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(KeypointDataset(samples, size, entry_stride=entry_stride), batch_size=batch,
                                         shuffle=True, generator=generator, num_workers=workers, drop_last=True,
                                         persistent_workers=workers > 0)
    if steps > len(loader):
        raise DartsMlError(f"--steps {steps} is more than one epoch, {len(loader)} batches of {batch} from "
                           f"{len(samples)} Photos; pass at most {len(loader)}")
    use_tuned_kernels(data)
    model = _model(device, speed, entry_stride)
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    model.train()
    losses = []
    started = None
    batches = iter(loader)
    for step in range(steps):
        if step == WARMUP:
            _sync(device)
            started = time.perf_counter()
        losses.append(_step(model, optimiser, next(batches), device, speed, ring_weight=ring_weight)[0])
    _sync(device)
    rate = (steps - WARMUP) * batch / (time.perf_counter() - started)
    miopen = {k: v for k, v in sorted(os.environ.items()) if k.startswith("MIOPEN_")}
    return Probe(device, hardware, size, batch, steps, rate, len(samples) / rate / 60, len(samples), losses,
                 speed.bf16, speed.channels_last, commit(), miopen, entry_stride, ring_weight)


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
    entry_stride: int = ENTRY_STRIDE
    ring_weight: float = RING_WEIGHT
    ring_inner_mm: float = RING_INNER_MM
    ring_outer_mm: float = RING_OUTER_MM
    renders: tuple[str, ...] = ()
    render_weight: float = RENDER_WEIGHT
    public: tuple[str, ...] = ()
    public_weight: float = PUBLIC_WEIGHT
    freeze_norm: bool = False

    @property
    def speed(self) -> Speed:
        return Speed(self.bf16, self.channels_last)


def run_folder(data: DataDir, name: str, today: dt.date) -> Path:
    if not _RUN_NAME.fullmatch(name):
        raise DartsMlError(f"--name {name!r}: lower-case letters, digits and hyphens, such as board-512")
    return data.runs() / f"{today:%Y-%m-%d}-{name}"


def load_weights(path: Path, device: str) -> torch.nn.Module:
    state = _state(path)
    model = KeypointNet(stride_of_weights(state))
    model.load_state_dict(state)
    return model.to(device)


def _state(path: Path) -> dict[str, torch.Tensor]:
    if not path.exists():
        raise DartsMlError(f"no weights at {path}")
    return torch.load(path, map_location="cpu", weights_only=True)["model"]


def initial_model(path: Path, entry_stride: int, log) -> tuple[KeypointNet, list[str]]:
    model = KeypointNet(entry_stride)
    fresh = load_matching(model, _state(path))
    print(f"--init {path.parent.name}: every parameter loaded but {len(fresh)}, which start fresh"
          + "".join(f"\n  {name}" for name in fresh), file=log, flush=True)
    return model, fresh


def loaded_norms(model: torch.nn.Module, fresh: list[str]) -> set[str]:
    return {name for name, module in model.named_modules()
            if isinstance(module, torch.nn.modules.batchnorm._BatchNorm) and f"{name}.running_mean" not in fresh}


def train(data: DataDir, config: RunConfig, today: dt.date | None = None, log=None) -> Path:
    log = log or sys.stderr
    if config.freeze_norm and not config.init:
        raise DartsMlError("--freeze-norm keeps the statistics of the run --init names; name one")
    folder = run_folder(data, config.name, today or dt.date.today())
    if folder.exists():
        raise DartsMlError(f"{folder} exists; a run is never overwritten, so give this one another --name")
    use_tuned_kernels(data)
    device, hardware = resolve_device(config.device)
    config.speed.check(device)
    torch.manual_seed(config.seed)
    training = deepdarts_samples(data, "train")
    validation = deepdarts_samples(data, "val")
    render_training, render_validation = render_split(render_samples(data, config.renders), config.seed)
    if config.renders and not render_training:
        raise DartsMlError(f"{', '.join(config.renders)} leave no rendered frame for training")
    public_training, public_validation = public_split(public_samples(data, config.public))
    if config.public and not public_training:
        raise DartsMlError(f"{', '.join(config.public)} leave no public frame for training")
    public_sets = {name: _public_provenance(data, name) for name in config.public}
    loader = training_loader(training, render_training, config, public_training)
    if not len(loader):
        raise DartsMlError(f"{len(training) + len(render_training) + len(public_training)} training Photos make no "
                           f"batch of {config.batch}")
    frozen: set[str] = set()
    if config.init:
        model, fresh = initial_model(data.runs() / config.init / "best.pt", config.entry_stride, log)
        model = model.to(device, memory_format=config.speed.memory)
        if config.freeze_norm:
            frozen = loaded_norms(model, fresh)
    else:
        model = _model(device, config.speed, config.entry_stride)
    optimiser = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    total = config.epochs * len(loader)
    schedule = torch.optim.lr_scheduler.LambdaLR(optimiser, lambda step: _rate(step, config.warmup_steps, total))
    inference = Inference(model, device, config.size, config.batch, config.workers, config.speed)

    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({
        **asdict(config), "device_used": device, "hardware": hardware, "commit": commit(),
        "torch": torch.__version__, "training_photos": len(training), "validation_photos": len(validation),
        "validation": "DeepDarts val", "started": dt.datetime.now().isoformat(timespec="seconds"),
        "training_renders": len(render_training), "validation_renders": len(render_validation),
        "render_sets": {name: _render_provenance(data, name) for name in config.renders},
        "training_public": len(public_training), "validation_public": len(public_validation),
        "public_sets": public_sets,
    }, indent=1), encoding="utf-8")
    best = None
    step = 0
    with (folder / "losses.jsonl").open("w", encoding="utf-8") as losses, \
         (folder / "epochs.jsonl").open("w", encoding="utf-8") as epochs:
        for epoch in range(1, config.epochs + 1):
            started = time.perf_counter()
            training_mode(model, frozen)
            running = []
            for batch in loader:
                loss, heatmap, offset = _step(model, optimiser, batch, device, config.speed, not config.board_only,
                                              config.ring_weight)
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
            rendered = None
            if render_validation:
                print(f"[epoch {epoch}/{config.epochs}] reading {len(render_validation)} rendered val frames, "
                      "never chosen on ...", file=log, flush=True)
                rendered = figures(render_validation, locate(inference, [s.photo for s in render_validation]))
            public = None
            if public_validation:
                print(f"[epoch {epoch}/{config.epochs}] reading {len(public_validation)} public val frames, "
                      "never chosen on ...", file=log, flush=True)
                public = figures(public_validation, locate(inference, [s.photo for s in public_validation]))
            key = reading.key(config.board_only)
            chosen = best is None or key > best[1]
            _save_weights(model, epoch, folder / "last.pt")
            if chosen:
                best = (epoch, key)
                _save_weights(model, epoch, folder / "best.pt")
            epochs.write(json.dumps({"epoch": epoch, "mean_loss": sum(running) / len(running),
                                     "train_seconds": trained, "validate_seconds": time.perf_counter() - started - trained,
                                     "best": chosen, "figures": reading.as_dict(),
                                     **({"render_figures": rendered.as_dict()} if rendered else {}),
                                     **({"public_figures": public.as_dict()} if public else {})}) + "\n")
            epochs.flush()
            for line in reading.lines():
                print(f"[epoch {epoch}/{config.epochs}] {line}", file=log, flush=True)
            for line in rendered.lines() if rendered else ():
                print(f"[epoch {epoch}/{config.epochs}] renders: {line}", file=log, flush=True)
            for line in public.lines() if public else ():
                print(f"[epoch {epoch}/{config.epochs}] public: {line}", file=log, flush=True)
    return folder


def mixing(deepdarts: int, renders: int, render_weight: float, public: int = 0,
           public_weight: float = PUBLIC_WEIGHT) -> tuple[list[float], int]:
    """Per-sample weights drawing each source its weight times as often as DeepDarts Photos, and an epoch's draws."""
    weights = [1 / deepdarts] * deepdarts
    share = 1.0
    for count, weight in ((renders, render_weight), (public, public_weight)):
        if count:
            weights += [weight / count] * count
            share += weight
    return weights, round(deepdarts * share)


def training_loader(deepdarts: list[Sample], renders: list[Sample], config: RunConfig,
                    public: list[Sample] = ()) -> torch.utils.data.DataLoader:
    public = list(public)
    dataset = KeypointDataset(deepdarts + renders + public, config.size, config.augment, config.entry_stride,
                              (config.ring_inner_mm, config.ring_outer_mm))
    generator = torch.Generator().manual_seed(config.seed)
    order = {"shuffle": True, "generator": generator}
    if renders or public:
        weights, draws = mixing(len(deepdarts), len(renders), config.render_weight, len(public), config.public_weight)
        order = {"sampler": torch.utils.data.WeightedRandomSampler(weights, draws, generator=generator)}
    return torch.utils.data.DataLoader(dataset, batch_size=config.batch, num_workers=config.workers, drop_last=True,
                                       persistent_workers=config.workers > 0, **order)


def _render_provenance(data: DataDir, name: str) -> dict:
    manifest = json.loads((data.render_set(name) / RENDER_MANIFEST).read_text(encoding="utf-8"))
    return {"renderer": manifest["renderer"], "records": manifest["records"]}


def _public_provenance(data: DataDir, name: str) -> dict:
    path = data.public_set(name) / PUBLIC_MANIFEST
    reason = ("a public set is trained on only with its source, licence, credit, checksummed mirror and refused "
              "frames recorded")
    if not path.exists():
        raise DartsMlError(f"no {path}; {reason}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in (*_PUBLIC_PROVENANCE, "refused") if key not in manifest]
    mirror = manifest.get("mirror")
    if "mirror" in manifest and not (isinstance(mirror, dict) and "sha256" in mirror):
        missing.append("mirror.sha256")
    if missing:
        raise DartsMlError(f"{path} has no {', '.join(missing)}; {reason}")
    return {key: manifest[key] for key in _PUBLIC_PROVENANCE}


def training_mode(model: torch.nn.Module, frozen: Collection[str] = ()) -> None:
    model.train()
    for name, module in model.named_modules():
        if name in frozen:
            module.eval()


def _rate(step: int, warmup: int, total: int) -> float:
    if step < warmup:
        return (step + 1) / warmup
    return 0.5 * (1 + math.cos(math.pi * min(1.0, (step - warmup) / max(1, total - warmup))))


def _save_weights(model: torch.nn.Module, epoch: int, path: Path) -> None:
    temporary = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "epoch": epoch}, temporary)
    temporary.replace(path)
