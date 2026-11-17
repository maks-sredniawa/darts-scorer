import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

from darts_ml.board import score
from m2_spike.model import CHANNELS, STRIDE, PointNet, focal_loss
from m2_spike.synth import CALIBRATION_MM, NUM_CALIBRATION, Renderer

MEAN = np.array([0.485, 0.456, 0.406], np.float32) * 255
STD = np.array([0.229, 0.224, 0.225], np.float32) * 255
SIGMA = 1.5


def to_tensor(image_bgr: np.ndarray) -> torch.Tensor:
    rgb = image_bgr[..., ::-1].astype(np.float32)
    return torch.from_numpy(((rgb - MEAN) / STD).transpose(2, 0, 1).copy())


def targets(sample, size: int):
    out = size // STRIDE
    heat = np.zeros((CHANNELS, out, out), np.float32)
    points, channels = [], []
    for i in range(NUM_CALIBRATION):
        if sample.calibration_visible[i]:
            points.append(sample.calibration_px[i])
            channels.append(i)
    for p in sample.darts_px:
        if 0 <= p[0] < size and 0 <= p[1] < size:
            points.append(p)
            channels.append(NUM_CALIBRATION)
    ys, xs = np.mgrid[0:out, 0:out].astype(np.float32)
    offset = np.zeros((2, out, out), np.float32)
    offset_mask = np.zeros((out, out), np.float32)
    for (px, py), c in zip(points, channels):
        cx, cy = px / STRIDE - 0.5, py / STRIDE - 0.5
        ix, iy = int(round(cx)), int(round(cy))
        if not (0 <= ix < out and 0 <= iy < out):
            continue
        g = np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * SIGMA**2))
        heat[c] = np.maximum(heat[c], g)
        heat[c, iy, ix] = 1.0
        offset[:, iy, ix] = (cx - ix, cy - iy)
        offset_mask[iy, ix] = 1.0
    return heat, offset, offset_mask


class Synthetic(IterableDataset):
    def __init__(self, size: int, seed: int):
        self.size, self.seed = size, seed

    def __iter__(self):
        info = get_worker_info()
        cv2.setNumThreads(1)
        torch.set_num_threads(1)
        renderer = Renderer(self.seed + (info.id if info else 0) * 7919 + int(time.time()), self.size)
        while True:
            s = renderer.sample()
            heat, offset, mask = targets(s, self.size)
            yield to_tensor(s.image), torch.from_numpy(heat), torch.from_numpy(offset), torch.from_numpy(mask)


def decode(heat_logits: torch.Tensor, offset: torch.Tensor, dart_threshold: float = 0.3, max_darts: int = 6):
    heat = torch.sigmoid(heat_logits)
    c, h, w = heat.shape
    flat = heat[:NUM_CALIBRATION].reshape(NUM_CALIBRATION, -1)
    conf, idx = flat.max(1)
    iy, ix = idx // w, idx % w
    ox, oy = offset[0, iy, ix], offset[1, iy, ix]
    calibration = torch.stack([(ix + ox + 0.5) * STRIDE, (iy + oy + 0.5) * STRIDE], 1)
    dart = heat[NUM_CALIBRATION]
    peaks = (dart == torch.nn.functional.max_pool2d(dart[None, None], 3, 1, 1)[0, 0]) & (dart > dart_threshold)
    dy, dx = torch.nonzero(peaks, as_tuple=True)
    order = dart[dy, dx].argsort(descending=True)[:max_darts]
    dy, dx = dy[order], dx[order]
    darts = torch.stack([(dx + offset[0, dy, dx] + 0.5) * STRIDE, (dy + offset[1, dy, dx] + 0.5) * STRIDE], 1)
    return calibration.cpu().numpy(), conf.cpu().numpy(), darts.cpu().numpy(), dart[dy, dx].cpu().numpy()


