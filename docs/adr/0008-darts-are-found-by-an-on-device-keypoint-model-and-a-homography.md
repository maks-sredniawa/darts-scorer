# Darts are found by an on-device keypoint model, and scored through a homography onto the board

## Context

The app reads a darts score from handheld photos of the board: no fixed camera, no photo of the
empty board before the darts are thrown, often an oblique angle, and darts that hide each other. A
player's photos never leave the phone (`CLAUDE.md`), so there is no server to run anything on.

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
- **The board is the regulation steel-tip wire board** of the
  [WDF Playing and Tournament Rules, rev. 20](https://site.dartswdf.com/wp-content/uploads/2020/05/2018-02-28_WDF_Playing_and_Tournament_Rules_rev20.pdf),
  §4.01, checked against that PDF on 2026-11-11. The rules fix the bull and 25 rings by their inside
  diameters (12.7 mm and 31.8 mm), the treble and double wires by their outside edge (107.4 mm and
  170.0 mm from the centre), and both narrow rings as 8.0 mm wide measured inside wire to inside
  wire. A wire may be 1.27–1.85 mm thick, written *w*. Each wire is a band, in mm from the centre:

  | Wire | Inner edge | Outer edge |
  | --- | --- | --- |
  | Bull ring | 6.35 | 6.35 + *w* |
  | 25 ring | 15.9 | 15.9 + *w* |
  | Inner treble wire | 99.4 − 2*w* | 99.4 − *w* |
  | Outer treble wire | 107.4 − *w* | 107.4 |
  | Inner double wire | 162.0 − 2*w* | 162.0 − *w* |
  | Outer double wire | 170.0 − *w* | 170.0 |

  A region runs between the wires around it, and a dart scores on the side of the wire its point
  enters (§3.03). The app takes *w* as 1.5 mm. A real board's wire differs from that by at most
  0.35 mm, so an edge measured across one wire moves by up to 0.35 mm and the inner treble and
  double edges, measured across two, by up to 0.7 mm: both inside the 2 mm wire margin below. Older BDO tables give the treble as 107.0 mm; WDF rev. 20 gives 107.4 mm, and that is used.
  Segments run clockwise from the top starting at 20: 20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7,
  16, 8, 11, 14, 9, 12, 5.
- **The homography is fitted with RANSAC.** Each entry point is mapped into board millimetres and
  scored there. Only the entry point is mapped: the homography is correct only on the board's plane,
  and a dart's flight sticks out of it.
- **Several photos are merged in board millimetres, one dart to one dart.** Each further photo's
  Entry points are matched to the darts found so far by an assignment on distance, so two Entry
  points from the same photo never land on one dart. A pair further apart than a gate of a few
  millimetres is not a match: those stay separate darts. A matched dart's position is the average of
  its Entry points, weighted by confidence. The app asks for **another angle** only when one of these
  is true:
  - fewer darts were found than were thrown;
  - a dart's confidence is low;
  - the photos disagree on a dart's segment;
  - an entry point sits within about 2 mm of a wire.
- **The model is trained off the phone, with permissively licensed code only** (amended
  2026-11-13, below), in this repo's `ml/` folder.
  `ml/` holds code only: the datasets, the labels and the training weights are git-ignored and never
  published, because the owner's photos show their home. The one thing that leaves `ml/` is the
  exported model file that ships inside the app, so scoring needs no network, and Play services
  does not supply the runtime. Which framework and which runtime is settled in phase M2 by
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
  a dart's Entry point only by comparing against a photo taken before the dart from the same fixed
  camera, which a handheld phone does not have. **Kept as a cross-check** on the calibration, not as
  the way darts are found.
- **Fixed-camera systems (Autodarts, Scolia):** these use three cameras mounted around the board and
  compare frames from before and after each dart. The app has neither the mounted cameras nor the
  before frame. What carries over is the idea that more views settle a hidden dart, which is what
  the second angle is for.
- **A cloud vision model** (any hosted multimodal API): the photo would leave the phone, the app
  would need `INTERNET` and someone to pay per request, and nothing published shows such models
  locate a dart to the millimetre a wire needs.
- **Ultralytics YOLO**, the easiest route to train: AGPL-3.0, and its terms make the trained weights
  AGPL too. Using it means releasing the app under AGPL or buying a licence.

## Consequences

- **Most of the work is data.** Hundreds of labelled handheld photos from several angles have to be
  taken and labelled before any accuracy figure means anything. Phase M1 is that work and phase M2
  trains on it; both come before the app shows anything real.
- **A dart on a wire needs 1–2 mm of accuracy.** Lens distortion, a calibration point hidden by a
  dart, or the wrong spot on a dart taken for its Entry point each cost that much. So the app will sometimes be
  unsure, says so, and lets the player correct a dart by tapping the board.
- Steel-tip regulation boards only. A soft-tip board has different geometry and needs its own ADR.
- The app ships the model, which adds roughly 5–20 MB.
- CC BY 4.0 requires attribution. The DeepDarts dataset's credit belongs on the licences screen from
  the first build that ships a model trained on it.

## Amendment — 2026-11-13: the Calibration points, DeepDarts' labels and the licence rule

Phase M1 ([`phase-M1.md`](../phase-M1.md)) writes the geometry above as code (`ml/src/darts_ml/board.py`)
and settles three things this ADR left open.

- **A Calibration point is the centre of a crossing**: where the centre line of the radial wire
  between two segments meets the centre line of one of the four ring wires. That is 20 × 4 = **80
  points**. Each radial wire lies on a segment boundary, at 9° plus a multiple of 18° clockwise from
  the top, and each ring wire's centre radius follows from the bands above with *w* = 1.5 mm:

  | Ring wire | Name | Centre radius (mm) |
  | --- | --- | --- |
  | Outer double | `do` | 169.25 |
  | Inner double | `di` | 159.75 |
  | Outer treble | `to` | 106.65 |
  | Inner treble | `ti` | 97.15 |

  A point is named `<ring>-<a>-<b>`, with `a` and `b` the segments either side in clockwise order,
  such as `do-20-1` and `ti-5-20`. The centre of a crossing is what the eye finds on a Photo; a wire's
  edge is not.
- **DeepDarts' labels come from IEEE DataPort's `labels_pkl.zip`**, which is CC BY 4.0, and not from
  the `dataset/labels.pkl` in `wmcnally/deep-darts`, which carries that repository's no-licence status.
  DataPort's **`models.zip` is not used**: those weights were trained with the unlicensed code, and M2
  starts from its own permissively licensed initialisation.
- **The licence rule is permissive licences only** (Apache, MIT, BSD and the like) for everything in
  `ml/`'s lockfile, everything that trains, and everything that ships. Copyleft code (GPL, AGPL) stays
  out of all three. The earlier wording, "Apache or MIT code only", contradicted this ADR's own table,
  which counts BSD-3 ncnn as usable. labelme, which is GPL-3.0, runs beside `ml/` through `uvx` to
  label Photos and never enters the lockfile, training or the app.
