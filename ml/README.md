# ml/ — the labelling loop

Code only. The owner's Photos, their labels, DeepDarts and any weights live in `DARTS_DATA`, outside
the repository, and never enter git ([ADR-0008](../docs/adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md)).
The plan, the data layout and the bar are in [`docs/phase-M1.md`](../docs/phase-M1.md); the words are
in [`CONTEXT.md`](../CONTEXT.md).

## Setup

```bash
sudo apt install libjpeg-turbo-progs        # jpegtran, for ingest
uv sync --locked --directory ml --extra rocm   # PyTorch for an AMD GPU (ROCm); --extra cpu for no GPU
uv run --directory ml darts-ml paths        # prints DARTS_DATA, refuses one inside the repo, checks jpegtran
```

PyTorch comes in one of two builds, the `rocm` and `cpu` extras, which cannot be installed together
(`litert`, below, is a third).
Sync once with the one this machine wants: a later `uv sync` without it removes PyTorch, while `uv run`
leaves it alone. The `rocm` build carries the whole ROCm runtime (about 17 GB installed) and needs only
the kernel's `amdgpu` driver. The lock covers Linux on x86-64 only, and holds PyPI packages to releases
before 2026-11-03 (`[tool.uv.exclude-newer-package]`); move that date forward deliberately.

