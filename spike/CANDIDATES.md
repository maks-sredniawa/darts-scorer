# M2 candidates: permissive keypoint detectors for the on-device darts model

Checked 2026-11-17 against primary sources (GitHub repos and their source, PyPI, Maven, model cards,
arXiv). Anything not read from a primary source is marked **unverified**. Inputs: ADR-0008 and
`docs/phase-M1.md` (80 named Calibration points `<ring>-<a>-<b>`, variable Entry points, 1–2 mm
on a wire, model budget "roughly 5–20 MB").

## Three findings that apply to every candidate

1. **The Calibration points are named, so the model must name them.** A homography needs
   correspondences: which pixel is `do-20-1`. A detector with only two classes ("calibration",
   "dart") returns 80 unlabelled dots, and the app would have to work out which is which (ellipse
   fit + ordering + a rotation anchor from the 20). DeepDarts avoided that by giving each of its four
   points its own class. Three shapes keep the names in the model:
   - **81 detection classes** (80 named points + Entry point), each point a small fixed-size box.
     COCO detectors already train 80 classes, so this is ordinary.
   - **81 heatmap channels** (CenterNet / DeepDarts style): one channel per named point, one for
     Entry points; peaks plus a sub-pixel offset head.
   - **A pose model with two instance classes**: a *board* instance with 80 keypoints (each with a
     visibility score, so a dart covering one is fine) and a *dart* instance with 1 keypoint (or 2:
     entry and flight). Only RF-DETR supports per-class keypoint counts natively (below).
2. **Precision drives input size more than the framework does (estimate, unverified).** A board
   filling ~500 px of a 640 px input gives ~0.7 mm/px, so 1–2 mm needs ≲1.5–3 px error. Stride-4
   heatmaps with an offset head are the usual way to get sub-pixel points; box-centre regression and
   DETR L1 regression are typically a few px. Expect M2 to need either a larger input (800–1024) or
   a second pass on a board crop, whichever framework wins.
