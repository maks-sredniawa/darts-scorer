import math
from dataclasses import dataclass

import cv2
import numpy as np

from darts_ml.board import (
    CALIBRATION_POINTS,
    INNER_DOUBLE,
    INNER_TREBLE,
    OUTER_BULL_RING,
    OUTER_DOUBLE,
    OUTER_TREBLE,
    SEGMENTS,
    WIRES,
    boundary_degrees,
)

SURROUND_MM = 225.0
TOP_PX = 1800
TOP_SCALE = TOP_PX / (2 * SURROUND_MM)
CALIBRATION_MM = np.array([p.mm for p in CALIBRATION_POINTS], dtype=np.float64)
NUM_CALIBRATION = len(CALIBRATION_POINTS)


@dataclass
class Sample:
    image: np.ndarray
    calibration_px: np.ndarray
    calibration_visible: np.ndarray
    darts_px: np.ndarray
    darts_mm: np.ndarray
    image_from_board: np.ndarray


def _jitter(rng, colour, amount=18):
    return tuple(int(np.clip(c + rng.integers(-amount, amount + 1), 0, 255)) for c in colour)


def render_top_down(rng: np.random.Generator) -> np.ndarray:
    half = TOP_PX / 2
    ys, xs = np.mgrid[0:TOP_PX, 0:TOP_PX].astype(np.float32)
    x_mm = (xs + 0.5 - half) / TOP_SCALE
    y_mm = (half - ys - 0.5) / TOP_SCALE
    r = np.hypot(x_mm, y_mm)
    clockwise = (np.degrees(np.arctan2(x_mm, y_mm)) + 360) % 360
    segment = (((clockwise + 9) % 360) // 18).astype(np.int32)
    dark_segment = segment % 2 == 0

    black = _jitter(rng, (25, 25, 25), 10)
    cream = _jitter(rng, (205, 225, 235))
    red = _jitter(rng, (40, 40, 200))
    green = _jitter(rng, (60, 140, 30))
    surround = _jitter(rng, (20, 20, 20), 10)

    img = np.empty((TOP_PX, TOP_PX, 3), np.uint8)
    img[:] = surround
    singles = r < OUTER_DOUBLE.outer_mm
    img[singles & dark_segment] = black
    img[singles & ~dark_segment] = cream
    for inner, outer in ((INNER_TREBLE, OUTER_TREBLE), (INNER_DOUBLE, OUTER_DOUBLE)):
        band = (r >= inner.inner_mm) & (r < outer.outer_mm)
        img[band & dark_segment] = red
        img[band & ~dark_segment] = green
    img[r < OUTER_BULL_RING.outer_mm] = green
    img[r < WIRES[0].outer_mm] = red

    wire = _jitter(rng, (185, 190, 195), 25)
    on_wire = np.zeros_like(r, dtype=bool)
    for w in WIRES:
        on_wire |= (r >= w.inner_mm) & (r < w.outer_mm)
    radial = (r >= OUTER_BULL_RING.inner_mm) & (r < OUTER_DOUBLE.outer_mm)
    for i in range(len(SEGMENTS)):
        theta = math.radians(boundary_degrees(i))
        dist = np.abs(x_mm * math.cos(theta) - y_mm * math.sin(theta))
        ahead = x_mm * math.sin(theta) + y_mm * math.cos(theta) > 0
        on_wire |= radial & ahead & (dist < 0.75)
    img[on_wire] = wire

    text = _jitter(rng, (235, 235, 235), 15)
    for i, number in enumerate(SEGMENTS):
        theta = math.radians(i * 18)
        cx = half + 196 * TOP_SCALE * math.sin(theta)
        cy = half - 196 * TOP_SCALE * math.cos(theta)
        label = str(number)
        scale = 2.6
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 6)
        cv2.putText(img, label, (int(cx - tw / 2), int(cy + th / 2)), cv2.FONT_HERSHEY_SIMPLEX, scale, text, 6, cv2.LINE_AA)
    return img


def _top_from_board() -> np.ndarray:
    half = TOP_PX / 2
    return np.array([[TOP_SCALE, 0, half], [0, -TOP_SCALE, half], [0, 0, 1]], dtype=np.float64)


