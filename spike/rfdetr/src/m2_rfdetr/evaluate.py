import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from darts_ml.board import score
from m2_spike.synth import CALIBRATION_MM, NUM_CALIBRATION, Renderer
from rfdetr import RFDETRKeypointPreview

BOARD, DART = 0, 1


def decode(kp, dart_threshold: float):
    cal, conf = np.zeros((NUM_CALIBRATION, 2)), np.zeros(NUM_CALIBRATION)
    boards = np.flatnonzero(kp.class_id == BOARD)
    if len(boards):
        best = boards[kp.detection_confidence[boards].argmax()]
        cal = kp.xy[best, :NUM_CALIBRATION].astype(np.float64)
        conf = kp.keypoint_confidence[best, :NUM_CALIBRATION]
    darts = np.flatnonzero((kp.class_id == DART) & (kp.detection_confidence > dart_threshold))
    darts = darts[np.argsort(-kp.detection_confidence[darts])]
    return cal, conf, kp.xy[darts, 0].astype(np.float64).reshape(-1, 2)


def evaluate(model, size: int, count: int, max_tilt: float, dart_threshold: float, batch: int = 16) -> dict:
    renderer = Renderer(12345, size, max_tilt=max_tilt)
    samples = [renderer.sample() for _ in range(count)]
    px_err, board_mm, dart_mm, exact, darts_total, missed, extra, fits = [], [], [], 0, 0, 0, 0, 0
    seconds = 0.0
    for b in range(0, count, batch):
        chunk = samples[b : b + batch]
        t = time.time()
        preds = model.predict([s.image[..., ::-1].copy() for s in chunk], threshold=0.01, include_source_image=False)
        seconds += time.time() - t
        for s, kp in zip(chunk, preds):
            cal, conf, darts = decode(kp, dart_threshold)
            vis = s.calibration_visible
            px_err.extend(np.linalg.norm(cal[vis] - s.calibration_px[vis], axis=1))
            keep = conf > 0.3
            if keep.sum() < 4:
                missed += len(s.darts_mm)
                darts_total += len(s.darts_mm)
                continue
            h, _ = cv2.findHomography(cal[keep], CALIBRATION_MM[keep], cv2.RANSAC, 3.0)
            if h is None:
                missed += len(s.darts_mm)
                darts_total += len(s.darts_mm)
                continue
            fits += 1
            mapped = cv2.perspectiveTransform(s.calibration_px[None].astype(np.float64), h)[0]
            board_mm.extend(np.linalg.norm(mapped - CALIBRATION_MM, axis=1))
            found = cv2.perspectiveTransform(darts[None], h)[0] if len(darts) else np.zeros((0, 2))
            used = set()
            darts_total += len(s.darts_mm)
            for truth in s.darts_mm:
                if len(found) == 0:
                    missed += 1
                    continue
                d = np.linalg.norm(found - truth, axis=1)
                j = int(d.argmin())
                if d[j] > 15 or j in used:
                    missed += 1
                    continue
                used.add(j)
                dart_mm.append(d[j])
                exact += score(*found[j]) == score(*truth)
            extra += len(found) - len(used)
    pct = lambda a, q: float(np.percentile(a, q)) if len(a) else math.nan
    return {
        "images": count,
        "max_tilt": max_tilt,
        "dart_threshold": dart_threshold,
        "homography_fits": fits,
        "calib_px_median": pct(px_err, 50),
        "calib_px_p90": pct(px_err, 90),
        "board_mm_median": pct(board_mm, 50),
        "board_mm_p90": pct(board_mm, 90),
        "darts": darts_total,
        "darts_missed": missed,
        "darts_found_pct": round(100 * (1 - missed / darts_total), 1) if darts_total else math.nan,
        "darts_extra": extra,
        "dart_mm_median": pct(dart_mm, 50),
        "dart_mm_p90": pct(dart_mm, 90),
        "dart_score_exact": exact / darts_total if darts_total else math.nan,
        "gpu_ms_per_image": round(1000 * seconds / count, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--dart-threshold", type=float, default=0.5)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    model = RFDETRKeypointPreview(pretrain_weights=str(args.weights), num_keypoints_per_class=[80, 1], num_classes=2, num_queries=30, num_select=30)
    with torch.no_grad():
        results = [evaluate(model, args.size, 500, 55.0, args.dart_threshold), evaluate(model, args.size, 300, 35.0, args.dart_threshold)]
    print(json.dumps(results, indent=1), flush=True)
    args.out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
