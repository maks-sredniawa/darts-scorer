# M2 toolchain trial — results

Throwaway trial on 2026-11-17, never merged. Its findings go into `docs/phase-M2.md`.

Candidate research (sources, licences, why MMPose is out): `CANDIDATES.md`.

## Candidate A: timm MobileNetV4-Conv-Small + heatmap head

- 81 heatmap channels (the 80 named Calibration points from `darts_ml.board`, plus Entry points) and a
  2-channel sub-pixel offset, at stride 4. 1.55 M parameters, ~4 GMACs at 512 px (most of it in the
  full-width 3×3 head at stride 4: a depthwise head would cut that).
- Trained only on `synth.py`'s renders: a regulation board under a random handheld perspective (tilt
  up to 55°), 0–3 darts drawn in 3D, photometric noise and JPEG. RTX 3070, ~100 img/s, data-bound
  (GPU ~18%).
- Evaluated on 500 renders from a fixed seed; homography by RANSAC over points with confidence > 0.3;
  a Dart matches within 15 mm.

| Training | Board mm at the wires, median / p90 | Darts found | Extra | Dart mm, median / p90 | Score exact |
| --- | --- | --- | --- | --- | --- |
| 3 min | 0.11 / 0.33 | 67% | 403 | 3.6 / 10.3 | 49% |
| 20 min | 0.04 / 0.13 | 96% | 134 | 2.0 / 4.7 | 81% |

Synthetic renders are far easier than photos: no lens distortion, no real darts, a clean board.
These numbers prove the pipeline, not the accuracy on real Photos.

## Export and on-device run

- `torch.onnx.export` (dynamo) and `litert-torch` 0.10.0 both convert it. LiteRT fp32 6.3 MB,
  fp16 3.1 MB; both match PyTorch (1.5e-6 and 7.3e-4 on the heatmap).
- `PointNetOnDeviceTest` loads each `.tflite` with `com.google.ai.edge.litert:litert:2.3.2` on a
  pixel-api36 x86_64 emulator (AGP 9.0.1, minSdk 26 app) and checks it against PyTorch: passes.
  70 ms per 512 px image on 4 threads of an emulated x86 CPU — not a phone figure.
- Outputs are NCHW (`[1, 81, 128, 128]`, `[1, 2, 128, 128]`); the input is NHWC float32.

## Gotchas

- `uv add litert-torch` pins torch 2.14.1; changing the venv under a running training broke its
  final evaluation (`CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH`). Install before training.
- OpenCV and torch threads must be 1 per DataLoader worker, or 16 workers oversubscribe 20 cores.
- Google no longer publishes `benchmark_model` for x86_64 Android; the instrumented test replaces it.
