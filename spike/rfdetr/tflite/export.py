import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
import torch
import torch.nn.functional as F

from rfdetr import RFDETRKeypointPreview
from rfdetr.export._backend import _switch_to_export_mode
from rfdetr.export.prepare import prepare_export_graph

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def preprocess(rgb_uint8: np.ndarray, resolution: int) -> torch.Tensor:
    x = torch.from_numpy(rgb_uint8.astype(np.float32) / 255.0).permute(2, 0, 1)[None]
    x = F.interpolate(x, size=(resolution, resolution), mode="bilinear", align_corners=False)
    return (x - torch.from_numpy(MEAN)[None, :, None, None]) / torch.from_numpy(STD)[None, :, None, None]


def run_tflite(path: Path, nchw: torch.Tensor) -> dict:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=4)
    interpreter.allocate_tensors()
    (inp,) = interpreter.get_input_details()
    x = nchw.numpy()
    if inp["shape"][-1] == 3:
        x = x.transpose(0, 2, 3, 1)
    interpreter.set_tensor(inp["index"], np.ascontiguousarray(x, np.float32))
    interpreter.invoke()
    t = time.time()
    for _ in range(3):
        interpreter.invoke()
    ms = (time.time() - t) / 3 * 1000
    outs = {d["name"]: interpreter.get_tensor(d["index"]) for d in interpreter.get_output_details()}
    return {"input_shape": [int(v) for v in inp["shape"]], "outputs": outs, "host_ms_4_threads": round(ms, 1)}


def by_shape(outputs: dict, ref: dict) -> dict:
    matched = {}
    for name, ref_value in ref.items():
        hits = [v for v in outputs.values() if tuple(v.shape) == tuple(ref_value.shape)]
        matched[name] = hits[0] if hits else None
    return matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--render", type=Path, required=True, help="RGB uint8 .npy of one render")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--queries", type=int, default=30)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    model = RFDETRKeypointPreview(pretrain_weights=str(args.weights), num_keypoints_per_class=[80, 1], num_classes=2, num_queries=args.queries, num_select=args.queries)
    resolution = model.model_config.resolution
    x = preprocess(np.load(args.render), resolution)

    reference = copy.deepcopy(model.model.model).cpu()
    graph = prepare_export_graph(reference, model.model_config, shape=(resolution, resolution), device="cpu")
    _switch_to_export_mode(graph.model)
    with torch.no_grad():
        ref = dict(zip(graph.output_names, (o.numpy() for o in graph.model(x))))
    report = {"resolution": resolution, "params_m": round(sum(p.numel() for p in reference.parameters()) / 1e6, 2), "pytorch_shapes": {k: list(v.shape) for k, v in ref.items()}}

    t = time.time()
    exported = model.export(output_dir=str(args.out), format="tflite", quantization="int8", verbose=False)
    report["export_seconds"] = round(time.time() - t)
    report["export_returned"] = str(exported)

    nhwc = x.permute(0, 2, 3, 1).contiguous().numpy()
    nhwc.astype("<f4").tofile(args.out / "rfdetr_input.bin")
    for name, value in ref.items():
        value.astype("<f4").tofile(args.out / f"rfdetr_{name}.bin")

    for path in sorted(args.out.rglob("*.tflite")):
        result = run_tflite(path, x)
        matched = by_shape(result["outputs"], ref)
        report[path.name] = {
            "mb": round(path.stat().st_size / 1e6, 2),
            "input_shape": result["input_shape"],
            "output_shapes": {k: list(v.shape) for k, v in result["outputs"].items()},
            "host_ms_4_threads": result["host_ms_4_threads"],
            "max_diff": {k: (float(np.abs(v - ref[k]).max()) if v is not None else "no output of this shape") for k, v in matched.items()},
        }
    print(json.dumps(report, indent=1))
    (args.out / "export.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
