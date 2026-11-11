# Darts are found by an on-device keypoint model, and scored through a homography onto the board

## Context

The app reads a darts score from handheld photos of the board: no fixed camera, no photo of the
empty board before the throw, often an oblique angle, and darts that hide each other. Photos never
leave the phone (`CLAUDE.md`), so there is no server to run anything on.

The published work that comes closest is **DeepDarts** (McNally et al., CVPR 2021 Workshops,
[arXiv 2105.09880](https://arxiv.org/abs/2105.09880)). One detector finds four calibration points on
the double wire and the point where each dart enters the board. A homography maps those points onto
the regulation board, and the score is read in polar coordinates. It reports 94.7% of images scored
exactly right on face-on phone photos, but only 84.0% at varied angles. That 84.0% was taken on DSLR
photos and chosen as the best of five runs on the test set, so it is optimistic. The main failure is
a dart hidden by another dart. No later peer-reviewed work on handheld scoring was found as of
2026-11-11.

The licences constrain what can be reused. This repo is all-rights-reserved and source-available,
and the app is on Play with a tip purchase:

| Source | Licence | Usable |
| --- | --- | --- |
| DeepDarts dataset, [IEEE DataPort](https://ieee-dataport.org/open-access/deepdarts-dataset) | CC BY 4.0 | yes, with attribution |
| DeepDarts code, `wmcnally/deep-darts` | none, so all rights reserved | no; the method is reimplemented |
| Ultralytics YOLOv5/v8/11, and models trained with it | AGPL-3.0 | no |
| `bnww/dart-sense` (YOLOv8 on darts) | non-commercial, plus AGPL | no |
| MMPose/RTMPose, MMDetection/RTMDet, YOLOX, RF-DETR N/S/M/L | Apache-2.0 | yes |
| `MultimediaTechLab/YOLO` (YOLOv9) | MIT | yes |
| LiteRT / ONNX Runtime / ncnn | Apache-2.0 / MIT / BSD-3 | yes |

## Decision

- **One keypoint detector does both jobs.** In each photo it finds two kinds of point:
  - **Calibration points:** the boundary points between segments on the double and treble wires. That
    is many points rather than DeepDarts' four, so a homography still fits when darts cover some of
    them.
  - **Entry points:** where each dart's shaft enters the board.
- **The board is the regulation steel-tip board** (WDF Rules rev. 20, §4): double wire at 170.0 mm,
  treble wire at 107.4 mm, 25 ring at 15.9 mm, bull at 6.35 mm, segments clockwise from the top
  starting at 20: 20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5.
- **The homography is fitted with RANSAC.** Each entry point is mapped into board millimetres and
  scored there. Only the entry point is mapped: the homography is correct only on the board's plane,
  and a dart's flight sticks out of it.
- **Several photos are merged in board millimetres.** Entry points from different photos that lie
  within a few millimetres of each other are the same dart, and their positions are averaged,
  weighted by confidence. The app asks for **another angle** only when one of these is true:
  - fewer darts were found than were thrown;
  - a dart's confidence is low;
  - the photos disagree on a dart's segment;
  - an entry point sits within about 2 mm of a wire.
- **The model is trained off the phone, with Apache or MIT code only**, in this repo's `ml/` folder.
  It is exported to a file that ships inside the app, so scoring needs no network, and Play
  services does not supply the runtime. Which framework and which runtime is settled in phase M by
  measurement, not here.
- **Training data:**
  - the DeepDarts dataset, credited on the open-source licences screen;
  - the owner's own handheld photos from several angles, labelled. No public handheld set exists,
    and these are what the accuracy bar is measured on.
  
  A Roboflow dataset is added only after its page has been opened and both its licence and where its
  images came from are confirmed.

## Alternatives

- **Classical computer vision only:** red and green ring masks, an ellipse fit, and the segment
  boundaries as calibration points (Zgonc & Batagelj, ROSUS 2023). It finds the board well. It finds
  the dart tip only by comparing against a photo taken before the throw from the same fixed camera,
  which a handheld phone does not have. **Kept as a cross-check** on the calibration, not as the way
  darts are found.
- **Fixed-camera systems (Autodarts, Scolia):** these use three cameras mounted around the board and
  compare frames from before and after each throw. The app has neither the mounted cameras nor the
  before frame. What carries over is the idea that more views settle a hidden dart, which is what
  the second angle is for.
- **A cloud vision model** (any hosted multimodal API): the photo would leave the phone, the app
  would need `INTERNET` and someone to pay per request, and nothing published shows such models
  locate a dart to the millimetre a wire needs.
- **Ultralytics YOLO**, the easiest route to train: AGPL-3.0, and its terms make the trained weights
  AGPL too. Using it means releasing the app under AGPL or buying a licence.

## Consequences

- **Most of the work is data.** Hundreds of labelled handheld photos from several angles have to be
  taken and labelled before any accuracy figure means anything. Phase M is that work, and it comes
  before the app shows anything real.
- **A dart on a wire needs 1–2 mm of accuracy.** Lens distortion, a calibration point hidden by a
  dart, or a tip mistaken for the entry point each cost that much. So the app will sometimes be
  unsure, says so, and lets the player correct a dart by tapping the board.
- Steel-tip regulation boards only. A soft-tip board has different geometry and needs its own ADR.
- The app ships the model, which adds roughly 5–20 MB.
- CC BY 4.0 requires attribution. The DeepDarts dataset's credit belongs on the licences screen from
  the first build that ships a model trained on it.
