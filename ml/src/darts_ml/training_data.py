from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from . import DartsMlError
from .board import CALIBRATION_BY_NAME, CALIBRATION_POINTS
from .deepdarts import ORDER, PROJECTED, RECORDS as DEEPDARTS_RECORDS, SOURCE as DEEPDARTS, deepdarts_mm
from .homography import fit, project
from .model import ENTRY_CHANNEL, HEATMAPS, STRIDE
from .paths import DataDir

PROJECTED_WEIGHT = 0.5
SIGMA_CELLS = 2.0
ENTRY_SIGMA_CELLS = 1.0
_INDEX = {point.name: i for i, point in enumerate(CALIBRATION_POINTS)}
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class RefusedRecord(DartsMlError):
    pass


@dataclass(frozen=True)
class Sample:
    photo: Path
    calibration: tuple[tuple[int, float, float, float], ...]
    entries: tuple[tuple[float, float], ...]


def deepdarts_samples(data: DataDir, split: str) -> list[Sample]:
    if split == "test":
        raise RefusedRecord("DeepDarts' test split is read only for readings, never trained or chosen on (phase-M2.md §3)")
    path = data.deepdarts() / DEEPDARTS_RECORDS
    if not path.exists():
        raise DartsMlError(f"no {path}; run `darts-ml deepdarts convert` first")
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["split"] == "test":
            continue
        if record["split"] == split:
            samples.append(_deepdarts_sample(data.root, record))
    return samples


def _deepdarts_sample(root: Path, record: dict) -> Sample:
    clicked = {c["name"]: (c["x"], c["y"]) for c in record["calibration"] if c["source"] == DEEPDARTS}
    to_image = fit(deepdarts_mm(), [clicked[n] for n in ORDER])
    centres = project(to_image, [CALIBRATION_BY_NAME[n].mm for n in ORDER])
    moved = dict(zip(ORDER, map(tuple, centres), strict=True))
    calibration = []
    for c in record["calibration"]:
        x, y = moved.get(c["name"], (c["x"], c["y"]))
        weight = PROJECTED_WEIGHT if c["source"] == PROJECTED else 1.0
        calibration.append((_INDEX[c["name"]], float(x), float(y), weight))
    entries = tuple((e["x"], e["y"]) for e in record["entries"])
    return Sample(root / record["photo"], tuple(calibration), entries)


class KeypointDataset(torch.utils.data.Dataset):
    def __init__(self, samples: list[Sample], size: int) -> None:
        self.samples = samples
        self.size = size

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        sample = self.samples[index]
        with Image.open(sample.photo) as photo:
            scale = (self.size / photo.width, self.size / photo.height)
            image = np.asarray(photo.convert("RGB").resize((self.size, self.size), Image.BILINEAR), dtype=np.float32)
        image = (image / 255.0 - _MEAN) / _STD
        cells = self.size // STRIDE
        heatmaps = np.zeros((HEATMAPS, cells, cells), dtype=np.float32)
        weights = np.ones(HEATMAPS, dtype=np.float32)
        calibration_offsets, entry_offsets = np.zeros((2, 2, cells, cells), dtype=np.float32)
        calibration_mask, entry_mask = np.zeros((2, cells, cells), dtype=np.float32)
        points = [(channel, x, y, w) for channel, x, y, w in sample.calibration]
        points += [(ENTRY_CHANNEL, x, y, 1.0) for x, y in sample.entries]
        for channel, x, y, weight in points:
            cx, cy = x * scale[0] / STRIDE, y * scale[1] / STRIDE
            if not (0 <= cx < cells and 0 <= cy < cells):
                continue
            entry = channel == ENTRY_CHANNEL
            _splat(heatmaps[channel], cx, cy, ENTRY_SIGMA_CELLS if entry else SIGMA_CELLS)
            if not entry:
                weights[channel] = weight
            ix, iy = int(cx), int(cy)
            offsets, mask = (entry_offsets, entry_mask) if entry else (calibration_offsets, calibration_mask)
            offsets[:, iy, ix] = (cx - ix, cy - iy)
            mask[iy, ix] = 1.0
        arrays = (heatmaps, weights, calibration_offsets, calibration_mask, entry_offsets, entry_mask)
        return (torch.from_numpy(image.transpose(2, 0, 1).copy()), *map(torch.from_numpy, arrays))


def _splat(heatmap: np.ndarray, cx: float, cy: float, sigma: float) -> None:
    cells = heatmap.shape[0]
    radius = int(3 * sigma)
    ix, iy = int(cx), int(cy)
    x0, x1 = max(0, ix - radius), min(cells, ix + radius + 1)
    y0, y1 = max(0, iy - radius), min(cells, iy + radius + 1)
    xs = np.arange(x0, x1) - ix
    ys = np.arange(y0, y1) - iy
    patch = np.exp(-(xs[None, :] ** 2 + ys[:, None] ** 2) / (2 * sigma**2))
    np.maximum(heatmap[y0:y1, x0:x1], patch, out=heatmap[y0:y1, x0:x1])
