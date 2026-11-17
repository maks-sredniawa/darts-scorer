from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from .board import CALIBRATION_POINTS, OUTER_DOUBLE
from .homography import project

RING = np.array([p.mm for p in CALIBRATION_POINTS if p.wire is OUTER_DOUBLE])
CROP_FILL = 0.8


@dataclass(frozen=True)
class Ranges:
    yaw_deg: float = 60.0
    pitch_deg: float = 20.0
    roll_deg: float = 30.0
    distance_mm: tuple[float, float] = (1000.0, 2000.0)
    crop_share: float = 0.7
    crop_fill: tuple[float, float] = (0.7, 0.9)
    whole_fill: tuple[float, float] = (0.25, 0.7)
    crop_shift: float = 0.08
    brightness: float = 0.4
    contrast: float = 0.3
    saturation: float = 0.3
    blur_share: float = 0.3
    blur_radius: float = 1.5


RANGES = Ranges()


def warp(photo: Image.Image, matrix: np.ndarray, size: int) -> Image.Image:
    shrink = _shrink(matrix, photo.size)
    if shrink < 1:
        reduced = (max(1, round(photo.width * shrink)), max(1, round(photo.height * shrink)))
        scale = np.diag([reduced[0] / photo.width, reduced[1] / photo.height, 1.0])
        photo = photo.resize(reduced, Image.BILINEAR, reducing_gap=None)
        matrix = matrix @ np.linalg.inv(scale)
    inverse = np.linalg.inv(matrix)
    inverse /= inverse[2, 2]
    return photo.transform((size, size), Image.PERSPECTIVE, tuple(inverse.ravel()[:8]), Image.BILINEAR)


def _shrink(matrix: np.ndarray, photo_size) -> float:
    centre = np.array([photo_size[0] / 2, photo_size[1] / 2])
    near = project(matrix, [centre, centre + (1, 0), centre + (0, 1)])
    jacobian = np.column_stack([near[1] - near[0], near[2] - near[0]])
    return math.sqrt(abs(np.linalg.det(jacobian)))


def letterbox(photo_size, size: int) -> np.ndarray:
    scale = size / max(photo_size)
    return np.array([[scale, 0, (size - scale * photo_size[0]) / 2],
                     [0, scale, (size - scale * photo_size[1]) / 2],
                     [0, 0, 1.0]])


def framing(board_to_photo: np.ndarray, size: int, fill: float = CROP_FILL, shift=(0.0, 0.0)) -> np.ndarray:
    ring = project(board_to_photo, RING)
    low, high = ring.min(axis=0), ring.max(axis=0)
    scale = fill * size / max(high - low)
    centre = (low + high) / 2
    return np.array([[scale, 0, size / 2 + shift[0] * size - scale * centre[0]],
                     [0, scale, size / 2 + shift[1] * size - scale * centre[1]],
                     [0, 0, 1.0]])


def orbit(yaw_deg: float, pitch_deg: float, roll_deg: float, distance_mm: float) -> np.ndarray:
    yaw, pitch, roll = map(math.radians, (yaw_deg, pitch_deg, roll_deg))
    centre = distance_mm * np.array([math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    forward = -centre / np.linalg.norm(centre)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    c, s = math.cos(roll), math.sin(roll)
    right, down = c * right + s * down, -s * right + c * down
    rotation = np.vstack([right, down, forward])
    h = np.column_stack([rotation[:, 0], rotation[:, 1], -rotation @ centre])
    return h / h[2, 2]


def random_matrix(board_to_photo: np.ndarray, size: int, rng: np.random.Generator, ranges: Ranges = RANGES) -> np.ndarray:
    # The Board plane is re-viewed from a camera orbiting it, as a handheld phone does; every factor is a
    # rotation or a positive scale, so the Board is never mirrored (phase-M2.md §3).
    camera = orbit(rng.uniform(-ranges.yaw_deg, ranges.yaw_deg), rng.uniform(-ranges.pitch_deg, ranges.pitch_deg),
                   rng.uniform(-ranges.roll_deg, ranges.roll_deg), rng.uniform(*ranges.distance_mm))
    if rng.random() < ranges.crop_share:
        fill = rng.uniform(*ranges.crop_fill)
        shift = rng.uniform(-ranges.crop_shift, ranges.crop_shift, 2)
    else:
        fill = rng.uniform(*ranges.whole_fill)
        shift = rng.uniform(-(1 - fill) / 2, (1 - fill) / 2, 2)
    return framing(camera, size, fill, shift) @ camera @ np.linalg.inv(board_to_photo)


def photometric(image: Image.Image, rng: np.random.Generator, ranges: Ranges = RANGES) -> Image.Image:
    for enhancer, spread in ((ImageEnhance.Brightness, ranges.brightness), (ImageEnhance.Contrast, ranges.contrast),
                             (ImageEnhance.Color, ranges.saturation)):
        image = enhancer(image).enhance(rng.uniform(1 - spread, 1 + spread))
    if rng.random() < ranges.blur_share:
        image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0, ranges.blur_radius)))
    return image