def evaluate(model, size: int, count: int, device, max_tilt: float = 55.0) -> dict:
    model.eval()
    renderer = Renderer(12345, size, max_tilt=max_tilt)
    px_err, board_mm, dart_mm, exact, darts_total, missed, extra, fits = [], [], [], 0, 0, 0, 0, 0
    with torch.no_grad():
        for _ in range(count):
            s = renderer.sample()
            heat, off = model(to_tensor(s.image)[None].to(device))
            cal, conf, darts, _ = decode(heat[0], off[0])
            vis = s.calibration_visible
            px_err.extend(np.linalg.norm(cal[vis] - s.calibration_px[vis], axis=1))
            keep = conf > 0.3
            if keep.sum() < 4:
                missed += len(s.darts_mm)
                darts_total += len(s.darts_mm)
                continue
            h, _ = cv2.findHomography(cal[keep].astype(np.float64), CALIBRATION_MM[keep], cv2.RANSAC, 3.0)
            if h is None:
                missed += len(s.darts_mm)
                darts_total += len(s.darts_mm)
                continue
            fits += 1
            truth_px = s.calibration_px
            mapped = cv2.perspectiveTransform(truth_px[None].astype(np.float64), h)[0]
            board_mm.extend(np.linalg.norm(mapped - CALIBRATION_MM, axis=1))
            found = cv2.perspectiveTransform(darts[None].astype(np.float64), h)[0] if len(darts) else np.zeros((0, 2))
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
    model.train()
    pct = lambda a, q: float(np.percentile(a, q)) if len(a) else math.nan
    return {
        "images": count,
        "homography_fits": fits,
        "calib_px_median": pct(px_err, 50),
        "calib_px_p90": pct(px_err, 90),
        "board_mm_median": pct(board_mm, 50),
        "board_mm_p90": pct(board_mm, 90),
        "darts": darts_total,
        "darts_missed": missed,
        "darts_extra": extra,
        "dart_mm_median": pct(dart_mm, 50),
        "dart_mm_p90": pct(dart_mm, 90),
        "dart_score_exact": exact / darts_total if darts_total else math.nan,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--backbone", default="mobilenetv4_conv_small.e2400_r224_in1k")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--eval-images", type=int, default=300)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True
    model = PointNet(args.backbone).to(device)
    params = sum(p.numel() for p in model.parameters())
    print(f"params {params / 1e6:.2f} M", flush=True)
    loader = DataLoader(Synthetic(args.size, 1), batch_size=args.batch, num_workers=args.workers, pin_memory=True, persistent_workers=True, prefetch_factor=4)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    scaler = torch.amp.GradScaler()
    deadline = time.time() + args.minutes * 60
    start, step = time.time(), 0
    log = open(args.out / "log.jsonl", "a")
    for image, heat, offset, mask in loader:
        frac = min(1.0, (time.time() - start) / (args.minutes * 60))
        for g in opt.param_groups:
            g["lr"] = 2e-3 * (min(1.0, step / 300)) * 0.5 * (1 + math.cos(math.pi * frac))
        image, heat, offset, mask = (t.to(device, non_blocking=True) for t in (image, heat, offset, mask))
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits, off = model(image)
        logits, off = logits.float(), off.float()
        loss_heat = focal_loss(logits, heat)
        loss_off = (torch.abs(off - offset).sum(1) * mask).sum() / mask.sum().clamp(min=1)
        loss = loss_heat + loss_off
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()
        step += 1
        if step % 200 == 0:
            rate = step * args.batch / (time.time() - start)
            row = {"step": step, "min": round((time.time() - start) / 60, 1), "loss": round(loss.item(), 4), "heat": round(loss_heat.item(), 4), "off": round(loss_off.item(), 4), "img_s": round(rate)}
            print(json.dumps(row), flush=True)
            log.write(json.dumps(row) + "\n")
            log.flush()
        if time.time() > deadline:
            break
    torch.save(model.state_dict(), args.out / "model.pt")
    result = evaluate(model, args.size, args.eval_images, device)
    result.update({"steps": step, "minutes": args.minutes, "params_m": round(params / 1e6, 2), "size": args.size, "backbone": args.backbone})
    print(json.dumps(result, indent=1), flush=True)
    (args.out / "eval.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
