# Public darts datasets and AI-assisted labelling, against ADR-0008

A survey taken on 2026-11-20 of the public image sets that could add training data for the keypoint
model ([ADR-0008](adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md)), and of
the tools that could speed up labelling in `ml/`. Nothing was downloaded and no account was made. It
reopens nothing in ADR-0008 and decides nothing: where a source would need a decision, that is said.

**The rule it is read against.** The repo is all-rights-reserved and source-available, the app is free
on Play with a Tip, and the exported model ships inside it (committed as `assets/model/darts.tflite`).
So a source's licence has to allow commercial use of a model trained on it, and must not attach
share-alike terms to that model. ADR-0008 adds two things: a Roboflow dataset is used only after **its
page has been opened and both its licence and where its images came from are confirmed**, and
research-only data is out (`phase-M2.md` D2).

## How far the checks got

- **Roboflow Universe refused every automated read.** Each page answers a fetch with HTTP 403 and a
  Cloudflare "Just a moment…" challenge. A headless browser was not used to get past it. So every
  Roboflow figure below comes from search-engine snippets of those pages or from a Hugging Face mirror
  of them, and **no Roboflow page has been opened in the sense ADR-0008 requires**. That is the one
  step left for the owner, in a normal browser.
- **The licence on a Roboflow page is whatever its workspace owner picked.** Roboflow does not check
  that the owner holds the rights to the images. Almost every darts set shows CC BY 4.0, which says
  nothing about where the photos came from. That is why ADR-0008 asks for the origin as well as the
  licence. One public darts project, `bnww/dart-sense`, says its 8,000 added images were taken from
  YouTube videos, so frames from broadcasts and videos are a real risk in this corner.

## The sources

**Verdicts:** *usable with attribution* means the licence fits and the origin is plausible;
*unclear* means a step in ADR-0008's rule is still open; *not usable* names the reason.

| Source | Licence (as seen, and where) | Images | Labels | DeepDarts-derived? | Verdict |
| --- | --- | --- | --- | --- | --- |
| [DeepDarts, IEEE DataPort](https://ieee-dataport.org/open-access/deepdarts-dataset) | "Creative Commons Attribution", CC BY 4.0 (page read) | 16,050 (d1 ≈ 15k face-on phone, d2 830 at angles), 800×800 crops | 4 Calibration points + Entry points | is DeepDarts | **in use**, credited (ADR-0008) |
| [salmasolly967-gmail-com/darts-eob9x](https://universe.roboflow.com/salmasolly967-gmail-com/darts-eob9x) | CC BY 4.0 (search snippet) | 492 | boxes: `tip`, `cal1`–`cal4`, `center` | **likely**: DeepDarts' four-point scheme under DeepDarts' `cal1`–`cal4` names | **unclear**; dedupe before anything else |
| [darts-dmwtf/dartboard-detection](https://universe.roboflow.com/darts-dmwtf/dartboard-detection) | CC BY 4.0 (snippet of image metadata) | 500 | keypoint project, "Dartboard annotations"; skeleton not seen | unknown | **unclear**; open the page |
| [autodartapp/dartsai](https://universe.roboflow.com/autodartapp/dartsai) | CC BY 4.0 (snippet) | 186, 3 versions | keypoint project; classes not seen | unknown; the name points at fixed Autodarts-style cameras | **unclear**; small |
| [maxtest/dartpose](https://universe.roboflow.com/maxtest/dartpose) | CC BY 4.0 (HF mirror's card) | 224 on Universe, 574 in the mirror's v8 | keypoint, one class `dart` | unknown | **unclear**; Entry points only |
| [onecamsteeldarts/dartboarddetection](https://universe.roboflow.com/onecamsteeldarts/dartboarddetection) | not seen | 1.37k | boxes; a sibling project has `bull`, `cal1`–`cal4` | unknown; "one cam" means a fixed camera | **unclear**; licence unseen |
| [score-lpfmv/dart-app](https://universe.roboflow.com/score-lpfmv/dart-app) | CC BY 4.0 (snippet of image metadata) | 149 | boxes, 42 classes (score regions, by the count) | unknown | **unclear**; region boxes do not give Entry points |
| [matic-zgonc/darts-su3](https://universe.roboflow.com/matic-zgonc/darts-su3) | CC BY 4.0 (snippet) | 301 | boxes, one class `dart` | **no**: Zgonc & Batagelj, ERK 2023, 300 own photos from fixed cameras left, right and above | **unclear** on the page; origin is the paper's own rig, so likely usable with attribution once opened; low value |
| [dart-sqziy/darts-3jiso](https://universe.roboflow.com/dart-sqziy/darts-3jiso) | CC BY 4.0 (snippet) | 329 | boxes, darts | unknown | **unclear**; low value |
| [aidartboard-dataset/ai-dartboard-scoring-system-fina-0xgab](https://universe.roboflow.com/aidartboard-dataset/ai-dartboard-scoring-system-fina-0xgab) | not seen | 311 or 933 (the page disagrees with itself) | boxes, region classes (`triple_9`, `single_5`, `bullseye`) | unknown | **unclear**; region boxes, licence unseen |
| [mydarts/mydartboard](https://universe.roboflow.com/mydarts/mydartboard) | CC BY 4.0 (snippet, and HF mirror) | 116 on Universe, 283 in the mirror's v3 | boxes, 2 classes (by the snippet `bull`, `hit`) | unknown | **unclear**; low value |
| [Bayernator/scorelens-rf10-quellen](https://huggingface.co/datasets/Bayernator/scorelens-rf10-quellen) (HF mirror of 11 Roboflow sets, 9,531 images) | `cc-by-4.0`; "Jeder Datensatz steht unter CC BY 4.0; diese Sammlung gibt sie unverändert und mit Namensnennung weiter." | 9,531 | YOLOv8 exports, dart tips; only `darts_detection-yp7lt` has board labels (20 segment boundaries on the double) | unknown | **unclear**: a mirror cannot stand in for the source pages; useful as a list of what exists, see below |
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
Autodarts rigs. Every row would still need its own Universe page opened.

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
2. **If more data is wanted before more Capture sessions, open the Roboflow keypoint sets first**, in a
   normal browser, logged out: `darts-dmwtf/dartboard-detection`, `jonas-workspace-lm7ia/dart-pose-v6-ovihb`
   (the largest, 3,545), `maxtest/dartpose`, `autodartapp/dartsai`, and `darts-eob9x` only to confirm it
   is DeepDarts. For each, write down the licence and where the photos came from, per ADR-0008. Expect
   fixed cameras and tip-only labels. Their worth is Entry points on other boards, darts and light, and
   training on them needs `train` to tell "Calibration point not labelled" from "not on the Photo", or
   the model learns that boards have no crossings. That is code to write first, so the gain should be
   weighed against one more Capture session.
3. **The stronger lever, if the bar is missed, is synthetic renders**, which `phase-M2.md` already
   names as an escalation: `ahie/darts-model`'s renderer is Apache-2.0 and labels 81 board points and
   each dart's landing point exactly. Use it with procedural backgrounds or the owner's own empty-wall
   photos, never its optional Places365 backgrounds, whose terms are non-commercial research and
   education.
4. **Leave out** dartscribe (share-alike, unless the owner decides otherwise), the Hugging Face
   DeepDarts re-upload, dart-sense, the Kaggle in-flight set, and, as not worth the effort,
   Wikimedia Commons and Open Images.
5. **For labelling, keep `prefill` and the project's own model.** Add an open-vocabulary detector
   (OWLv2, Apache-2.0) only if unlabelled public photos are ever triaged in bulk, after the question in
   the section above has an answer.
