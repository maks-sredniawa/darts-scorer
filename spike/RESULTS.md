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

## Candidate B: RF-DETR keypoint

`RFDETRKeypointPreview` from `rfdetr` 1.12.1 (Apache-2.0 package only, no `rfdetr_plus`), its Apache
pretrained `rf-detr-keypoint-preview-xlarge.pth`, `num_keypoints_per_class=[80, 1]`: a `board` with
the 80 named Calibration points and a `dart` with its Entry point. Code in `rfdetr/`, its own uv
project; `rfdetr/tflite/` is a second one for the export (see *What broke*).

- **Data:** 6000 train / 500 valid renders at 512 px written as COCO keypoints (seeds 100000+ and
  200000+). Board box: the visible Calibration points' bbox padded 8 px; points outside the image
  `v=0`, under a dart `v=1`, else `v=2`. Dart box: 32 px square on the Entry point (the renderer
  does not expose the shaft). No flip augmentation (no left/right pairs among the point names).
- **Training:** 576 px (the checkpoint's own size), batch 2 × 8 accumulation, 30 queries instead
  of 100, gradient checkpointing, bf16. Batch 8 and batch 4 run out of 8 GB even with checkpointing:
  the decoder carries 80 keypoint tokens for each of 30 × 13 group-DETR queries. 2.9 it/s =
  5.8 img/s (candidate A: ~100), so 35 minutes is 2 epochs. Keypoint mAP50:95 on valid 0.23 → 0.26.
- **Evaluation:** the same metrics as `evaluate()` (`rfdetr/src/m2_rfdetr/evaluate.py`). Board
  keypoints from the top `board` detection, confidence = the keypoint's findable sigmoid > 0.3;
  Darts are `dart` detections above `predict()`'s default threshold, 0.5.

| Training | Board mm at the wires, median / p90 | Darts found | Extra | Dart mm, median / p90 | Score exact |
| --- | --- | --- | --- | --- | --- |
| 35 min, tilt ≤ 55° (500) | 199 / 785 | 1% | 2659 | 10.9 / 14.8 | 0.5% |
| 35 min, tilt ≤ 35° (300) | 198 / 754 | 0.7% | 1639 | 5.2 / 8.2 | 0.7% |

It has not learned the board yet. The 80 points come back clustered near the centre (their spread
is ~40% of the true one; calibration error 98 px median), so no homography is usable. Dart Entry
points are found in pixels, with several queries piling onto each Dart (no NMS, one-to-one matching
not converged), which the "Extra" column counts. A fair run needs hours of GPU, not 35 minutes.

| | Params | Model MB | Emulator ms, 4 threads | vs PyTorch, keypoints max | GPU ms (3070, `predict()` in batches of 16) |
| --- | --- | --- | --- | --- | --- |
| A, fp32 / fp16 | 1.55 M | 6.3 / 3.1 | 70 / 70 | 1.5e-6 / 7.3e-4 (heatmap) | — |
| B, fp32 | 40.5 M | 151 | 1990 | 2.9 (board points ~5.6 px median, 34 px max) | 25 |
| B, fp16 | | 76 | 1980 | 3.1 | |
| B, dynamic int8 | | 48 | 2310 | 14.3 | |

- **Export:** `model.export(format="tflite", quantization="int8")` (onnx2tf) writes all three in
  16 minutes. The ONNX matches PyTorch (6.7e-4); the **onnx2tf step** loses it: boxes still match
  (1.2e-5) but the board's keypoints move 5.6 px median, 34 px max at 512, and the class logits by
  2. RF-DETR's docs report 3.2e-3 on the 17-point pretrained schema; an 80-point schema does not get
  that. Host LiteRT takes ~600 ms per image on 4 threads.
- **On the emulator:** `RfDetrOnDeviceTest` (same pixel-api36 x86_64 emulator, same session where A
  still measured 70 ms) runs all three; fp32 boxes match host LiteRT to 5e-7, its keypoint channels
  to 0.31. About 28× slower than A, and 151 / 76 / 48 MB against ADR-0008's 5–20 MB.

### What broke

- `rfdetr[tflite]` pins onnx2tf 2.4.x, which pins **numpy 1.26.4**; `darts-ml` needs numpy ≥ 2.5. So
  training and evaluation live in `rfdetr/` (with `m2-spike` and `darts-ml` by path) and the export
  in `rfdetr/tflite/`, a venv of its own that reads a saved render.
- The export path needs the `LWDETR` module switched with `rfdetr.export._backend._switch_to_export_mode`
  before a PyTorch reference forward; without it the forward returns the training dict.
- The keypoint output is `[1, 30, 160, 8]`: 160 slots for an 80-point schema (why 160 is not
  checked), x and y normalised to the input, then the findable logit and the precision Cholesky
  terms among the other six. The dynamic-int8 file names its outputs
  `StatefulPartitionedCall:N` in a different order from fp32/fp16: match outputs by shape.