def _rotation(axis_deg: float, tilt_deg: float, roll_deg: float) -> np.ndarray:
    a, t, r = (math.radians(v) for v in (axis_deg, tilt_deg, roll_deg))
    rz = lambda g: np.array([[math.cos(g), -math.sin(g), 0], [math.sin(g), math.cos(g), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    return rz(r) @ rz(a) @ rx @ rz(-a)


def _camera(rng, size: int, max_tilt: float):
    rot = _rotation(rng.uniform(0, 360), rng.uniform(0, max_tilt), rng.normal(0, 12))
    distance = rng.uniform(450, 900)
    focal = rng.uniform(0.8, 1.6) * size
    flip = np.diag([1.0, -1.0, 1.0])
    k = np.array([[focal, 0, 0], [0, focal, 0], [0, 0, 1]])

    def project3d(points_mm: np.ndarray) -> np.ndarray:
        cam = (rot @ (flip @ points_mm.T)).T + np.array([0, 0, distance])
        uv = (k @ cam.T).T
        return uv[:, :2] / uv[:, 2:3]

    rim = np.array([[SURROUND_MM * math.sin(t), SURROUND_MM * math.cos(t), 0] for t in np.linspace(0, 2 * math.pi, 64)])
    rim_px = project3d(rim)
    lo, hi = rim_px.min(0), rim_px.max(0)
    fill = rng.uniform(0.6, 1.0) * size / max(hi - lo)
    centre = (lo + hi) / 2
    offset = rng.uniform(-0.12, 0.12, 2) * size
    fit = np.array([[fill, 0, size / 2 + offset[0] - fill * centre[0]], [0, fill, size / 2 + offset[1] - fill * centre[1]], [0, 0, 1]])

    def project(points_mm: np.ndarray) -> np.ndarray:
        px = project3d(points_mm)
        return (fit[:2, :2] @ px.T).T + fit[:2, 2]

    plane = np.array([[0, 0, 0], [100, 0, 0], [0, 100, 0], [100, 100, 0]], dtype=np.float64)
    image_from_board = cv2.getPerspectiveTransform(plane[:, :2].astype(np.float32), project(plane).astype(np.float32)).astype(np.float64)
    return project, image_from_board


def _background(rng, size: int) -> np.ndarray:
    base = rng.integers(0, 256, 3)
    grad = np.linspace(0, 1, size, dtype=np.float32)[None, :, None] * rng.integers(-80, 80, 3)
    bg = np.clip(base + grad + rng.normal(0, 12, (size, size, 3)), 0, 255).astype(np.uint8)
    for _ in range(rng.integers(2, 8)):
        p1 = rng.integers(0, size, 2)
        p2 = p1 + rng.integers(20, size // 2, 2)
        cv2.rectangle(bg, tuple(int(v) for v in p1), tuple(int(v) for v in p2), tuple(int(v) for v in rng.integers(0, 256, 3)), -1)
    return cv2.GaussianBlur(bg, (0, 0), rng.uniform(0.5, 4))


def _draw_dart(rng, img, mask, project, entry_mm):
    length = rng.uniform(95, 140)
    lean = rng.normal(0, 0.18, 2) * length + np.array([0, rng.uniform(0, 25)])
    tail = np.array([entry_mm[0] + lean[0], entry_mm[1] + lean[1], -length])
    along = lambda s: np.array([entry_mm[0], entry_mm[1], 0]) * (1 - s) + tail * s
    pts = project(np.array([along(s) for s in (0.0, 0.08, 0.42, 0.72, 0.78, 1.0)]))
    p = [tuple(int(round(v)) for v in q) for q in pts]
    width = max(2, int(np.linalg.norm(pts[1] - pts[0]) * 0.5) + 1)
    barrel = _jitter(rng, (150, 150, 155), 40)
    shaft = tuple(int(v) for v in rng.integers(0, 256, 3))
    flight = tuple(int(v) for v in rng.integers(0, 256, 3))
    for canvas, colours in ((img, (barrel, shaft, flight)), (mask, (255, 255, 255))):
        cv2.line(canvas, p[0], p[1], colours[0], max(1, width // 2), cv2.LINE_AA)
        cv2.line(canvas, p[1], p[2], colours[0], width + 2, cv2.LINE_AA)
        cv2.line(canvas, p[2], p[3], colours[1], max(1, width // 2), cv2.LINE_AA)
        direction = pts[5] - pts[4]
        normal = np.array([-direction[1], direction[0]])
        normal = normal / (np.linalg.norm(normal) + 1e-6) * max(4.0, np.linalg.norm(direction) * 0.45)
        quad = np.array([pts[4], pts[5] + normal, pts[5], pts[5] - normal]).astype(np.int32)
        cv2.fillConvexPoly(canvas, quad, colours[2], cv2.LINE_AA)


def _entry_point(rng) -> np.ndarray:
    radius = OUTER_DOUBLE.outer_mm * math.sqrt(rng.uniform(0, 1))
    if rng.uniform() < 0.35:
        radius = rng.choice([INNER_TREBLE.inner_mm, OUTER_TREBLE.outer_mm, INNER_DOUBLE.inner_mm, OUTER_DOUBLE.outer_mm]) + rng.normal(0, 2.5)
    theta = rng.uniform(0, 2 * math.pi)
    return np.array([radius * math.sin(theta), radius * math.cos(theta)])


class Renderer:
    def __init__(self, seed: int, size: int = 512, max_tilt: float = 55.0, boards: int = 4):
        self.rng = np.random.default_rng(seed)
        self.size = size
        self.max_tilt = max_tilt
        self.boards = [render_top_down(self.rng) for _ in range(boards)]

    def sample(self) -> Sample:
        rng, size = self.rng, self.size
        project, image_from_board = _camera(rng, size, self.max_tilt)
        warp = image_from_board @ np.linalg.inv(_top_from_board())
        top = self.boards[rng.integers(len(self.boards))]
        board = cv2.warpPerspective(top, warp, (size, size), flags=cv2.INTER_AREA)
        disc = np.zeros(top.shape[:2], np.uint8)
        cv2.circle(disc, (TOP_PX // 2, TOP_PX // 2), int(SURROUND_MM * TOP_SCALE), 255, -1)
        alpha = cv2.warpPerspective(disc, warp, (size, size))[..., None] / 255.0
        img = (board * alpha + _background(rng, size) * (1 - alpha)).astype(np.uint8)

        darts_mm = np.array([_entry_point(rng) for _ in range(rng.integers(0, 4))]).reshape(-1, 2)
        order = np.argsort(-darts_mm[:, 1]) if len(darts_mm) else []
        dart_mask = np.zeros((size, size), np.uint8)
        for i in order:
            _draw_dart(rng, img, dart_mask, project, darts_mm[i])

        img = self._photometric(img)
        calibration_px = project(np.c_[CALIBRATION_MM, np.zeros(NUM_CALIBRATION)])
        inside = np.all((calibration_px >= 0) & (calibration_px < size), axis=1)
        covered = np.zeros(NUM_CALIBRATION, bool)
        for i, (x, y) in enumerate(calibration_px):
            if inside[i]:
                covered[i] = dart_mask[int(y), int(x)] > 0
        darts_px = project(np.c_[darts_mm, np.zeros(len(darts_mm))]) if len(darts_mm) else np.zeros((0, 2))
        return Sample(img, calibration_px, inside & ~covered, darts_px, darts_mm, image_from_board)

    def _photometric(self, img: np.ndarray) -> np.ndarray:
        rng = self.rng
        out = img.astype(np.float32) * rng.uniform(0.55, 1.35) + rng.uniform(-35, 35)
        out *= rng.uniform(0.85, 1.15, 3)
        shade = np.linspace(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0), self.size, dtype=np.float32)
        out *= shade[:, None, None] if rng.uniform() < 0.5 else shade[None, :, None]
        out += rng.normal(0, rng.uniform(1, 8), out.shape)
        out = np.clip(out, 0, 255).astype(np.uint8)
        if rng.uniform() < 0.5:
            out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.3, 1.4))
        quality = int(rng.uniform(55, 95))
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
