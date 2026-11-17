import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from darts_ml.board import CALIBRATION_POINTS
from m2_spike.synth import NUM_CALIBRATION, Renderer

BOARD_PAD_PX = 8
DART_BOX_PX = 32
CATEGORIES = [
    {"id": 1, "name": "board", "supercategory": "darts", "keypoints": [p.name for p in CALIBRATION_POINTS], "skeleton": []},
    {"id": 2, "name": "dart", "supercategory": "darts", "keypoints": ["entry"], "skeleton": []},
]


def _box(lo, hi, size):
    lo = np.clip(lo, 0, size - 1)
    hi = np.clip(hi, 0, size - 1)
    return [float(lo[0]), float(lo[1]), float(hi[0] - lo[0]), float(hi[1] - lo[1])]


def annotate(sample, size: int):
    cal = sample.calibration_px
    inside = np.all((cal >= 0) & (cal < size), axis=1)
    rows = []
    if inside.sum() >= 1:
        kps = []
        for i in range(NUM_CALIBRATION):
            v = 0 if not inside[i] else (2 if sample.calibration_visible[i] else 1)
            x, y = (cal[i] if inside[i] else (0.0, 0.0))
            kps += [float(x), float(y), v]
        bbox = _box(cal[inside].min(0) - BOARD_PAD_PX, cal[inside].max(0) + BOARD_PAD_PX, size)
        rows.append({"category_id": 1, "bbox": bbox, "keypoints": kps, "num_keypoints": int(inside.sum())})
    for p in sample.darts_px:
        if not (0 <= p[0] < size and 0 <= p[1] < size):
            continue
        bbox = _box(p - DART_BOX_PX / 2, p + DART_BOX_PX / 2, size)
        rows.append({"category_id": 2, "bbox": bbox, "keypoints": [float(p[0]), float(p[1]), 2], "num_keypoints": 1})
    return rows


def _render_chunk(args):
    seed, count, size, folder, first_id = args
    cv2.setNumThreads(1)
    renderer = Renderer(seed, size)
    images, anns = [], []
    for k in range(count):
        image_id = first_id + k
        s = renderer.sample()
        name = f"{image_id:06d}.jpg"
        cv2.imwrite(str(folder / name), s.image, [cv2.IMWRITE_JPEG_QUALITY, 97])
        images.append({"id": image_id, "file_name": name, "width": size, "height": size})
        for row in annotate(s, size):
            row.update({"image_id": image_id, "iscrowd": 0, "area": row["bbox"][2] * row["bbox"][3]})
            anns.append(row)
    return images, anns


def write_split(root: Path, split: str, count: int, size: int, base_seed: int, workers: int):
    folder = root / split
    folder.mkdir(parents=True, exist_ok=True)
    per = -(-count // workers)
    jobs = [(base_seed + w, min(per, count - w * per), size, folder, w * per) for w in range(workers) if count - w * per > 0]
    images, anns = [], []
    with ProcessPoolExecutor(workers) as pool:
        for imgs, rows in pool.map(_render_chunk, jobs):
            images += imgs
            anns += rows
    for i, a in enumerate(anns):
        a["id"] = i + 1
    (folder / "_annotations.coco.json").write_text(json.dumps({"images": images, "annotations": anns, "categories": CATEGORIES}))
    print(split, len(images), "images", len(anns), "annotations", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--train", type=int, default=6000)
    ap.add_argument("--val", type=int, default=500)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    write_split(args.out, "train", args.train, args.size, 100_000, args.workers)
    write_split(args.out, "valid", args.val, args.size, 200_000, args.workers)
    write_split(args.out, "test", 50, args.size, 300_000, 4)


if __name__ == "__main__":
    main()
