# Public darts datasets and AI-assisted labelling, against ADR-0008

A survey taken on 2026-11-20 of the public image sets that could add training data for the keypoint
model ([ADR-0008](adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md)), and of
the tools that could speed up labelling in `ml/`. Nothing was downloaded but a few Roboflow
thumbnails for the DeepDarts check, and no account was made. It
reopens nothing in ADR-0008 and decides nothing: where a source would need a decision, that is said.

**The rule it is read against.** The repo is all-rights-reserved and source-available, the app is free
on Play with a Tip, and the exported model ships inside it (committed as `assets/model/darts.tflite`).
So a source's licence has to allow commercial use of a model trained on it, and must not attach
share-alike terms to that model. ADR-0008 adds two things: a Roboflow dataset is used only after **its
page has been opened and both its licence and where its images came from are confirmed**, and
research-only data is out (`phase-M2.md` D2). The owner set the rest on 2026-11-20: CC BY 4.0, MIT
or Apache-2.0 data is usable with a Credits-screen entry (name, author, licence and link, "changed:
used to train the model"), provided the uploader appears to own the images and the set has passed the
DeepDarts duplicate check below; CC BY-SA and any NC licence are not usable. That rule is not in
ADR-0008 either: like the share-alike change below, it waits for a dated amendment.

## Since this survey (2026-11-22)

The rest of this page is the 2026-11-20 record and is left as it was, apart from the dated
*Outcome* lines under *Recommendation*. Four things have moved since:

- **Share-alike.** Later on 2026-11-20 the owner accepted CC BY-SA training data, such as dartscribe,
  even though it may make `darts.tflite` CC BY-SA (whether a trained model is Adapted Material is
  unsettled, see [Why share-alike is a problem here](#why-share-alike-is-a-problem-here)); the app's code stays all-rights-reserved and NC
  data stays out. ADR-0008 does not record this yet: it needs a dated amendment before any
  share-alike set is used.
- **`dart-pose-v6-ovihb` was tried and dropped.** Its fine-tunes read at best 692 of the 1,070
  DeepDarts validation Photos exactly right, against the shipped run's 737.
- **`autodartapp/dartsai` was tried in one exploratory local run.** It was imported into the data
  folder only to try; it is in no shipped model, so ADR-0008 does not record it, and would need to
  only if a model trained on it were to ship. That run read 715 of 1,070.
- **Renders were tried**, from `maks-sredniawa/darts-render`, the owner's fork of `ahie/darts-model`
  (ADR-0008). No mix so far beats the shipped run on DeepDarts validation; the best read 722.

The runs and their figures are recorded in [`phase-M2.md`](phase-M2.md) §7, the 2026-11-22 note.

What has held: labelled Photos of the owner's own board, which recommendation 1 calls the data the
bar is measured on, remain the lever.

## How far the checks got

- **Roboflow Universe refused every automated read.** Each page answers a fetch with HTTP 403 and a
  Cloudflare "Just a moment…" challenge. So the eleven Roboflow pages in the table were **read on the
  page 2026-11-20** in a normal browser, logged out: the overview (licence, classes, counts), the
  version page where counts disagreed, and the first page of the image browser, which shows file names
  and annotated thumbnails. The licence and labels in the table are what those pages say.
- **The DeepDarts check was run on a sample.** Logged out, a set shows only its first 50 or so
  images. Where the photos could pass for DeepDarts' (a face-on board, `IMG_*` names), up to eight
  200 px thumbnails per set were hashed (the pHash of step 2 below, with flips and rotations) against
  all 16,050 DeepDarts crops, and a thumbnail that matched was compared pixel by pixel with the
  DeepDarts file of the same name. The other sets are told apart by their cameras, boards and names.
  Two sets are DeepDarts outright. For the rest the sample rules out a copy only of what it saw, so
  the full check still runs on download.
- **The licence on a Roboflow page is whatever its workspace owner picked.** Roboflow does not check
  that the owner holds the rights to the images. Almost every darts set shows CC BY 4.0, which says
  nothing about where the photos came from. That is why ADR-0008 asks for the origin as well as the
  licence. One public darts project, `bnww/dart-sense`, says its 8,000 added images were taken from
  YouTube videos, so frames from broadcasts and videos are a real risk in this corner.

## The sources

**Verdicts:** *usable with a Credits entry* means the licence fits and the uploader appears to own
the photos, so only the full duplicate check on download is left; *unclear* means a step in
ADR-0008's rule is still open; *not usable* names the reason.

| Source | Licence (as seen, and where) | Images | Labels | DeepDarts-derived? | Verdict |
| --- | --- | --- | --- | --- | --- |
| [DeepDarts, IEEE DataPort](https://ieee-dataport.org/open-access/deepdarts-dataset) | "Creative Commons Attribution", CC BY 4.0 (page read) | 16,050 (d1 ≈ 15k face-on phone, d2 830 at angles), 800×800 crops | 4 Calibration points + Entry points | is DeepDarts | **in use**, credited (ADR-0008) |
| [darts-eob9x](https://universe.roboflow.com/salmasolly967-gmail-com/darts-eob9x) | "CC BY 4.0" (read on the page 2026-11-20) | 492, 7 versions | boxes, 6 classes: `cal1`–`cal4`, `center`, `tip`; in the samples the `cal` boxes sit on the numbers 20, 6, 3 and 11 | **no**, by the sample: 7 thumbnails are 14–16 bits from the nearest DeepDarts crop. Several boards, cracked cheap ones among them, and five naming schemes: `images10.jpg`, `(51).jpg`, `a_19.jpg`, `test65.jpg`, `output40.jpg` | **not usable**: no sign the uploader took the photos. `images*.jpg` is what image-search downloaders write, and there is no description or source |
| [darts-dmwtf/dartboard-detection](https://universe.roboflow.com/darts-dmwtf/dartboard-detection) | "CC BY 4.0" (read on the page 2026-11-20) | 500; v1 and v2 both 500, no augmentation | keypoint, one class `dartboard`: points on the bull and the double ring; point names not shown logged out | **yes**: every name seen is a DeepDarts name (`IMG_6775.JPG`, `DSC_0012.JPG` …), and 8 of 8 thumbnails match the DeepDarts crop of the same name (pHash 0–2 bits, mean pixel difference about 4/255 against 15–26 for the other file of that name) | **not usable**: DeepDarts re-uploaded without credit; adds nothing |
| [autodartapp/dartsai](https://universe.roboflow.com/autodartapp/dartsai) | "CC BY 4.0" (read on the page 2026-11-20) | 186, 3 versions | keypoint, one class `Dart`: two unnamed points per dart (ids 0 and 1), drawn as a line along it | **no**: 1536×2048 portrait phone photos, `IMG_4785`–`IMG_4992.JPEG` in one run, of one Winmau Blade 6 on a grey surround, face-on and a little off-axis; 8 thumbnails are 6–18 bits from DeepDarts and show another board and room | **usable with a Credits entry**; small, Entry points only, no Calibration points |
| [maxtest/dartpose](https://universe.roboflow.com/maxtest/dartpose) | "CC BY 4.0" (read on the page 2026-11-20) | 224, 7 versions (574 in the HF mirror's v8) | keypoint, one class `dart`: two points per dart along the barrel | **no**: darts off the board, on tables and in packaging; most named `grenadeBack_0036.jpg` (with `_00001` copies), a few `PXL_20241120_…` phone photos and `d25.JPG` | **not usable**: no dart is in a board, so no Entry points; the product-style `grenadeBack_*` shots give no sign the uploader took them |
| [onecamsteeldarts/dartboarddetection](https://universe.roboflow.com/onecamsteeldarts/dartboarddetection) | "MIT" (read on the page 2026-11-20) | 1,369, 2 versions | boxes, one class `Dartboard` | not checked: the names mix other sets, `darts-eob9x`'s (`test90.jpg`, `a_63.jpg`, `images4.jpg`, `output35.jpg`) and `mydarts/mydartboard`'s webcam sessions (`WIN_20240302_18_31_06_Pro.jpg`), with `PXL_2021…`, `IMG_5224.JPG`, `Screenshot 2022-07-18 …png` and `-60-.jpg` | **not usable**: gathered from other sets, so the MIT was not the uploader's to grant; whole-board boxes only |
| [jonas-workspace-lm7ia/dart-pose-v6-ovihb](https://universe.roboflow.com/jonas-workspace-lm7ia/dart-pose-v6-ovihb) | "CC BY 4.0" (read on the page 2026-11-20) | 1,317; its one version (2025-11-19) is 3,545 after 3× augmentation, the mirror's figure | keypoint, one class `Dart`: two unnamed points per dart (ids 0 and 1) | **no**: 640×480 webcam snapshots (`snapshot_316.jpg`, `snapshot_usb_cam1_18.jpg`, `snapshot_usb_cam2_65.jpg`) from fixed USB cameras at steep side angles round one Winmau Blade on an orange surround; 4 thumbnails are 16–20 bits from DeepDarts | **usable with a Credits entry**; fixed cameras, Entry points only, no Calibration points |
| [score-lpfmv/dart-app](https://universe.roboflow.com/score-lpfmv/dart-app) | "CC BY 4.0" (read on the page 2026-11-20) | 149, no version generated | boxes, 42 classes: score regions (`Single1` …, `Double17`, `Tripple20`, `Bull`, `NoScore`) and `Senkrecht`, `Waagerecht` | **yes**: names `IMG_1085`–`IMG_1841.JPG`, the range of DeepDarts' `d1_02_04_2020` and `d1_02_06_2020`; 6 of 6 thumbnails are 0–2 bits from a DeepDarts crop, 3 of them the file of the same name | **not usable**: DeepDarts re-uploaded without credit |
| [matic-zgonc/darts-su3](https://universe.roboflow.com/matic-zgonc/darts-su3) | "CC BY 4.0" (read on the page 2026-11-20) | 301, 4 versions | boxes, one class `Dart` | **no**: `cam1_17122021_102456.png`, `cam2_…`, `cam3_…` from three fixed cameras in December 2021, and numbered `236.jpg` crops, one Winmau board at oblique angles; the rig of Zgonc & Batagelj, ERK 2023 | **usable with a Credits entry**; low value: boxes, fixed cameras |
| [dart-sqziy/darts-3jiso](https://universe.roboflow.com/dart-sqziy/darts-3jiso) | "CC BY 4.0" (read on the page 2026-11-20) | 329, 1 version | boxes, one class `dart` | **no**: `dart-2023-04-14T05-16-38-842218-.jpg` …, one morning's timed captures from one fixed camera level with the board's face, darts seen side-on | **usable with a Credits entry**; low value: side-on boxes give no Entry points |
| [aidartboard-dataset/ai-dartboard-scoring-system-fina-0xgab](https://universe.roboflow.com/aidartboard-dataset/ai-dartboard-scoring-system-fina-0xgab) | "CC BY 4.0" (read on the page 2026-11-20) | 311; its one version (2025-09-24) is 933 after 3× augmentation, which is where the two figures came from | boxes, 71 classes: regions (`single_1` …, `double_20`, `triple_9`, `bullseye`, `inner_bullseye`, `outer_bullseye`, `miss`) and strays (`0`, `1`, `class_11`, `objects`, `tdouble_19`) | **no**: phone photos `20250913_104630.jpg` … from one day, one cheap board against a cardboard box, roughly face-on | **usable with a Credits entry**; low value: region boxes do not give Entry points |
| [mydarts/mydartboard](https://universe.roboflow.com/mydarts/mydartboard) | "CC BY 4.0" (read on the page 2026-11-20) | 116, 3 versions (283 in the HF mirror's v3) | boxes, 2 classes: `bull`, `hit` | **no**: Windows Camera captures `WIN_20240302_18_32_26_Pro.jpg`, `WIN_20240303_…` from two evenings, one fixed webcam low and to the left of a Unicorn board | **usable with a Credits entry**; low value |
| [Bayernator/scorelens-rf10-quellen](https://huggingface.co/datasets/Bayernator/scorelens-rf10-quellen) (HF mirror of 11 Roboflow sets, 9,531 images) | `cc-by-4.0`; "<span lang="de">Jeder Datensatz steht unter CC BY 4.0; diese Sammlung gibt sie unverändert und mit Namensnennung weiter.</span>" | 9,531 | YOLOv8 exports, dart tips; only `darts_detection-yp7lt` has board labels (20 segment boundaries on the double) | unknown | **unclear**: a mirror cannot stand in for the source pages; useful as a list of what exists, see below |
| [geforcefan/dartscribe](https://huggingface.co/datasets/geforcefan/dartscribe) | `cc-by-sa-4.0` (HF metadata); "Recorded and labelled by Ercan Akyürek" | 14.4k rows, three cameras, 827–2k px | **bull + 80 wire crossings in pixels**, and each dart's segment, multiplier and board position | no | **not usable as things stand**: share-alike, see below |
| [bhabha-kapil/Dartboard-Detection-Dataset](https://huggingface.co/datasets/bhabha-kapil/Dartboard-Detection-Dataset) | `mit` (HF metadata) | 16,050, 800 px | none: `label` is the folder name, 51 classes | **yes**: 16,050 images in DeepDarts' 51 session folders (`d1_02_04_2020` …), the count and folders of `cropped_images/800/` | **not usable**: a re-upload of DeepDarts with no credit; MIT was not the uploader's to grant, and it adds nothing |
| [Kaggle kaflebeast/dartboard-dart-images-with-annotations](https://www.kaggle.com/datasets/kaflebeast/dartboard-dart-images-with-annotations) | "MIT" (Kaggle API metadata) | not stated; 639 MB | boxes, darts **in flight** ("a projectile (dart) tracking model") | unlikely | **not usable** for this model: darts in flight, not in the Board; origin not stated |
| [bnww/dart-sense](https://github.com/bnww/dart-sense) | "licensed for non-commercial, non-distributable use only" | DeepDarts + ~8,000 own and YouTube frames; a sample only is released | boxes at DeepDarts' four points + darts | partly | **not usable** (already in ADR-0008's table) |
| [ahie/darts-model](https://github.com/ahie/darts-model) (a renderer, not a dataset) | "The code is licensed under the Apache License 2.0" | as many as rendered | **81 board keypoints** (40 double-ring corners among them), each dart's landing point and flight | no | **usable** as code, with procedural backgrounds only (below) |
| [Wikimedia Commons, Category:Dartboards](https://commons.wikimedia.org/wiki/Category:Dartboards) | per file (CC BY, CC BY-SA, public domain mixed) | 102 + 40 in "Dartboard with darts" + 22 in art | none | no | **marginal**: CC0/PD/CC BY files usable with per-file credit; CC BY-SA files as dartscribe; few are close handheld shots |
| Open Images V7 | annotations CC BY 4.0; images listed by Flickr as CC BY 2.0, which Google does not verify | not counted | `Dartboard`, `Dart`, `Darts` are **image-level labels only**, not among the 601 boxable classes | no | **marginal**: unlabelled photos, per-image credit |

**Searched and not found:** a Zenodo record of darts photos; a peer-reviewed paper after DeepDarts
that released handheld multi-angle data (the ERK 2023 paper above is the nearest, and its 300 Photos are
from fixed cameras at one angle). No public handheld, multi-angle set with Calibration points and Entry
points exists beyond DeepDarts, which matches ADR-0008's own finding.

### What the mirror shows about Roboflow

The Bayernator card is the most complete list of Roboflow darts sets with tip labels. Besides `maxtest/dartpose`
and `mydarts/mydartboard` above it names `darts-yolo/dart_final` (726), `darts-yolo/static_tip` (412),
`darts-yolo/dart_einschlagpunkt-gghqm` (79), `dartpg/autodarts_only_tip-8cfyh` (1,728),
`jonas-workspace-lm7ia/dart-pose-v6-ovihb` (3,545), `aidartboard-dataset/darts-again-enx2d` (899),
`aidartboard-dataset/dartss-pwjyf` (339), `cosc428-fl0r5/dartdetection-043ip` (330) and
`dartdetection-vfgjd/darts_detection-yp7lt` (616). Its own note says only the last carries board
calibration labels; the rest label dart tips alone. Names like `autodarts_only_tip` point at fixed
Autodarts rigs. Its counts are of augmented exports: `dart-pose-v6-ovihb`'s 3,545 is 1,317 photos
tripled. Of its list only `dartpose`, `mydartboard` and `dart-pose-v6-ovihb` have been opened (table);
every other row would still need its own Universe page opened.

### Why share-alike is a problem here

CC BY-SA 4.0 asks that Adapted Material be shared under the same licence. Whether a model trained on a
dataset is Adapted Material is not settled. If it is, `darts.tflite` would have to be CC BY-SA, while it
sits in an all-rights-reserved repo inside an all-rights-reserved app. dartscribe is the closest public
match to ADR-0008's own labels (its 80 crossings are the 80 Calibration points), so it is worth naming,
but using it needs an owner decision and an ADR-0008 amendment, and its cameras are fixed, not handheld.
Its model, `geforcefan/dartscribe`, is AGPL-3.0 YOLO11 and is not usable either way.

### Checking a set against DeepDarts, once it is downloaded

Only once a set has passed ADR-0008's page check, and into its own directory, never under
`deepdarts/`:

1. **Names first.** Roboflow exports usually keep the original stem, as `IMG_2956_JPG.rf.<hash>.jpg`. Stems that
   match DeepDarts' `IMG_*.JPG` names, together with 800×800 or a Roboflow resize of it (640, 416),
   are a strong sign of a copy.
2. **Perceptual hash.** Hash every Photo in `deepdarts/cropped_images/800/` (16,050) and every
   candidate image with a 64-bit DCT pHash (a few lines of NumPy, or `imagehash`, BSD-2-Clause). For
   each candidate also hash its horizontal flip and 90° rotations, which Roboflow's augmentations
   add. A Hamming distance of 8 or less is a likely duplicate; look at each pair side by side.
3. **Labels.** For a matched pair, scale the candidate's `cal1`–`cal4` and tip points into 800×800 and
   compare them with the record in `deepdarts/records.jsonl`. Points within a few pixels mean the
   labels were copied too.
4. **Drop the duplicates** before a single epoch, and keep the list. A set that is mostly DeepDarts adds
   nothing and is dropped whole; its licence would be DeepDarts' anyway.

## AI-assisted labelling inside the rules

The app stays offline. The rules for `ml/` are ADR-0008's: permissive code only for what is adapted,
trained with or shipped, and nothing from these tools ships. A labelling tool's output is a suggestion
that a person confirms, the way `prefill` already works.

| Option | Licence | Can it place a point to 1–2 mm? |
| --- | --- | --- |
| **What `ml/` already has.** `prefill` projects all 80 Calibration points from four Hand points through a homography, and suggests Entry points across a Visit's Angles. The project's own model (`predict`) can pre-label a new Capture session the same way. No OpenCV: `ml/README.md` says nothing in the loop needs it | the project's own | **Calibration points: yes**, a homography from four clicked points lands on the crossings. **Entry points: close**, but a person still drags each one; the model's own error is what is being trained away |
| **SAM, SAM 2** (Meta) | Apache-2.0, code and checkpoints | **No.** Masks of the board, the rings or a dart's barrel help draw a box; a mask's edge is not the point a tip enters the board |
| **SAM 3** (Meta, 2025-11) | Meta's own "SAM License": royalty-free and commercial use allowed by secondary sources, but not an open-source licence, with use restrictions and gated download | as SAM 2. Outside ADR-0008's "permissive" wording; needs a decision before use |
| **OWLv2 / OWL-ViT** (Google) | Apache-2.0 (HF metadata) | **No.** Open-vocabulary boxes: finds "dartboard" or "dart" in an unlabelled photo, which is triage, not labelling |
| **Grounding DINO** (IDEA Research) | repository Apache-2.0 (the weights' licence is not stated separately); 1.5 is reached through a separate API repository | **No.** As OWLv2 |
| **Florence-2** (Microsoft) | MIT (HF metadata) | **No.** Detection and region proposals, no keypoints |
| **A hosted vision LLM** | the provider's terms | **No**, and nothing published shows one locates a tip to the millimetre (ADR-0008, *Alternatives*). Usable for triage of public photos only: "is there a steel-tip board with darts in it, is it sharp". The owner's Photos never go to one, since they show the owner's home |

Every pretrained model above was trained on web-scale data under mixed terms (SAM on SA-1B, released
under a research licence, not checked again here; OWLv2 on web image-caption pairs, COCO and Open Images). Using one as a
**labelling tool** whose output a person confirms is a different question from D2's pretrained
*backbone*, whose weights end up in the shipped model; but it is close enough that the owner should
answer it once, in writing, before any of them is added to `ml/`.

**Bottom line:** no off-the-shelf model places Calibration points or Entry points precisely enough to
skip review. The one that does most of the work, the homography from four Hand points, is already in
`ml/`. The others would help only to find boards and darts in unlabelled photos.

## Recommendation

1. **Nothing here changes the plan.** The owner's Capture sessions stay the data the bar is measured on,
   and DeepDarts stays the bulk. No public set is handheld, multi-angle and labelled with both kinds of
   point.
2. **If more data is wanted before more Capture sessions, the Roboflow keypoint sets that pass are
   `jonas-workspace-lm7ia/dart-pose-v6-ovihb` (1,317 photos) and `autodartapp/dartsai` (186)**, each
   with a Credits entry and after the full duplicate check. The other two keypoint sets fail:
   `darts-dmwtf/dartboard-detection` is DeepDarts, and `maxtest/dartpose` has no board in it. Both
   that pass are tip-only, and dart-pose-v6's cameras are fixed. Their worth is Entry points on other
   boards, darts and light, and training on them needs `train` to tell "Calibration point not
   labelled" from "not on the Photo", or the model learns that boards have no crossings. That is code
   to write first, so the gain should be weighed against one more Capture session.
   **Outcome, 2026-11-22:** both were tried and neither is kept: dart-pose-v6 is dropped and DartsAI
   stayed one exploratory run ([Since this survey](#since-this-survey-2026-11-22)).
3. **The stronger lever, if the bar is missed, is synthetic renders**, which `phase-M2.md` already
   names as an escalation: `ahie/darts-model`'s renderer is Apache-2.0 and labels 81 board points and
   each dart's landing point exactly. Use it with procedural backgrounds or the owner's own empty-wall
   photos, never its optional Places365 backgrounds, whose terms are non-commercial research and
   education.
   **Outcome, 2026-11-22:** tried through the owner's fork, `maks-sredniawa/darts-render`; no mix
   tried so far beats the shipped run ([Since this survey](#since-this-survey-2026-11-22)), and
   `phase-M2.md` §7 keeps no render mix; it names labelled Photos of the owner's own board as the
   lever left.
4. **Leave out** dartscribe (share-alike, unless the owner decides otherwise), the Hugging Face
   DeepDarts re-upload and the two on Roboflow (`dartboard-detection`, `dart-app`), the Roboflow sets
   whose uploader shows no sign of owning the photos (`darts-eob9x`, `onecamsteeldarts`, `dartpose`),
   dart-sense, the Kaggle in-flight set, and, as not worth the effort, Wikimedia Commons, Open Images
   and the Roboflow box sets that pass (`darts-su3`, `darts-3jiso`, the AI-Dartboard set,
   `mydartboard`).
   **Outcome, 2026-11-22:** the owner has since accepted share-alike, so dartscribe now waits on
   ADR-0008's amendment and on the DeepDarts duplicate check this page requires
   ([Since this survey](#since-this-survey-2026-11-22)).
5. **For labelling, keep `prefill` and the project's own model.** Add an open-vocabulary detector
   (OWLv2, Apache-2.0) only if unlabelled public photos are ever triaged in bulk, after the question in
   the section above has an answer.
