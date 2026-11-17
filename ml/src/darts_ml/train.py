from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

import torch
from torch.nn import functional as F

from . import DartsMlError
from .model import CALIBRATION_OFFSETS, ENTRY_OFFSETS, HEATMAPS, KeypointNet
from .paths import DataDir
from .training_data import KeypointDataset, deepdarts_samples

FOCAL_ALPHA = 2.0
FOCAL_BETA = 4.0
OFFSET_WEIGHT = 1.0
WARMUP = 10


def loss_terms(output: torch.Tensor, heatmaps, weights, calibration_offsets, calibration_mask, entry_offsets,
               entry_mask) -> tuple[torch.Tensor, torch.Tensor]:
    predicted = torch.sigmoid(output[:, :HEATMAPS].float()).clamp(1e-4, 1 - 1e-4)
    positive = heatmaps.eq(1).float()
    positive_loss = torch.log(predicted) * (1 - predicted) ** FOCAL_ALPHA * positive
    negative_loss = torch.log(1 - predicted) * predicted**FOCAL_ALPHA * (1 - heatmaps) ** FOCAL_BETA * (1 - positive)
    per_channel = (positive_loss + negative_loss).sum(dim=(2, 3)) * weights
    heatmap_loss = -per_channel.sum() / positive.sum().clamp(min=1)
    offset_loss = (_offset_loss(output[:, CALIBRATION_OFFSETS], calibration_offsets, calibration_mask)
                   + _offset_loss(output[:, ENTRY_OFFSETS], entry_offsets, entry_mask))
    return heatmap_loss, offset_loss


def _offset_loss(predicted: torch.Tensor, offsets: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    error = F.l1_loss(predicted.float(), offsets, reduction="none").sum(dim=1) * mask
    return error.sum() / mask.sum().clamp(min=1)


def resolve_device(choice: str) -> tuple[str, str]:
    gpu = torch.cuda.is_available()
    if choice == "gpu" and not gpu:
        raise DartsMlError("PyTorch sees no GPU; install the ROCm (AMD) or CUDA (NVIDIA) build of PyTorch, or pass --device cpu")
    if choice == "cpu" or not gpu:
        return "cpu", f"CPU, {torch.get_num_threads()} threads"
    backend = f"ROCm {torch.version.hip}" if torch.version.hip else f"CUDA {torch.version.cuda}"
    return "cuda", f"{torch.cuda.get_device_name(0)} ({backend})"


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


def probe(data: DataDir, choice: str, steps: int = 200, size: int = 512, batch: int = 16, workers: int = 8,
          seed: int = 0) -> Probe:
    if steps <= WARMUP:
        raise DartsMlError(f"--steps {steps} leaves nothing to time after the {WARMUP} warm-up steps; pass more than {WARMUP}")
    device, hardware = resolve_device(choice)
    torch.manual_seed(seed)
    samples = deepdarts_samples(data, "train")
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(KeypointDataset(samples, size), batch_size=batch, shuffle=True,
                                         generator=generator, num_workers=workers, drop_last=True,
                                         persistent_workers=workers > 0)
    if steps > len(loader):
        raise DartsMlError(f"--steps {steps} is more than one epoch, {len(loader)} batches of {batch} from "
                           f"{len(samples)} Photos; pass at most {len(loader)}")
    model = KeypointNet().to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    model.train()
    losses = []
    started = None
    batches = iter(loader)
    for step in range(steps):
        tensors = [t.to(device, non_blocking=True) for t in next(batches)]
        if step == WARMUP:
            _sync(device)
            started = time.perf_counter()
        heatmap_loss, offset_loss = loss_terms(model(tensors[0]), *tensors[1:])
        loss = heatmap_loss + OFFSET_WEIGHT * offset_loss
        optimiser.zero_grad(set_to_none=True)
        loss.backward()
        optimiser.step()
        losses.append(float(loss.detach()))
    _sync(device)
    rate = (steps - WARMUP) * batch / (time.perf_counter() - started)
    return Probe(device, hardware, size, batch, steps, rate, len(samples) / rate / 60, len(samples), losses)


def _sync(device: str) -> None:
    if device.startswith("cuda"):
        torch.cuda.synchronize()


def save(result: Probe, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=1), encoding="utf-8")