**Every step reads a Photo through `images.open_srgb`**, which converts one tagged with a colour
profile to sRGB with LittleCMS (Pillow's `ImageCms`) and leaves a profile-free one as it is, and one
whose profile cannot be read, with a warning, as Android's decoder does. The app reads pixels as
sRGB, and a Xiaomi tags its Photos Display P3: read as raw numbers, they are up to 55 levels off what
the app sees, enough to move a Dart (`docs/phase-1.md` §1, 2026-11-21).

`DARTS_DATA` defaults to `~/darts-scorer-data`. `paths.py` refuses any value that resolves inside the
repository or one of its worktrees, symlinks followed, and the same for every folder under it that the
loop reads or writes.

## The sheet

`$DARTS_DATA/capture-sessions/<capture-session>.toml`, typed up the same day from the notes taken at
the Board. One `[[visits]]` per Visit, in order, one string per Dart: its Score, then any marks.

```toml
phone = "phone 1"
light = "day"            # day, evening, flash or harsh
set = "training"         # training, held-out or gate
date = 2026-11-14

[[visits]]
darts = ["T20", "T20 wire", "S1"]

[[visits]]
darts = ["S5", "T5 hidden", "out"]

[[mismatches]]           # only for a finding that cannot be fixed (phase-M1.md §5)
photo = "s01-v02-p3"
reason = "the S5 fell out before p3 was taken"
```

Scores are `S1`–`S20`, `D1`–`D20`, `T1`–`T20`, `25`, `50`, and `miss` for a Dart in the Board
outside the double. `out` is a Dart that is not in the Board. Marks are `wire`, `hidden` (not visible
in p1), `hidden-p2` and `hidden-p3` (not visible in that Photo), and `placed` (pushed in by hand;
never in a held-out Capture session). `ingest` appends an `[ingest]` table with each Photo's camera
and capture time.

`set = "gate"` is a session read for a gate before any verdict (phase-G.md §2): `build` leaves it
out of the training records, and `freeze-held-out` leaves it out of the Held-out set. If the
verdict is phase-G.md §2's verdict 2, its Photos would need a training session and a Validation one,
per M2's rules; how they are split is decided after the verdict, not here.

A Mounted camera's session carries a `[mount]` table, the position written down at the stand, and
holds one Photo per Visit, `p1` only:

```toml
[mount]
height_cm = 160.0        # the camera's height
distance_cm = 75.0       # out from the Board's face
angle_deg = 30.0         # its angle to the Board
```

## The loop, one Capture session at a time

```bash
uv run --directory ml darts-ml ingest s01          # inbox/s01 → photos/s01, upright and stripped
uv run --directory ml darts-ml label s01           # pass 1: Hand points and Entry points
uv run --directory ml darts-ml prefill s01         # pass 2: all 80 crossings; Entry points suggested across Angles
uv run --directory ml darts-ml review s01          # pass 3: confirm each Photo (run twice, on different days, if held-out)
uv run --directory ml darts-ml check s01           # label QA; must come back clean
uv run --directory ml darts-ml overlay s01         # QA renders into overlays/s01; flip through them
```

`ingest` keeps the phone's files in `inbox/<capture-session>/`: delete them, GPS and all, once the
Photos look right. It keeps one marker: a colour profile, since a phone may tag its Photos Display
P3. It never guesses: a count that is not three Photos per Visit stops it, and so do capture times
that do not fall three to a Visit (a gap inside a Visit as long as one between two); either way it
lists the files in capture order.

**A Mounted camera's position** (phase-G.md §2) is built from the debug build's marked Visits rather
than ingested, since a marked Photo carries no capture time and a Visit has one Photo, not three:

```bash
uv run --directory ml darts-ml pull-marked --serial <serial> --delete-after   # after each position
uv run --directory ml darts-ml mounted-session s20 --day 2026-11-24 --height-cm 160 --distance-cm 75 \
  --angle-deg 30 --light day --phone "Redmi Note 8 Pro"
```

`mounted-session` takes every marked Visit under `phone-captures/<day>/` that no sheet holds yet,
orders them by the record's `keptAt`, and copies each Photo, byte for byte, to
`photos/<session>/<session>-vNN-p1.jpg`. It writes the sheet: `set = "gate"`, the `[mount]` table, one
`[[visits]]` per Visit with the Darts the owner stood behind (a Miss the app filled in to make up three
is left out), and an `[ingest]` table naming each Photo's record, `keptAt` and the app's
`boardFound`. A Visit on which the app found no Board is kept like any other: those are the Photos
the gate most needs. `--kept-from` and `--kept-until` split one day's folder between positions
pulled together. It refuses the lot, naming each file, if a record cannot be read, its Photo is
missing, not the record's width×height, turned by EXIF, or carries any metadata; and it never
overwrites a sheet or a session's Photos. Then `label`, `prefill`, `review`, `check` and `overlay`
run on it as on any session, and `predict` and `evaluate` read it with `--session`.

**The gate** (phase-M1.md §1) repeats the labelling in its own directories and compares the rounds:

```bash
uv run --directory ml darts-ml label s01 --round b      # then prefill, review and check with --round b
uv run --directory ml darts-ml label s01 --round c      # no pre-fill: click every visible crossing; then review
uv run --directory ml darts-ml repeatability s01
```

`repeatability` reads only reviewed labels. A Hand point counts as dragged, because it was placed by
hand.

## DeepDarts

phase-M1.md §4. From [IEEE DataPort](https://ieee-dataport.org/open-access/deepdarts-dataset), logged
in: `labels_pkl.zip` and `cropped_images.zip` only, never the GitHub repo's `labels.pkl` and never
`models.zip`. Unpack both into `$DARTS_DATA/deepdarts/` and keep their `sha256sum` beside them.

```bash
uv run --directory ml darts-ml deepdarts convert              # labels.pkl → deepdarts/records.jsonl
uv run --directory ml darts-ml deepdarts overlay --sample 10  # R3: drawn numbers match the Board's own
```

- **`convert`** loads `labels_pkl/labels.pkl` through an unpickler that admits only the classes the
  DataPort file names, at their 2021 paths or today's; anything else stops the load and names the
  class. It is the only step that reads the pickle. It skips, and lists, a row whose names are not
  plain file names, whose Photo is missing, or whose points are not four to seven finite numbers.
- **Each record** is phase-M1.md §4's common record, plus `split` (`train`, `val` or `test`, by
  DeepDarts' own folders) and `crop` (the row's `bbox`, unread). The four points keep DeepDarts'
  positions on the outer edge of the double wire, 170.0 mm, as `source = "deepdarts"`; the other 76
  crossings are projected through them as `deepdarts-projected`.
- **`overlay`** reads the records, not the pickle, and writes into `overlays/deepdarts/`.

## Synthetic renders

Frames from the owner's renderer, `maks-sredniawa/darts-render` (an Apache-2.0 fork of
`ahie/darts-model`; ADR-0008's 2026-11-21 amendment). Render without `--bg_image_dir`, so no Places365
photograph is in a frame, and at 768×1024: a 1536×2048 frame can outlast the laptop GPU driver's job
timeout. Only the renderer's images and labels are used, never darts-model's trained weights.
Use the renderer at `6ece137` or later, where darts-render PR #1, `feat: owner-like renders with
licence-clean assets`, landed by rebase; it brings the OFL assets, the wire-centre rings and
`--look owner`.
Frames from any earlier commit must not be used; `renders import`'s residual check refuses them.

```bash
dartboard_gen --look owner --width 768 --height 1024 --num_frames 2000 --seed 1 --output_dir <folder>
uv run --directory ml darts-ml renders import <folder> --set owner-768 --renderer <darts-render clone> --look owner
```

- **`renders import`** copies the renderer's `rgb/` and turns each `annotations/*.json` into a record in
  `$DARTS_DATA/renders/<set>/records.jsonl`, in the common record's field names with `source = "render"`.
  The renderer's rings are `board.py`'s wire centres, so its 81 keypoints (the bull, 20 segment points
  on the outer double and 20 on the inner treble wire, 40 crossings on the double wires) fit one
  homography, and the 80 Calibration points are that homography's projections of `board.py`'s own.
  A frame whose keypoints fit it worse than `--max-residual-px` (0.5) is refused and listed, which
  also refuses a frame rendered before the rings moved onto the wires. Each Dart's landing point is an
  Entry point; one off the image is dropped. Its Score is `board.py`'s, and the manifest counts any that
  differ from the renderer's own zone.
- **`manifest.json`** beside the records names the renderer's commit (from `--renderer`, a clone whose
  HEAD it reads, or `--renderer-commit`), `--look`, each `--option`, the renderer's own `manifest.json`,
  the fit residuals of the frames kept, and every frame refused with its own residual. A set is written
  once; another import needs another `--set`.

## Public sets

Real photos from a public dataset, in `$DARTS_DATA/public/<set>/`: `records.jsonl` in the common record's
field names with `source = "public"`, the Photos under `photos/`, and `manifest.json` naming the
dataset, its author, URL, licence, the mirror it was taken from with that file's SHA-256, the counts,
every frame refused with its reason, and the credit line. `train --public` refuses a set whose manifest
lacks any of `title`, `author`, `url`, `licence`, `licence_url`, `mirror` (with its `sha256`),
`records`, `refused` or `credit`, and copies all but `refused` into the run's `config.json`; it checks that
they are there, not what they hold. Only a set whose licence allows a public app with a tip is imported (ADR-0008's
licence table).

**`dart-pose-v6`** (imported 2026-11-21) is *Dart Pose v6* by `jonas-workspace-lm7ia` on Roboflow
Universe, CC BY 4.0, taken from the zip mirrored at `huggingface.co/datasets/Bayernator/scorelens-rf10-quellen`
(the SHA-256 is in its manifest). It was imported by hand, not by a `darts-ml` step:

- one copy per source photo, the un-augmented one, cut out of Roboflow's 720×720 letterbox back to
  640×480 and re-encoded at JPEG quality 95; Roboflow's auto-contrast stays in the pixels;
- each dart's tip label is an Entry point (`source = "public-label"`), its flight end kept as `flight`;
- the 80 Calibration points are run `2026-11-19-darts-640-s2-ring-ext`'s: `locate()`'s RANSAC
  homography projects all 80, and `detected` marks the ones the model itself found as inliers. A
  frame with under 40 inliers, a fit residual over 2.5 px, a fit that jumps against both neighbouring
  frames, no board found, or a tip off the board is refused, as are the 4–7-dart images, which carry
  a second, wrong label per dart. 567 of 1,317 source photos are kept, with 1,574 darts.

Credit, as the Credits screen would carry it if a model trained on the set ships:
*Dart Pose v6 by jonas-workspace-lm7ia, Roboflow Universe,
https://universe.roboflow.com/jonas-workspace-lm7ia/dart-pose-v6-ovihb, CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Photos cropped and re-encoded; board points added by
this app's model.*

**What it trains, and what it does not.** A detected Calibration point weighs 1, one the model only
projected weighs `PROJECTED_WEIGHT` (0.5, as DeepDarts' projected crossings do), so a run is not
pushed hard towards the earlier model's own guesses. The Entry points are the dataset's labels and are
the real signal. Its frames are consecutive snapshots from fixed USB webcams at steep side angles
round one board (the frame drifts slightly between snapshots), `snapshot_N` from one and
`snapshot_usb_cam1_N` / `snapshot_usb_cam2_N` from two cameras at the same moment, so a random split
would put a frame's twin in training. The held-out frames are instead, per series (the frame name
without its number and `_camK`), the last tenth of its frame numbers, every camera's frame at those
numbers, and the 5 numbers before that block are dropped from training (`public_split`). The figures
on them are read beside DeepDarts val as `public_figures` and never choose `best.pt`. A held-out frame
shares its camera's viewpoint with that camera's training frames, so `public_figures` read the same rig,
not new angles. Their Calibration
truth is the earlier model's, so their Calibration figures say how far a run stays with it; their
Entry figures are the useful reading.

## Training (phase M2)

[`docs/phase-M2.md`](../docs/phase-M2.md): the model, its training samples, the decoder and the two
passes, and the commands that train it and turn it into predictions.

```bash
uv run --directory ml darts-ml train --name board-512 --board-only   # C: Calibration points only
uv run --directory ml darts-ml train --name darts-512 --init <run>   # D: Entry points added, from C's weights
uv run --directory ml darts-ml train --name darts-640-s2-ring --size 640 --init <run>   # after D: Entry head at stride 2
uv run --directory ml darts-ml train --name renders-640 --size 640 --init <run> --renders owner-768 --render-weight 0.5   # DeepDarts plus renders
uv run --directory ml darts-ml train --name public-640 --size 640 --init <run> --public dart-pose-v6 --public-weight 0.3   # DeepDarts plus a public set
uv run --directory ml darts-ml evaluate-marked --run <run>          # the owner's marked Visits: read once a run is chosen
uv run --directory ml darts-ml deepdarts score --run <run> --split test   # R2, R3: a run's figures on DeepDarts
uv run --directory ml darts-ml deepdarts score --run <run> --as-stored   # phase 1 §1: on val, as MediaFiles stores a Photo
uv run --directory ml darts-ml deepdarts score --run <run> --entry-threshold 0.3   # on val, keeping Entry points at that heat
uv run --directory ml darts-ml deepdarts tune --run <run>            # each rule for keeping Entry points, on val only
uv run --directory ml darts-ml deepdarts grouped                     # pairs under 10 mm the targets decode as two
uv run --directory ml darts-ml predict --run <run>                   # the predictions file, on the Held-out set
uv run --directory ml darts-ml export --run <run> --format onnx      # E: the model in a runtime's format, into the run folder
uv run --directory ml darts-ml export-parity --run <run> --format onnx   # E: its points against PyTorch's, on val
ANDROID_SERIAL=emulator-5610 uv run --directory ml darts-ml runtime-bench --run <run>   # E: each runtime's size per ABI, and the model's latency on a device
uv run --directory ml darts-ml train --probe                         # gate A: time 200 steps (--device cpu for parity)
uv run --directory ml darts-ml phone-parity --run <run> --photos 200   # phase 1's gate: the app's pipeline against locate()
uv run --directory ml darts-ml phone-fixtures --run <run>           # phase 1's unit-test fixtures, into app/src/test/resources/
```

- **`train`** writes each run to `$DARTS_DATA/runs/<date>-<name>/` and refuses a folder that exists:
  `config.json` (every option, the commit, the hardware), `losses.jsonl` (one line per step),
  `epochs.jsonl` (one line per epoch, with the validation figures) and the weights, `last.pt` and
  `best.pt`. After each epoch it reads DeepDarts' `val` split through both passes, as `predict`
  would, and keeps `best.pt` from the epoch that reads best: Photos scored exactly right, then Board
  found; with `--board-only`, Board found, then the worse wire row's median. Weights never enter git.
- **`--renders SET[,SET]`** adds render sets to the training samples. A tenth of each set's frames,
  whole frames picked by a hash of `--seed` and the frame, so another set never moves them, is held
  out as rendered val: read after every epoch through both passes and written to `epochs.jsonl` as
  `render_figures`, never used to keep `best.pt`, which stays DeepDarts val's. `--render-weight W`
  (default 0.5) draws renders W times as often as DeepDarts Photos overall, whatever the sizes, so
  0.5 makes them a third of each batch; an epoch is then DeepDarts' count times 1 + W draws.
  `config.json` records the sets, each set's renderer commit and look, and both counts. With
  `--renders`, DeepDarts Photos are drawn with replacement, so about 63% of them are seen in an
  epoch and a renders run's DeepDarts sampling differs from a baseline's. Without `--renders` the
  loader is the one before renders came. Nothing under `phone-captures/` is ever a
  training or a choosing sample.
- **`--public SET[,SET]`** adds public sets (*Public sets*) the same way: their held-out frames are
  read after every epoch as `public_figures`, never used to keep `best.pt`. `--public-weight W`
  (default 0.3) draws public frames W times as often as DeepDarts Photos overall, beside renders'
  own weight; 0.3 alone makes them about a quarter of each batch. `dart-pose-v6` keeps 497 frames
  for training, so at 0.3 an epoch over DeepDarts' 12,830 draws each about 7.7 times, augmented.
  `config.json` records each set's title, author, URL, licence, mirror, record count and credit,
  and both counts.
- **`--freeze-norm`** (with `--init`) keeps the BatchNorm running statistics of the run it starts
  from, while a BatchNorm that starts fresh (such as a stride-2 Entry head's from a stride-4 run)
  still learns its own; the weights still train. Without it, a set unlike DeepDarts drags them
  whatever the learning rate: on 2026-11-21, one epoch of the shipped run with `--public dart-pose-v6` at lr 1e-12 took
  DeepDarts val from 737 to 694 exactly right, while the same epoch on DeepDarts alone held at 736.
  The public frames are far brighter after normalising (a channel mean near −0.5 against −1.4).
- **The samples** are augmented by default (`--no-augment` turns it off): the Board plane re-viewed
  from a camera orbiting it up to 60° to either side, 20° up or down and rolled up to 30°; framed as
  the second pass frames it (the outer double ring filling 70–90% of the side) seven times in ten,
  and as a whole Photo (25–70%) otherwise; brightness, contrast, colour and blur. Labels move with the
  pixels through the same matrix, and nothing mirrors the Board. The ranges are `Ranges` in
  `augment.py`.
- **Two heads.** The Calibration heatmaps and their offsets come out at stride 4; the Entry heatmap and
  its offsets at stride 2 (`--entry-stride 2`, the default), from a small head over the stride-4
  features and the backbone's stride-2 layer. `--entry-stride 4` is C's and D's layout. `--init`
  loads every weight whose name and shape fit, prints the rest, which start fresh, and starts a
  stride-2 model from a stride-4 run with its Calibration outputs unchanged. `predict` and
  `deepdarts score` read either layout from the weights themselves.
- **The ring.** A false Entry peak between 4 and 20 mm of Board from a labelled Entry point, where its
  own barrel and flight show, costs five times the ordinary penalty, except within 4 mm (or two
  cells) of any labelled Entry point, a close neighbour's tip included. `--ring-weight 0` turns it
  off and `--ring-mm INNER OUTER` moves it; `config.json` records all three.
- **Two passes** (phase-M2.md §2): the whole Photo, letterboxed, finds the Board; a square around the
  outer double ring, the ring filling 80% of it, gives the points kept. A Calibration point is its
  channel's peak from 0.25 up, an Entry point every local maximum of its channel from the decode
  floor (the `EntryRule` threshold; `deepdarts tune` decodes from its grid's lowest), both refined by
  their offsets. A Photo keeps at most three Entry points, the most confident, each over the
  `EntryRule` threshold, 0.25, chosen with `deepdarts tune`, and none beyond 1.8 Board radii
  (ADR-0008, 2026-11-23); one under 0.5 is `low_confidence`.
  RANSAC keeps the crossings within 3 mm of a four-point fit, and a Board needs eight of them.
- **`predict`** reads the frozen manifest, refuses a Held-out set that fails `verify-held-out`, and
  writes `predictions-held-out-<weights>-<time>.json` into the run folder, naming the run and the
  SHA-256 of its weights. Reading it with `evaluate` is one of phase M2's three readings (D6).
- **The fences.** DeepDarts' `test` split is served only to `deepdarts score`, never to training or
  to choosing a run. The owner's records (`build/records.jsonl`, from checkpoint F) are refused
  outright when one belongs to a held-out Capture session, by name or by the bytes of its Photo or
  label, and the Validation sessions (`s09`, `s14`) are never in the training split. An inferred
  Entry point, a Dart hidden in that Photo, is never a training target.
- **`export`** writes `<weights>.onnx` (`--format onnx`, through `torch.onnx.export`) or
  `<weights>.tflite` (`--format litert`, through Google's `litert-torch`) into the run folder, beside a
  `.json` naming the weights' SHA-256, and prints its size in bytes, its operations and any left
  outside the runtime's own set. It takes one 1×3×size×size float32 image and returns the raw heads;
  decoding stays in Python, and in Kotlin later. **`export-parity`** runs that file in its own runtime
  (ONNX Runtime, the LiteRT interpreter) and the weights in PyTorch, both on the CPU, through both
  passes on DeepDarts' `val` Photos, and prints how far each point moved in Board millimetres against
  phase-M2.md §5's 0.05 mm, the points only one runtime kept, and the Photos scored differently. It
  refuses a file whose weights have changed since it was exported. The `export` extra (ONNX's tools
  and both runtimes) syncs beside `cpu` or `rocm`. The LiteRT converter is the `litert` extra, a third
  PyTorch flavour (the CPU build plus the converter), because its `xdsl` holds typing-extensions below
  4.13; give it a venv of its own and run with the same variable:
  `UV_PROJECT_ENVIRONMENT=~/.venvs/darts-ml-litert uv sync --locked --directory ml --extra litert --extra export`.
- **`phone-parity`** is phase 1's gate (`docs/phase-1.md` §1, R1). It needs the `export` extra (the
  LiteRT interpreter), one device in `adb devices` (or the one `ANDROID_SERIAL` names) with the debug
  app and its test APK installed, and the run's `best.tflite` byte for byte the app's
  `assets/model/darts.tflite`. It takes `--photos` of DeepDarts' val Photos spread evenly through the
  split, the same ones every time, and `--display-p3` of those again (default 20) rewritten as the
  same scene in Display P3's numbers and tagged with its profile, as a Xiaomi stores a Photo. Those
  copies check the app's half: `MediaFiles` stores them as sRGB, and the app reads the stored files
  as Python reads them. Python only reads what `MediaFiles` wrote, so they never reach it as P3;
  `test_locate.py` holds Python's reading of a P3 Photo. It pushes them to the app's external files
  (`parity/source/`, made writable for the app), has
  `PhoneParityTest#writesEachPhotoThroughMediaFiles` write each through `MediaFiles` as a Photo,
  pulls the written files back, runs `locate()` on them here with the same model, pushes that as
  `expected.json`, has `PhoneParityTest#matchesPythonOnEachPhoto` run the app's `PhotoReader` on each
  and compare, and prints the phone's report. Everything it moves lives under
  `$DARTS_DATA/phone-parity/<run>/` and on the device, never in the repo. Install with `adb install`,
  not `connectedAndroidTest`, which uninstalls the app, and its files, when it finishes:

  ```bash
  ./gradlew assembleDebug assembleDebugAndroidTest
  adb install -r -t app/build/outputs/apk/debug/app-debug.apk
  adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
  uv run --directory ml darts-ml phone-parity --run 2026-11-19-darts-640-s2-ring-ext --photos 200
  ```

  Without the pushed files both test methods are skipped, so CI's instrumented legs stay green.
- **`pull-marked`** copies the debug build's marked Visits (`docs/phase-1.md` §4) off the phone or
  emulator `--serial` names into `$DARTS_DATA/phone-captures/<date>/`: each Photo
  (`<photo-uuid>.jpg`) and its record (`<photo-uuid>.json`), read from the app's `files/marked/`
  over `adb run-as`, so only a debug build answers. A file already under any date is skipped while
  its size and time match the phone's, and copied again over its first copy when the Visit was kept
  again since; each copy takes the phone's time. `--delete-after` then deletes on the phone each file
  that is here unchanged, and nothing else.

  ```bash
  uv run --directory ml darts-ml pull-marked --serial <serial> [--delete-after]
  ```
- **`evaluate-marked`** reads the pulled marked Visits as the owner's real test set: each Photo
  through a run's model and both passes, against the owner's corrected Darts. It prints Board found,
  Visits scored exactly right (the Scores as multisets, a Dart the owner added with no point
  included, each side made up to three with Misses as the app makes up a reading), Darts right,
  and how far each Entry point lies from the owner's in Board mm through the run's own homography, split into the Darts the owner moved and those whose point the owner kept; a
  Dart whose Score was corrected without moving it gives no point. Beside it, the app's reading as
  kept on the phone, from the same records. A Visit whose Photo is not the record's width×height, or
  carries an EXIF orientation other than 1, is skipped and named with the reason, and so is one a
  Capture session's sheet names in its `[ingest]` table (`mounted-session` built it into that
  session). It writes nothing. **Read once:** these Visits choose no
  run, threshold or setting, or they stop measuring anything; the step says so as it reads them.
- **`phone-fixtures`** writes what the app's JVM tests hold the Kotlin port to, into
  `app/src/test/resources/scoring/`: `scores.tsv` (every bed, 0.1 mm either side of every wire, and
  `tests/scoring-cases.toml`, each with `board.score`'s answer), `rng.json` (the sets of four
  `default_rng(0)` draws for RANSAC), `warp.json` (a small Photo through `warp`, Pillow's bytes) and,
  with `--run`, `heads-*.json`: three Photos' heads from that run's LiteRT model, every logit under
  −3 lowered so the files stay small, with what `decode` and `_board` give for them (a strip with
  Calibration points and no Board, two Darts in one bed, three in three beds). It also writes
  `MediaFilesTest`'s Display P3 source, `app/src/androidTest/assets/display-p3-red.jpg`: sRGB red in
  Display P3's numbers, tagged with `images.display_p3()`, since API 26's encoder embeds no P3
  profile in a Bitmap it compresses. Run it again after changing `board.py`, `decode.py`,
  `homography.py`, `augment.py` or `images.py`, and commit what changed: `test_phone.py`'s
  `CommittedFixturesTest` regenerates the files and re-decodes the stored heads, and fails while the
  committed ones are stale.
- **`runtime-bench`** downloads each runtime's Android AAR, pinned by version and SHA-256 in
  `runtime_bench.py` (LiteRT 2.3.2 from Google Maven, `litert` and `litert-api`; ONNX Runtime 1.32.0
  from Maven Central), into `$DARTS_DATA/runtimes/`, and prints the native libraries each would add
  per ABI, uncompressed and deflated. With `--run` and one device in `adb devices` (or the one
  `ANDROID_SERIAL` names), it times each exported model there whose record matches the run's
  weights (a format never exported, or exported from other weights, is named and left out), the
  warm-up excluded, at each `--threads` count (0 is the runtime's default): LiteRT through Google's
  prebuilt `benchmark_model`
  2.3.1 (no 2.3.2 build is published), ONNX Runtime through `android/OrtBench.java`, compiled with
  `javac` and the SDK's `d8` against the AAR's own classes and run under `app_process`, since ONNX
  Runtime publishes no Android `onnxruntime_perf_test`. It cleans up after itself on the device and
  never installs an app. An x86_64 emulator runs on the host's CPU with the emulator's virtual CPU
  in front of it, so its figures say little about a phone's.
- **`--probe`** writes `runs/probes/<device>-<size>-<batch>-<steps>steps[-bf16][-cl]-<time>.json`, never
  over an earlier one, with the commit and any `MIOPEN_*` settings it ran under.

`--device` is `auto` (the GPU if PyTorch sees one, else the CPU), `gpu` or `cpu`. A GPU is an AMD one
through ROCm or an NVIDIA one through CUDA; PyTorch names both `cuda`, and the run prints the real
name. `--bf16` (bfloat16 autocast) and `--channels-last` are for the GPU; leave both off. `--bf16`
needs its kernels in MIOpen's database first (below). Tuned, it read 9% faster than float32 over 200
steps, and no run has been trained in it (phase-M2.md §2).

MIOpen ships no tuned kernels for gfx1151. `train`, `predict` and `deepdarts score` keep its user
database in `$DARTS_DATA/miopen/` (an `MIOPEN_USER_DB_PATH` already set wins), and one probe fills it
for a new input size, batch size or precision:

```bash
MIOPEN_FIND_ENFORCE=SEARCH uv run --directory ml darts-ml train --probe          # slow once; later runs ~12% faster
MIOPEN_FIND_ENFORCE=SEARCH uv run --directory ml darts-ml train --probe --bf16   # the same for bfloat16, about 3.5 min
```

**Run a search only after a restart, before the laptop sleeps.** MIOpen chooses a kernel for a shape
it has not run before by timing each candidate, and on the Radeon 8050S the GPU's timer reads zero
once the laptop has been suspended and resumed. Every search then stops with
`miopenStatusUnknownError`, in float32 as much as in bfloat16, until the next restart (phase-M2.md
§2), and the step that hit it says so. A shape already in the database runs in any session.
Inference pads a short last batch to the run's batch size and drops the padding's output, so it only
ever runs shapes training has already searched.

## The Held-out set and the bar

phase-M1.md §6 and §7. The bar's numbers live once, in `BAR` in `evaluate.py`, and `BarTest` pins
them; a change to the bar is a change to §7 first.

```bash
uv run --directory ml darts-ml freeze-held-out     # G: hash every held-out file into ml/splits/held-out.toml
uv run --directory ml darts-ml verify-held-out     # fails on any held-out file missing or changed since
uv run --directory ml darts-ml build               # build/records.jsonl, refusing every held-out Photo
uv run --directory ml darts-ml evaluate --predictions labels           # R7: the harness reads perfect as perfect
uv run --directory ml darts-ml evaluate --predictions predictions.json # a model's reading
uv run --directory ml darts-ml predict --run <run> --session s20                   # a gate session, outside the Held-out set
uv run --directory ml darts-ml evaluate --predictions <file> --session s20        # read against the same bar
```

- **`freeze-held-out`** freezes every Capture session whose sheet says `set = "held-out"`, and only
  once `check` is clean on each. The manifest holds the SHA-256 of each held-out Photo and label, and
  of each held-out sheet and review manifest; it is committed, and a later change to it says why in
  its commit body. It refuses to overwrite an existing manifest unless given `--replace`, which
  states the intent and skips none of the checks. A frozen Capture session is only ever added to:
  it refuses any freeze that would leave out one the manifest, or any commit of it, froze, even
  once its sheet says training or the manifest is deleted.
- **`verify-held-out`** fails on a frozen file that is missing or changed, on a Photo a frozen sheet
  lists and the manifest leaves out, on a frozen Photo its frozen sheet does not list, on a sheet it
  cannot read, on a Capture session an earlier commit of the manifest froze and this one leaves out,
  and on a held-out sheet the manifest does not freeze. `evaluate` runs the same check first and
  reads nothing that fails it.
- **`build`** writes one record per reviewed training Photo (phase-M1.md §4, *The common record*). It
  refuses a Photo whose sheet says held-out, one of a Capture session the manifest or any earlier
  commit of it freezes, and one whose Photo or label has the bytes of a held-out one. It needs the
  frozen manifest to run.
- **`evaluate`** counts Photos and Visits from the manifest, never from the predictions: a Photo the
  predictions leave out is a Board not found. It exits 0 when the bar is met and 1 when it is not.
- **`--session`**, on `predict` and `evaluate` in place of `--manifest`, reads named Capture sessions
  whose sheet says `set = "gate"`, such as a Mounted camera's position: each only once `check` is
  clean on it, never a training session the model may have learnt from, and never a held-out one,
  which is read only through the frozen manifest. Photos are counted
  from the sheets; a one-Angle session reads B2 from p1 alone and leaves p2 and p3 at 0/0.

### The predictions file

JSON, pixel positions on the held-out Photo as ingested:

```json
{
  "photos": {
    "s04-v01-p1": {
      "calibration": {"do-5-20": [812.4, 140.9], "ti-6-10": [1180.2, 603.5]},
      "entries": [{"x": 940.1, "y": 512.8}, {"x": 951.7, "y": 498.0, "low_confidence": true}]
    }
  }
}
```

- `calibration` names crossings from `board.py`'s list. *Ĥ* is the least-squares homography through
  every point given, so a model that fits with RANSAC passes its inliers only. Fewer than four points,
  or a degenerate set, is a Board not found. A position that is not a finite number, here or in
  `entries`, is refused: the file is broken, not the Board unseen.
- `entries` are Entry points. `low_confidence`, optional, is the model's own flag; it feeds only the
  trigger figure below.

### How the figures beside the bar are read

The plan names them; these are the rules this code applies where it leaves one open.

- **Merged** (B2 on all three Photos, and the Visits hidden in p1): each Photo's Entry points, in
  board mm, join the Darts found so far one to one, nearest pair first, within 2 mm (pre-fill's
  same-Dart distance); the rest are new Darts. A merged Dart scores at its points' mean.
- **Darts scored right**: over the Visits B2 counts, from p1, the predicted and recorded Scores in
  common as multisets, out of the Darts in the Board.
- **Triggers** (ADR-0008), on p1 alone: the Board not found; fewer Darts found than were thrown, `out`
  included; a `low_confidence` Entry point; an Entry point within 2 mm of a wire's centre line. The
  fourth, Photos disagreeing on a segment, needs a second Photo and is not read on p1.

## labelme

`label` and `review` open one labelme window per Photo through `uvx`, so labelme (GPL-3.0) stays out
of this lockfile and out of anything that trains or ships. The pin lives in `labelme.py`:

- **labelme 7.9.1**, the newest release at least two weeks old on 2026-11-13.
- **Resolved as of 2026-10-26** (`uvx --exclude-newer`). labelme's own dependencies are unbounded,
  and on 2026-11-13 a fresh `uvx labelme==7.9.1` pulled osam 0.11.3, released that day, which crashes
  7.9.1 at start-up (`module 'osam' has no attribute 'apis'`). Resolving as of the release date gives
  the environment 7.9.1 shipped against.
- **`--python`, the version in `.python-version`**, so the interpreter labelme runs on does not
  depend on the machine.
- **`--config '{with_image_data: false, auto_save: true}'`**, so a stray `~/.labelmerc` cannot embed
  the Photo in a label: given `--config`, labelme does not read `~/.labelmerc`.
- **Offline.** The only network code in 7.9.1 is its AI tools' model download, which runs only when a
  model's download button is clicked; there is no setting that turns the tools off. The windows run
  with `UV_OFFLINE=1` and every proxy variable pointed at an unreachable address, so a click by mistake
  fails instead of downloading. Checked on 2026-11-13 by running a window for 20 s under
  `strace -f -e trace=connect`: no connection of any kind. Only `label` and `review` first run
  `uvx … labelme --version` with the network, to fetch labelme into uv's cache.

To move the pin: pick the newest release at least two weeks old, set `RESOLVED_AS_OF` to the day
after it, read its CLI (`--config`, `--labels`, `--validate-label`, `--label-flags`, `--output`) and
`_config/default_config.yaml` again, and open one Photo with a pre-filled label before relabelling
anything.

## Scoring at a wire

`board.py` scores a board-millimetre point by ADR-0008's bands with *w* = 1.5 mm. A point that lands
inside a wire scores on the side of the wire's centre line it falls on, since a Dart enters on one
side or the other (WDF §3.03); a point exactly on a centre line scores on its outer, or clockwise,
side. Board millimetres put x to the right and y up, with the bull at the origin.
`tests/scoring-cases.toml` holds the cases phase 1's Kotlin test reads too.

## Tests

```bash
uv run --directory ml python -m unittest discover -s tests
```

They need `jpegtran`, PyTorch from either extra synced as in Setup (`uv run` alone installs neither),
and no data: the Photos and labels are built from `board.py` in the test. The export tests skip what
an extra they lack would run: ONNX without `export`, LiteRT without `litert`.

## Dependencies and their licences

Re-read this table whenever the lockfile gains a package. The rule is ADR-0008's, with its 2026-11-13,
2026-11-17 and 2026-11-19 amendments; the table lists every bundled library that rule covers, in its last column.

| Package | Licence | Bundled in the Linux wheel |
| --- | --- | --- |
| NumPy 2.5.4 | BSD-3-Clause | OpenBLAS (BSD-3-Clause); libgfortran (GPL-3.0 with the GCC Runtime Library Exception); libquadmath (LGPL-2.1-or-later) |
| Pillow 13.0.0 | MIT-CMU | libjpeg-turbo, libpng, zlib, libtiff, libwebp, lcms2, OpenJPEG, HarfBuzz, Brotli, libavif and others, all permissive; FreeType under its FTL (dual-licensed FTL or GPL-2.0) |
| tomli-w 1.2.0 | MIT | — |
| pandas 3.1.0 | BSD-3-Clause | — |
| python-dateutil 4.0.0 | BSD-3-Clause | — |
| tzdata 2026.6 | Apache-2.0 | — |
| PyTorch 2.14.1 (`cpu` and `rocm` extras) | BSD-3-Clause, with Apache-2.0, MIT, BSD-2-Clause and BSL-1.0 third-party parts | libgomp (GPL-3.0 with the GCC Runtime Library Exception) |
| torchvision 0.29.1 | BSD-3-Clause | — |
| onnx 1.23.2, onnx-ir 1.1.0 (`export` extra) | Apache-2.0 | — |
| onnxscript 0.7.2, onnxruntime 1.31.1 (`export` extra) | MIT | **Eigen (MPL-2.0)**, statically linked; Mbed TLS (Apache-2.0 OR GPL-2.0-or-later), which its ThirdPartyNotices take under Apache-2.0; nothing under the GPL or LGPL alone |
| ai-edge-litert 2.3.0, flatbuffers 25.12.19, ml-dtypes 0.6.0 (`export` extra) | Apache-2.0 | the LiteRT runtime, with **Eigen (MPL-2.0)** compiled in, which its licence file does not list |
| protobuf 7.36.2 | BSD-3-Clause | — |
| packaging 26.3 | Apache-2.0 or BSD-2-Clause | — |
| backports-strenum 1.3.1 | MIT | — |
| **tqdm 4.70.1** (`export` extra, through ai-edge-litert) | **MPL-2.0 AND MIT** | — |
| litert-torch 0.10.0, litert-converter 0.5.0, litert-lm-builder 0.19.0, ai-edge-quantizer 0.10.1 (`litert` extra) | Apache-2.0 | — |
| jax 0.12.0.1, jaxlib 0.12.0.1, transformers 5.22.1, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 2.4.0, hf-xet 1.8.0, kagglehub 1.0.3, kagglesdk 0.1.38, sentencepiece 0.2.2, absl-py 2.5.1, fire 0.7.1, requests 2.34.2, wadler-lindig 0.1.8 (`litert` extra) | Apache-2.0 | — |
| torchao 0.18.0, scipy 1.18.1, click 8.5.0, idna 3.20, httpx2 2.16.0, httpcore2 2.16.0, multipledispatch 1.0.0 (`litert` extra) | BSD-3-Clause | scipy: OpenBLAS, libgfortran and libquadmath, as NumPy |
| regex 2026.9.29 (`litert` extra) | Apache-2.0 AND CNRI-Python | — |
| pygments 2.21.0 (`litert` extra) | BSD-2-Clause | — |
| xdsl 0.28.0, jaxtyping 0.3.11, lark 1.3.1, rich 15.0.0, markdown-it-py 4.2.0, mdurl 0.1.2, pyyaml 6.0.3, typer 0.27.3, tabulate 0.10.0, termcolor 3.3.0, tomli 2.5.0, opt-einsum 3.4.0, ordered-set 4.1.0, immutabledict 4.2.1, anyio 4.14.2, h11 0.16.0, charset-normalizer 3.5.2, urllib3 2.8.0, truststore 0.10.5, annotated-doc 0.0.5 (`litert` extra) | MIT | — |
| shellingham 1.5.4 (`litert` extra) | ISC | — |
| **certifi 2026.10.23** (`litert` extra, through requests) | **MPL-2.0** | — |
| ROCm 7.14.1 runtime (`rocm`, `rocm-sdk-core`, `rocm-sdk-libraries`, `rocm-sdk-device-*`; `rocm` extra only) | MIT and Apache-2.0, per component | under the LGPL: elfutils' libelf, libdw and libasm (LGPL-3.0-or-later, or GPL-2.0-or-later), libnuma, libnl, libmnl, util-linux's libblkid and libmount (LGPL-2.1-or-later), GMP and MPFR (LGPL-3.0-or-later). **Under the GPL**: SuiteSparse's libcholmod with its Supernodal and Modify modules (GPL-2.0-or-later), loaded with the runtime's sparse solvers and never called by training (ADR-0008, 2026-11-17). The rest permissive: libdrm, ncurses, SQLite, zstd, zlib, LLVM and others |
| triton-rocm 3.8.0 (`rocm` extra only) | MIT | — |
| sympy 1.14.0, mpmath 1.3.0 | BSD-3-Clause | — |
| networkx 3.7, fsspec 2026.9.0, Jinja2 3.1.6, MarkupSafe 3.0.4 | BSD-3-Clause | — |
| filelock 4.2.7, setuptools 84.2.1 | MIT | — |
| typing-extensions 4.16.0 (4.12.2 under `litert`) | PSF-2.0 | — |

Outside the lockfile: **labelme** (GPL-3.0) runs beside it through `uvx` and never ships;
**jpegtran** (libjpeg-turbo, IJG and BSD-style) is a system tool. **OpenCV is not used**: nothing in
the loop needs it.
