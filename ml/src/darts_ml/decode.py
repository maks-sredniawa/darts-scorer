from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import DartsMlError
from .board import CALIBRATION_POINTS
from .homography import _normaliser, fit, project
from .model import CALIBRATION_CHANNELS, CALIBRATION_OFFSETS, ENTRY_CHANNEL, ENTRY_OFFSETS, STRIDE

THRESHOLD = 0.25
ENTRY_THRESHOLD = 0.34
ENTRIES_APART_MM = 0.0
MOST_ENTRIES = 3
CONFIDENT = 0.5
RANSAC_MM = 3.0
MIN_INLIERS = 8
RANSAC_ROUNDS = 500
_BOARD = np.array([p.mm for p in CALIBRATION_POINTS])


@dataclass(frozen=True)
class Peak:
    x: float
    y: float
    confidence: float

    @property
    def low_confidence(self) -> bool:
        return self.confidence < CONFIDENT


@dataclass(frozen=True)
class EntryRule:
    threshold: float = ENTRY_THRESHOLD
    apart_mm: float = ENTRIES_APART_MM
    most: int | None = MOST_ENTRIES


@dataclass(frozen=True)
class Decoded:
    calibration: dict[int, Peak]
    entries: tuple[Peak, ...]


def sigmoid(logits: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-logits))


def decode(logits: np.ndarray, threshold: float = THRESHOLD, entry_threshold: float | None = None) -> Decoded:
    heat = sigmoid(logits[:ENTRY_CHANNEL + 1].astype(np.float64))
    calibration_offsets, entry_offsets = logits[CALIBRATION_OFFSETS], logits[ENTRY_OFFSETS]
    calibration = {}
    for channel in range(CALIBRATION_CHANNELS):
        iy, ix = np.unravel_index(int(heat[channel].argmax()), heat[channel].shape)
        if heat[channel, iy, ix] >= threshold:
            calibration[channel] = _peak(ix, iy, heat[channel, iy, ix], calibration_offsets)
    entry = heat[ENTRY_CHANNEL]
    floor = threshold if entry_threshold is None else entry_threshold
    ys, xs = np.nonzero((entry >= floor) & (entry >= _neighbourhood_max(entry)))
    entries = tuple(_peak(ix, iy, entry[iy, ix], entry_offsets) for iy, ix in zip(ys, xs, strict=True))
    return Decoded(calibration, entries)


def kept_entries(board_mm: np.ndarray, confidences: list[float], rule: EntryRule) -> list[int]:
    kept: list[int] = []
    for i in sorted(range(len(confidences)), key=lambda i: -confidences[i]):
        if confidences[i] < rule.threshold or (rule.most is not None and len(kept) >= rule.most):
            break
        if all(np.linalg.norm(board_mm[i] - board_mm[k]) >= rule.apart_mm for k in kept):
            kept.append(i)
    return sorted(kept)


def _peak(ix: int, iy: int, confidence: float, offsets: np.ndarray) -> Peak:
    return Peak(float((ix + offsets[0, iy, ix]) * STRIDE), float((iy + offsets[1, iy, ix]) * STRIDE), float(confidence))


def _neighbourhood_max(heat: np.ndarray) -> np.ndarray:
    padded = np.pad(heat, 1, constant_values=-np.inf)
    rows, cols = heat.shape
    return np.max([padded[dy:dy + rows, dx:dx + cols] for dy in range(3) for dx in range(3)], axis=0)


def ransac(calibration: dict[int, tuple[float, float]], seed: int = 0) -> tuple[np.ndarray, list[int]] | None:
    channels = sorted(calibration)
    if len(channels) < MIN_INLIERS:
        return None
    pixels = np.array([calibration[c] for c in channels], dtype=float)
    board = _BOARD[channels]
    rng = np.random.default_rng(seed)
    best = np.zeros(len(channels), dtype=bool)
    needed, rounds = RANSAC_ROUNDS, 0
    while rounds < min(needed, RANSAC_ROUNDS):
        rounds += 1
        pick = rng.choice(len(channels), 4, replace=False)
        h = _four_point(pixels[pick], board[pick])
        if h is None:
            continue
        inliers = np.linalg.norm(project(h, pixels) - board, axis=1) < RANSAC_MM
        if inliers.sum() > best.sum():
            best = inliers
            share = best.mean()
            needed = 1 if share >= 1 else math.ceil(math.log(1e-3) / math.log(1 - share**4))
    if best.sum() < MIN_INLIERS:
        return None
    try:
        to_board = fit(pixels[best], board[best])
    except DartsMlError:
        return None
    inliers = np.linalg.norm(project(to_board, pixels) - board, axis=1) < RANSAC_MM
    if inliers.sum() < MIN_INLIERS:
        return None
    try:
        to_board = fit(pixels[inliers], board[inliers])
    except DartsMlError:
        return None
    return to_board, [c for c, kept in zip(channels, inliers, strict=True) if kept]


def _four_point(source: np.ndarray, target: np.ndarray) -> np.ndarray | None:
    try:
        source_norm, target_norm = _normaliser(source), _normaliser(target)
    except DartsMlError:
        return None
    rows = []
    for (x, y), (u, v) in zip(project(source_norm, source), project(target_norm, target), strict=True):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, singular, vt = np.linalg.svd(np.asarray(rows))
    if singular[-1] < 1e-9 * singular[0]:
        return None
    h = np.linalg.inv(target_norm) @ vt[-1].reshape(3, 3) @ source_norm
    return h / h[2, 2] if abs(h[2, 2]) > 1e-12 else None
