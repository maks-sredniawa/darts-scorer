from __future__ import annotations

import numpy as np

from . import DartsMlError
from .board import CALIBRATION_POINTS

MIN_POINTS = 4


def project(h: np.ndarray, points) -> np.ndarray:
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    mapped = np.column_stack([points, np.ones(len(points))]) @ h.T
    return mapped[:, :2] / mapped[:, 2:3]


def invert(h: np.ndarray) -> np.ndarray:
    return np.linalg.inv(h)


def fit(source, target) -> np.ndarray:
    source = np.asarray(source, dtype=float).reshape(-1, 2)
    target = np.asarray(target, dtype=float).reshape(-1, 2)
    if len(source) != len(target):
        raise ValueError("source and target differ in length")
    if len(source) < MIN_POINTS:
        raise DartsMlError(f"a homography needs at least {MIN_POINTS} points, got {len(source)}")
    source_norm, target_norm = _normaliser(source), _normaliser(target)
    s, t = project(source_norm, source), project(target_norm, target)
    h = _refine(_dlt(s, t), s, t)
    return invert(target_norm) @ h @ source_norm


def residuals_mm(h: np.ndarray, source, target) -> np.ndarray:
    return np.linalg.norm(project(h, source) - np.asarray(target, dtype=float), axis=1)


def crossing_errors_mm(truth: np.ndarray, other: np.ndarray) -> np.ndarray:
    board = np.array([point.mm for point in CALIBRATION_POINTS])
    return np.linalg.norm(project(other, project(invert(truth), board)) - board, axis=1)


def _normaliser(points: np.ndarray) -> np.ndarray:
    centre = points.mean(axis=0)
    spread = np.linalg.norm(points - centre, axis=1).mean()
    if spread == 0:
        raise DartsMlError("the points for a homography all coincide")
    scale = np.sqrt(2) / spread
    return np.array([[scale, 0, -scale * centre[0]], [0, scale, -scale * centre[1]], [0, 0, 1]])


def _dlt(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    rows = []
    for (x, y), (u, v) in zip(source, target, strict=True):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    design = np.asarray(rows)
    if np.linalg.matrix_rank(design, tol=1e-9) < 8:
        raise DartsMlError("the points for a homography are degenerate (three or more in a line)")
    h = np.linalg.svd(design)[2][-1].reshape(3, 3)
    return h / h[2, 2]


def _refine(h: np.ndarray, source: np.ndarray, target: np.ndarray) -> np.ndarray:
    params = h.ravel()[:8].copy()
    cost = _cost(params, source, target)
    damping = 1e-3
    for _ in range(100):
        residual, jacobian = _residual_and_jacobian(params, source, target)
        normal = jacobian.T @ jacobian
        gradient = jacobian.T @ residual
        step = np.linalg.solve(normal + damping * np.diag(np.diag(normal) + 1e-12), -gradient)
        candidate = params + step
        candidate_cost = _cost(candidate, source, target)
        if candidate_cost < cost:
            params, cost = candidate, candidate_cost
            damping /= 10
            if np.linalg.norm(step) < 1e-12 * (1 + np.linalg.norm(params)):
                break
        else:
            damping *= 10
            if damping > 1e12:
                break
    return np.append(params, 1.0).reshape(3, 3)


def _cost(params: np.ndarray, source: np.ndarray, target: np.ndarray) -> float:
    residual = project(np.append(params, 1.0).reshape(3, 3), source) - target
    return float((residual**2).sum())


def _residual_and_jacobian(params: np.ndarray, source: np.ndarray, target: np.ndarray):
    x, y = source[:, 0], source[:, 1]
    w = params[6] * x + params[7] * y + 1
    u = (params[0] * x + params[1] * y + params[2]) / w
    v = (params[3] * x + params[4] * y + params[5]) / w
    zeros = np.zeros_like(x)
    du = np.column_stack([x / w, y / w, 1 / w, zeros, zeros, zeros, -u * x / w, -u * y / w])
    dv = np.column_stack([zeros, zeros, zeros, x / w, y / w, 1 / w, -v * x / w, -v * y / w])
    residual = np.concatenate([u - target[:, 0], v - target[:, 1]])
    return residual, np.vstack([du, dv])
