import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from m2_spike.model import PointNet
from m2_spike.synth import Renderer
from m2_spike.train import to_tensor


class Exported(torch.nn.Module):
    def __init__(self, net: PointNet):
        super().__init__()
        self.net = net

    def forward(self, x):
        heat, offset = self.net(x)
        return torch.sigmoid(heat), offset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    net = PointNet(pretrained=False)
    net.load_state_dict(torch.load(args.weights, map_location="cpu"))
    model = Exported(net).eval()
    sample = to_tensor(Renderer(7, args.size).sample().image)[None]
    with torch.no_grad():
        ref_heat, ref_off = model(sample)
    report = {}

    onnx_path = args.out / "pointnet.onnx"
    torch.onnx.export(model, (sample,), onnx_path, input_names=["image"], output_names=["heat", "offset"], dynamo=True)
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    heat, off = session.run(None, {"image": sample.numpy()})
    t = time.time()
    for _ in range(10):
        session.run(None, {"image": sample.numpy()})
    report["onnx"] = {"mb": round(onnx_path.stat().st_size / 1e6, 2), "max_heat_diff": float(np.abs(heat - ref_heat.numpy()).max()), "host_cpu_ms": round((time.time() - t) / 10 * 1000, 1)}

    import litert_torch

    nhwc = sample.permute(0, 2, 3, 1).contiguous()

    class Nhwc(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, x):
            return self.inner(x.permute(0, 3, 1, 2))

    edge = litert_torch.convert(Nhwc(model).eval(), (nhwc,))
    tflite_path = args.out / "pointnet_fp32.tflite"
    edge.export(str(tflite_path))
    heat_t, off_t = edge(nhwc)
    report["tflite_fp32"] = {"mb": round(tflite_path.stat().st_size / 1e6, 2), "max_heat_diff": float(np.abs(np.asarray(heat_t) - ref_heat.numpy()).max())}

    try:
        from litert_torch.generative.quantize import quant_recipes

        q = litert_torch.convert(Nhwc(model).eval(), (nhwc,), quant_config=quant_recipes.full_fp16_recipe())
        fp16_path = args.out / "pointnet_fp16.tflite"
        q.export(str(fp16_path))
        heat_q, _ = q(nhwc)
        report["tflite_fp16"] = {"mb": round(fp16_path.stat().st_size / 1e6, 2), "max_heat_diff": float(np.abs(np.asarray(heat_q) - ref_heat.numpy()).max())}
    except Exception as e:
        report["tflite_fp16"] = {"error": f"{type(e).__name__}: {e}"[:300]}

    print(json.dumps(report, indent=1))
    (args.out / "export.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