3. **Licences drift; pin the commit.** Two Apache projects relicensed to non-commercial in 2026:
   DEIMv2 (LICENSE now "All rights reserved" custom
   [DEIMv2 License](https://github.com/Intellindust-AI-Lab/DEIMv2)) and EdgeCrafter (Apache →
   non-commercial on 2026-08-20, commit
   [e0656d4](https://github.com/Intellindust-AI-Lab/EdgeCrafter/commit/e0656d44b80ecb97ba96bb8a804a741169431e0f),
   recorded in LibreYOLO's
   [provenance note](https://github.com/LibreYOLO/libreyolo/blob/main/docs/provenance/edgecrafter.md)).
   Record the LICENSE text at the pinned commit in `ml/README.md`'s licence table.
   **Dataset caveat (unverified, applies to all):** every pretrained checkpoint below was trained on
   COCO (annotations CC BY 4.0, images under their Flickr licences), ImageNet-1k (research-only image
   terms) and/or Objects365. No primary source settles whether those terms reach the weights; the
   projects license the weights Apache/MIT and the industry treats them so. Training from scratch is
   the only way around it and is a poor fit for ~540 training Photos.

## Candidates

### 1. MMPose — RTMPose, RTMO (and RTMDet / YOLOX-Pose through MMDetection)

- **Maintenance:** last release **mmpose v1.3.2, 2024-07-12**
  ([releases](https://github.com/open-mmlab/mmpose/releases)); last commits on `main` 2025-08-04
  (three doc/small fixes), before that 2024-08-07
  ([commits](https://github.com/open-mmlab/mmpose/commits/main)). MMDetection last release v3.3.0,
  2024-01-05; MMDeploy last release v1.3.1, 2023-12-25, last commit 2024-09-30 (GitHub API).
  Effectively dormant.
- **Install on Python 3.12 + CUDA 12.x — checked, it is a trap:**
  - mmcv on PyPI is an sdist only (2.2.0, 2024-04-24). OpenMMLab's prebuilt wheels for **cp312
    exist only for mmcv 2.2.0, torch 2.2–2.4, cu118/cu121**; nothing for torch ≥2.5 or CUDA >12.1
    (listing of `download.openmmlab.com/mmcv/dist/{cu}/torch{v}/index.html`). mmcv 2.1.0 has no
    cp312 wheel at all (cp38–cp311 only).
  - **MMDetection refuses mmcv 2.2.0:** `mmdet/__init__.py` has `mmcv_maximum_version = '2.2.0'`
    with a strict `<` assert, and mmpose's `mminstall.txt` pins `mmdet>=3.0.0,<3.3.0`.
    RTMO needs mmdet (`rtmo_head.py`: `from mmdet.utils import ConfigType, reduce_mean`), and even
    RTMPose's configs build the CSPNeXt backbone with `_scope_='mmdet'`. So on 3.12 the only path is
    to patch mmdet's assert; on 3.11 it is torch 2.1 + mmcv 2.1.0 (2023 stack).
  - **`chumpy`** (a hard runtime requirement of mmpose, last release 0.70 in 2020, sdist only)
    **fails to build under uv on Python 3.12**: `ModuleNotFoundError: No module named 'pip'` (tried
    here in a throwaway venv). `xtcocotools` has no cp312 wheel either (cp37–cp311), so it compiles.
    Workarounds: `--no-deps`/override chumpy; it is unused for 2D.
- **Keypoint fit:** RTMPose is top-down (needs a detector first) with a fixed skeleton; RTMO is
  one-stage multi-person with a fixed K and `num_classes=1`
  ([config](https://github.com/open-mmlab/mmpose/blob/main/configs/body_2d_keypoint/rtmo/coco/rtmo-s_8xb32-600e_coco-640x640.py)).
  Board = one instance with K=80 fits. Darts do not, except by a hack: K=81 with board instances
  using only 1–80 and dart instances only #81 via visibility masks (**unverified** that the
  OKS/MLE losses behave). RTMDet/YOLOX-Pose: points as boxes / same fixed-K story.
- **Export to Android:** RTMPose has a documented ncnn path and Android ncnn examples
  ([RTMPose project](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)).
  **RTMO is ONNX Runtime/TensorRT only; ncnn and OpenVINO are "N"** in MMDeploy's own table, as is
  ncnn for YOLOX-Pose
  ([mmdeploy mmpose.md](https://github.com/open-mmlab/mmdeploy/blob/main/docs/en/04-supported-codebases/mmpose.md)).
  No TFLite route documented for RTMO (**unverified** whether onnx2tf converts it). Inference
  without mmcv: [rtmlib](https://github.com/Tau-J/rtmlib) (Apache-2.0, active, 0.0.16 2026-08,
  ONNX Runtime/OpenCV/OpenVINO). INT8/FP16: FP16 via ncnn/TensorRT configs; INT8 via MMDeploy only.
- **Licence:** code Apache-2.0 (repo LICENSE). Checkpoints carry no separate licence; the project
  pages state none ([RTMO](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmo)). RTMO-s
  initialises from the MMDetection YOLOX-s COCO checkpoint (Apache repo). The "body7/Body8"
  checkpoints are trained on AI Challenger, CrowdPose, Halpe, MPII, PoseTrack18, sub-JHMDB too:
  avoid them, start from the COCO-only ones.
- **Phone cost:** RTMPose-t 3.34 M params / 0.36 GFLOPs at 256×192, **9.02 ms ncnn-FP16 on a
  Snapdragon 865**; RTMPose-s 5.47 M / 0.68 G / 13.89 ms (RTMPose page — the only primary-source
  mobile latency in this report, but for a 256×192 crop, not a 640 board). RTMO-s **9.9 M params**,
  640 input, 48.7–65.3 ms ONNX Runtime on a Xeon CPU; FLOPs not reported
  ([arXiv 2312.07526](https://arxiv.org/abs/2312.07526) Tables 1 and 4). RTMDet-tiny 4.8 M / 8.1 G,
  RTMDet-s 8.89 M / 14.8 G at 640
  ([RTMDet README](https://github.com/open-mmlab/mmdetection/tree/main/configs/rtmdet)).

### 2. YOLOX (Megvii)

- **Maintenance:** last release **0.3.0, 2022-04-22**; last commit 2025-06-08 (a doc typo)
  (GitHub API). Dormant but small and self-contained.
- **Install:** `requirements.txt` pins **`onnx-simplifier==0.4.10`, which has wheels only up to
  cp310** (PyPI), so a plain install on 3.12 tries to compile it. Install with `--no-deps` and a
  current `onnxsim`. `setup.py` builds optional C++ ops only if torch is importable. No torch upper
  bound. Works on current torch: **unverified** here (not run).
- **Keypoint fit:** boxes only. Points as small boxes, **81 classes** (80 named points + Entry
  point), score = the box centre. Variable count and occlusion are natural (a hidden point is simply
  not detected). Precision limited by box-centre regression at stride 8 (**unverified** how close to
  1–2 mm).
- **Export:** ONNX, TensorRT, OpenVINO, MegEngine and an **ncnn C++ and Android demo** in-repo
  (`demo/ncnn/android`); release assets include `yolox_s_ncnn.tar.gz` and ONNX files
  ([releases](https://github.com/Megvii-BaseDetection/YOLOX/releases)). TFLite via onnx2tf:
  **unverified**. INT8/FP16: ncnn FP16 by default; INT8 via ncnn/ORT tooling (generic, unverified
  for YOLOX).
- **Licence:** code Apache-2.0; weights are GitHub release assets of the same Apache repo, no
  separate weight licence. LibreYOLO lists them as Apache-2.0
  ([LICENSE_NOTICE](https://github.com/LibreYOLO/libreyolo/blob/main/weights/LICENSE_NOTICE.txt)).
- **Phone cost:** Nano 0.91 M / 1.08 GFLOPs at 416; Tiny 5.06 M / 6.45 G at 416; S 9.0 M / 26.8 G
  at 640 ([README](https://github.com/Megvii-BaseDetection/YOLOX)). No mobile latency published.

### 3. MultimediaTechLab/YOLO (YOLOv9, MIT)

- **Maintenance:** release **v1.0, 2025-12-30** (no notes, no assets); last push 2026-03-16;
  weights only in `v1.0-alpha` (2024-06-03: `v9-t/s/m/c.pt`, `v7.pt`, `rd-9c.pt`).
  `requires-python >=3.6`, unpinned torch: no install blocker found (not run, **unverified**).
- **Keypoint fit:** detection (plus `v9-c-seg`, `v9-c-cls` configs). **No pose head.** Same
  "81 classes of small boxes" mapping as YOLOX.
- **Export:** in-repo only ONNX and TensorRT (`yolo/utils/deploy_utils.py`). No TFLite/ncnn path.
  [LibreYOLO](https://github.com/LibreYOLO/libreyolo) ports this code (MIT, commit c4cb5f6f) and marks
  yolo9 detect export to ONNX, TFLite, ncnn as "parity-validated"
  ([export matrix](https://github.com/LibreYOLO/libreyolo/blob/main/docs/export_support.md)).
- **Licence:** code MIT, "Copyright (c) 2024 Kin-Yiu, Wong and Hao-Tang, Tsui". **The weights have
  no stated licence**, and the repo ships `format_converters.py` that converts old-format
  checkpoints, consistent with them being converted from `WongKinYiu/yolov9` (**GPL-3.0**). Wong is
  author of both, so an MIT grant by him is plausible, but nothing says so: **unverified, real
  risk**.
- **Phone cost:** v9-T 2.0 M / 7.7 G, v9-S 7.1 M / 26.4 G at 640
  ([upstream README](https://github.com/WongKinYiu/yolov9)). No mobile latency.

### 4. RF-DETR (Roboflow) — including its keypoint model

- **Maintenance:** very active. PyPI `rfdetr` **1.12.1, 2026-11-12**; `develop` commit 2026-11-15.
  `requires-python >=3.10`, `torch>=2.2`, no upper bound; the `[tflite]` extra pins onnx2tf
  2.4.x / tf-keras for Python 3.12 specifically (pyproject.toml).
- **Licences (README table):** `pip install rfdetr` gives "only Apache 2.0 RF-DETR code and models".
  Detection **Nano, Small, Medium, Large: Apache-2.0**; Atto/Femto/Pico/XL/2XL are under the
  Roboflow **Platform Model License 1.0** (commercial self-hosting needs Enterprise) and ship in a
  separate `rfdetr_plus` package since 1.12.0 — don't install that. "Every RF-DETR-Seg size and
  RF-DETR Keypoint are Apache 2.0." Backbone DINOv2, Apache-2.0. Repo LICENSE: Apache-2.0.
  Objects365 pretraining of the detectors: its terms **unverified**.
- **Keypoint fit: the best native fit found.** `RFDETRKeypointPreview` takes
  **`num_keypoints_per_class: list[int]`**, "Keypoint schema by model label slot. A zero entry marks
  a detection-only class slot" ([training parameters](https://github.com/roboflow/rf-detr/blob/develop/docs/learn/train/training-parameters.md)).
  So `[80, 1]` (or `[80, 2]` with a flight point) = a *board* instance with 80 named keypoints and a
  *dart* instance with its Entry point. It has per-keypoint "findable" and "visible" losses, which is
  what a dart covering a crossing needs. Trains from COCO keypoint JSON or YOLO-pose labels. It is
  **a preview**: "API surface and checkpoint weights may change before the stable release"
  ([keypoints](https://rfdetr.roboflow.com/latest/learn/run/keypoints/)).
- **Export:** ONNX (FP32, static INT8 since 1.12.0), TFLite via onnx2tf (FP32, FP16, **dynamic-range
  INT8 only**; "Static (full-integer) INT8 is not supported"), LiteRT direct via litert-torch
  (experimental, FP32 only), ExecuTorch, CoreML, OpenVINO. For **keypoint models**: the TFLite route
  is "verified … on `RFDETRKeypointPreview` (pretrained, and a 1-class, 4-keypoint schema)" (FP32
  within 3.2e-3 of ONNX); the direct LiteRT route **refuses keypoint models** (rank-4
  `batch_matmul`). The LiteRT GPU delegate has no kernels for the query selection
  (`TOPK_V2`/`GATHER_ND`), so it runs on CPU/XNNPACK ([litert.md](https://github.com/roboflow/rf-detr/blob/develop/docs/exports/litert.md),
  `src/rfdetr/export/_tflite/exporter.py`). Phone latency tables are "pending a rerun".
- **Phone cost — the problem:** keypoint model **40.7 M params at 576×576**; detection Nano 30.5 M
  at 384, Small 32.1 M at 512. Fastest x86 CPU result for the keypoint model: **650 ms** (ONNX INT8,
  8-core EPYC; [keypoints](https://rfdetr.roboflow.com/latest/learn/run/keypoints/)). On a phone CPU
  expect seconds per Photo (**unverified estimate**). File size at 40.7 M params: ~81 MB FP16,
  ~41 MB dynamic INT8 — **over ADR-0008's 5–20 MB** (arithmetic, not measured).

### 5. Others worth naming

- **Own CenterNet/DeepDarts-style heatmap model on a `timm` backbone (recommended to trial).**
  `timm` 1.0.31 (2026-11-03, Apache-2.0, Python ≥3.10, current torch). Weights
  `timm/mobilenetv4_conv_small.e2400_r224_in1k`: 3.8 M params, 0.2 GMACs at 224, **Apache-2.0**,
  ImageNet-1k; `mobilenetv4_conv_medium.e500_r256_in1k`: 9.7 M, 1.1 GMACs at 256, Apache-2.0
  (HF model cards). At 640 that scales to ~1.6 / ~6.9 GMACs before the head (arithmetic). Head:
  small FPN to stride 4, **81 heatmap channels + 2-channel offset**, focal loss — a few hundred lines
  in `ml/`. Fits all three shapes of the task (names, variable darts, sub-pixel). A plain CNN exports
  cleanly: [litert-torch](https://github.com/google-ai-edge/litert-torch) (Apache-2.0, v0.10.0
  2026-10-20, "PyTorch converter is a Beta release", Python ≥3.10, Linux), ONNX → ONNX Runtime
  Android (MIT, `onnxruntime-android` 1.32.0 on Maven Central), or pnnx → ncnn (BSD-3, 20261020).
  Runs on the LiteRT GPU delegate / NNAPI (**unverified** per op until tried). Cost: we own the
  training loop, augmentation and decoding; no pretrained keypoint head.
- **[LibreYOLO](https://github.com/LibreYOLO/libreyolo)** — MIT umbrella (v1.8.0, 2026-11-15,
  created 2025-11-27, 151 model families, one contributor with ~3,300 of the commits). Wraps
  YOLOX/YOLOv9/RF-DETR/RTMDet with training and an export matrix (yolo9 and yolox detect: ONNX,
  TFLite, ncnn parity-validated); per-family weight licences in
  [LICENSE_NOTICE.txt](https://github.com/LibreYOLO/libreyolo/blob/main/weights/LICENSE_NOTICE.txt).
  Its `fomo` "point" task (x, y, class, confidence) is MobileNetV2 at 96–224 px with a 1×1
  classification head and **no sub-cell offset** — far too coarse for 1–2 mm. Breadth over depth;
  useful as a reference for export recipes, risky as a training dependency.
- **Excluded:** YOLO-NAS / YOLO-NAS-Pose (weights under Deci's non-commercial licence, per
  LibreYOLO's `yolonas/model.py`), DEIMv2 and EdgeCrafter (relicensed, above), Ultralytics
  (AGPL, ADR-0008), `WongKinYiu/yolov9` and YOLOv7 (GPL-3.0). D-FINE / DEIM v1 / RT-DETR are
  Apache-2.0 but box-only and DETR-heavy — no advantage over YOLOX for points-as-boxes.
  torchvision Keypoint R-CNN (BSD) is fixed-K and too heavy for a phone.

## Summary table

| | Maintained | Py 3.12 + current torch | Named points + variable darts | Android path | Code / weights licence | Size at ~640 |
| --- | --- | --- | --- | --- | --- | --- |
| MMPose RTMO/RTMPose | dormant (2024) | **no** without patching (mmcv/mmdet/chumpy) | fixed K, 1 class; darts by hack | RTMPose ncnn yes; RTMO ORT only | Apache / none stated | RTMO-s 9.9 M |
| YOLOX | dormant (2022 release) | probably, `--no-deps` | 81 classes as boxes | ncnn Android demo, ONNX | Apache / Apache | Tiny 5.1 M, S 9.0 M |
| MultimediaTechLab YOLOv9 | slow | probably | 81 classes as boxes | ONNX/TRT only (LibreYOLO adds TFLite/ncnn) | MIT / **unstated, likely from GPL** | T 2.0 M, S 7.1 M |
| RF-DETR Keypoint | very active | yes | **native: `[80, 1]`** | TFLite fp16/int8-dyn verified, CPU only | Apache / Apache | **40.7 M**, 576 |
| timm + heatmap head | timm active | yes | **native: 81 channels** | litert-torch / ORT / ncnn, GPU-delegate-friendly | Apache / Apache | ~4–10 M |

## Recommendation for the toolchain trial

1. **timm MobileNetV4 + a CenterNet-style heatmap head (81 named channels + offset), exported with
   litert-torch, ONNX → ONNX Runtime Android as fallback.** Best fit to the phone (size inside the
   ADR budget, GPU delegate possible), the most direct route to sub-pixel points, current
   toolchain, clean licences. **Biggest risk:** it is our own code — loss, target encoding, peak
   decoding and augmentation have no upstream to lean on, so a weak result may be a bug rather than
   a limit; the trial should include a sanity overfit on a handful of Photos.
2. **RF-DETR `RFDETRKeypointPreview` with `num_keypoints_per_class=[80, 1]`, exported through its
   TFLite (onnx2tf) route.** The least code to a first accuracy number, with occlusion modelled per
   keypoint. **Biggest risk:** phone cost — 40.7 M params (~41 MB even at dynamic INT8, over the
   ADR's 5–20 MB), CPU-only on LiteRT, 650 ms on an 8-core x86 so likely seconds on a phone; plus a
   preview API that may change under us.

Fallback if both stall: YOLOX-Tiny with 81 point-classes as small boxes (proven ncnn Android demo,
Apache weights; risk: box-centre precision). MMPose is not recommended: the install on Python 3.12
needs patching three dependencies and the project has been dormant since 2024.
