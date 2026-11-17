import argparse
import json
import time
from pathlib import Path

from rfdetr import RFDETRKeypointPreview


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--resolution", type=int, default=576)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--queries", type=int, default=100)
    ap.add_argument("--checkpointing", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    model = RFDETRKeypointPreview(num_keypoints_per_class=[80, 1], num_classes=2, resolution=args.resolution, num_queries=args.queries, num_select=args.queries, gradient_checkpointing=args.checkpointing)
    params = sum(p.numel() for p in model.model.model.parameters())
    print(f"params {params / 1e6:.2f} M", flush=True)
    start = time.time()
    model.train(
        dataset_dir=str(args.data),
        output_dir=str(args.out),
        epochs=args.epochs,
        batch_size=args.batch,
        grad_accum_steps=args.accum,
        num_workers=args.workers,
        aug_config={},
        multi_scale=False,
        class_names=["board", "dart"],
        tensorboard=False,
        progress_bar="tqdm",
        device="cuda",
        skip_best_epochs=0,
        checkpoint_interval=1,
    )
    minutes = (time.time() - start) / 60
    (args.out / "train.json").write_text(json.dumps({"params_m": round(params / 1e6, 2), "train_minutes": round(minutes, 1), **{k: v for k, v in vars(args).items() if k not in ("data", "out")}}, indent=1))
    print(f"trained in {minutes:.1f} min", flush=True)


if __name__ == "__main__":
    main()
