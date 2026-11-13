# Phase M1 — The owner's Photos are taken, labelled and split beside DeepDarts, and the bar for phase 1 is set before training

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
serves [ADR-0008](adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md) and
reopens nothing in it. It gives the ADR one dated amendment at A: the exact set of Calibration
points, where the DeepDarts labels are taken from, and the wording of its licence rule (§0, §2,
§4). [`CONTEXT.md`](../CONTEXT.md) is owed three terms at A, **Capture session**, **Held-out set**
and **Hand point**, because `ml/` code names all three.

**What closing this phase means.** Today there is an ADR and no data. After this phase, the
`ml/` folder holds the code that ingests, labels, checks and splits Photos. Outside the repo there
are about 800 of the owner's handheld Photos of about 270 Visits, every one labelled with its
Calibration points and Entry points, and every Visit carries the Score the owner read at the Board.
DeepDarts' 16,050 Photos are converted into the same records, unless the labels cannot be had (D5).
A third of the owner's Capture sessions are frozen as the Held-out set, by a hash manifest in git.
The bar for opening phase 1 is written below and computed by code that has been tested on perfect
and on broken predictions. No model exists yet. The difference a reader can check: **`darts-ml
verify-held-out` passes against the committed manifest, and `darts-ml evaluate --predictions
labels` reads 100% found and 0 mm on the Held-out set, with B2 short of 100% only by the counted
Visits whose sheet records an open mismatch on p1**, so the bar is a command before it is a result.

**`PLAN.md`'s paragraph holds, with one addition said here first.** It names the bar but not where
the truth comes from. A label is the owner's reading of a Photo, and DeepDarts' own labels disagreed
with the Score recorded at the Board on 2.4% of Darts (paper §5.3). So every Visit's Score is also
written down at the Board, before the Darts come out (§3). The bar is measured against that, and
the labels are checked against it.

---

## Decisions for the owner

All six were decided on **2026-11-13**, each as recommended. Two review questions were settled the
same day and are written into D1 and D5: which Visits B2 counts (§7), and what happens if DataPort
asks for a subscription (§4). B2's rule is why D3 now has 18 Capture sessions rather than 16.

| # | Decision | Decided 2026-11-13 |
| --- | --- | --- |
| **D1** | **The bar for opening phase 1** (§7) | **Board:** found in ≥ 98% of held-out Photos. At the treble wires and at the double wires separately, the error has a median ≤ 0.5 mm and a 95th percentile ≤ 1.0 mm. **Visits:** ≥ 80% of the held-out Visits whose Darts are all visible in their front Photo are scored exactly right from it alone, over at least 60 such Visits. A Visit with a Dart hidden in p1 is left out of the bar and counted in a figure of its own, which is phase 2's input |
| **D2** | **Which phones** | Two phones of different makes: your own and one other, such as an old phone or one borrowed for a few Capture sessions. If the second falls through, the model has only ever seen one lens and one image pipeline; that becomes a *Known gap* |
| **D3** | **How much to capture**: your hours | 18 Capture sessions of 15 Visits, about 810 Photos: 12 training and 6 held-out. The two held-out Capture sessions beyond the 16 first proposed follow from D1's B2 rule (§6). That is about 9 hours at the Board and about 31 at the labelling tool (*The owner's hours*). The floor is 8 training Capture sessions, and §3 says which go first. The pilot (B) measures the real minutes per Photo before the rest is taken |
| **D4** | **Where the data lives, and its backup** | `~/darts-scorer-data` on this machine (`DARTS_DATA`), backed up to an external disk. **No cloud drive**, and no phone's cloud backup either (§3): the Photos show your home, and the labels are hours of work you cannot buy back |
| **D5** | **Where DeepDarts comes from** | IEEE DataPort, with a free account, because the licence is stated there (§4). If DataPort asks for a paid subscription, the author is asked in writing for the labels under CC BY 4.0. With no grant three weeks after the ask, M1 goes on with the owner's Photos alone (§4 says what that costs). Record the source's SHA-256 in R2 |
| **D6** | **A second Board** | Not now. If one Capture session on someone else's Board comes for free (a friend's, a club's), take it and put it in the Held-out set. Its Photos then show someone else's home, so ask first. Otherwise it stays a *Known gap* |

---

## 0. What this phase inherits

- **ADR-0008's geometry and rules**: the WDF board table, *w* = 1.5 mm, the segment order, a Dart
  scoring on the side of the wire its Entry point enters, the 2 mm wire margin, and the licence
  rule for training code. This phase writes the geometry as code once (`board.py`, §2). Phase 1
  ports it to Kotlin and reads the same test cases (*Tests*).
- **The licence rule, as this phase applies it: permissive licences only** (Apache, MIT, BSD and
  the like) for the code we adapt, train with, or ship, and no copyleft code (GPL, AGPL) among it. A
  runtime library bundled inside a dev tool's wheel under a runtime exception or the LGPL is
  allowed and listed in `ml/README.md`'s licence table, such as NumPy's libgfortran and libquadmath:
  `ml/` never ships, and the app ships only weights. labelme, which is GPL-3.0, runs beside `ml/`
  through `uvx` and never ships (§5). ADR-0008 words the rule as "Apache or MIT code only", while
  its own table already counts BSD-3 ncnn as usable, and §2's NumPy and pandas are BSD-3. So the
  ADR's wording is amended to "permissive" at A, and `PLAN.md`'s Phase M2 line with it.
- **A `.gitignore` that already fences `ml/`** (`d1e24ce`). Everything under `ml/` is ignored except
  `.py`, `.toml`, `.yaml`, `.yml`, `.md`, `.lock` and `.python-version`. Checked on 2026-11-13 with
  `git check-ignore --no-index`: `pyproject.toml`, `uv.lock`, `.python-version`, `src/**/*.py`,
  `splits/held-out.toml` and `README.md` are tracked. `.jpg`, `.json`, `.pkl`, `.txt`, `.onnx` and
  `.tflite` are ignored. So photos, labelme's JSON labels, DeepDarts' pickle and any weights cannot
  be committed by accident, and this phase needs no change to the file.
- **The repo's Python is stdlib-only scripts run with `python3`**, with tests by `python3 -m
  unittest discover -s scripts` in CI. `ml/` cannot be stdlib-only: it needs NumPy and Pillow,
  and later a training framework. That is why it gets a locked environment of its own (§2),
  not a change to how `scripts/` runs.
- **The asymmetry that shapes the phase: code is cheap and can go ahead, while the owner's hours
  cannot be got back.** A capture protocol that turns out unlabellable at 1 mm, found after 18
  Capture sessions, costs most of 40 hours. So the gate (B) is one small Capture session put
  through the whole loop before anything else is captured. The code it needs (A) comes first
  because it is small.

## What is in, and what is deliberately not

**In:** `ml/` as a uv project with a lockfile; the Board geometry and scoring as tested code;
ingest, pre-fill, review, label QA and overlay tools around a pinned local labelling tool; the
DeepDarts dataset downloaded, converted through a restricted unpickler, and checked; the capture
protocol and its Capture sessions; labelling and QA; the Held-out set frozen by manifest; the bar
written here and as an evaluation command; a CI job for `ml/`'s tests.

**Not in, and each with a reason rather than a phase:**

- **Training, the framework, the runtime, the input size, augmentation.** M2 settles all of them by
  measurement (ADR-0008, `PLAN.md` rule 2). Nothing in M1 assumes one, which is why the common
  record (§4) stores pixels and board millimetres, not a framework's format.
- **A validation split.** M2 carves it from the training Capture sessions, by Capture session as
  well. Only the Held-out set is decided here, because it is the one thing that must exist before
  training starts.
- **Roboflow or any other third-party set.** ADR-0008 admits one only after its licence and the
  origin of its images are confirmed. None is needed to reach the bar's first reading.
- **Synthetic renders of a Board.** They are cheap to make but answer nothing about handheld phone
  photos, which is where the bar is measured. If M2 runs short of data, it is M2's option to try.
- **The classical cross-check** (ring masks and an ellipse fit, ADR-0008 *Alternatives*). It checks
  a calibration *on the phone*. Here the labels are the calibration, and the QA in §5 checks them
  more directly.
- **Any app code.** M1 changes nothing a player can see. The privacy policy is untouched: these
  Photos are the owner's own, taken with the system camera and copied to the owner's machine by
  hand. No player's Photo is involved (`PLAN.md`, *Not in this plan*).

**The tempting one is model-assisted labelling.** Train a rough model on DeepDarts, let it propose
the points, and only nudge them. It looks like a free upgrade in hours. It is not: a nudged proposal
is pulled towards the model's guess, so the labels inherit the model's bias, and the Held-out set
ends up measured against the bias it is meant to catch. labelme's built-in AI tools are off for the
same reason. They also download a model, which nothing in this phase needs. The pre-fill in §5 is
different: it projects through a homography fitted to points the owner clicked, so its only source
is the owner's own reading of that Photo.

**The second tempting one is splitting by Photo.** It gives a larger, more balanced Held-out set at
no cost. But three Photos of one Visit are the same Darts in the same light, and a model that has
seen one of them recognises the other two. DeepDarts split by Capture session for this reason (paper
§5.1). So does this phase (§6).

---

## Checkpoints

| | Checkpoint | Who | Merges | Depends on |
| --- | --- | --- | --- | --- |
| **A** | **The labelling loop in code**: `ml/` skeleton, Board geometry and scoring, ingest, the labelme driver, pre-fill, review, QA, overlays, `repeatability`, CI job | code | `chore(ml):` + `ci:` | — |
| **B** | **The gate**: the pilot Capture session through the whole loop in two rounds, and 10 of its Photos a third time without pre-fill | **owner**, about 4 h | `docs:` (verdict into R1) | A |
| **C** | **DeepDarts in, or out**: download, safe conversion, the four-point check; if DataPort asks for a subscription, the written ask and its three weeks (D5) | code; owner logs in, and writes the ask if needed | `chore(ml):`, or `docs:` if DeepDarts is left out | A |
| **D** | **Capture**: the other 17 Capture sessions | **owner**, about 8.5 h | none (data only) | B's verdict 1 or 2 |
| **E** | **Labelling and QA**, Capture session by Capture session as they are taken | **owner**, about 28 h | none (data only) | D, per Capture session |
| **F** | **The bar as code**: `evaluate`, `verify-held-out`, the builder refusing held-out Photos, and their tests | code | `chore(ml):` | A |
| **G** | **The freeze**: `held-out.toml` committed, R6 and R7 read | code | `chore(ml):` | F, and E for the six held-out Capture sessions |
| **H** | **Close**: counts read, ADR and docs amended, `PLAN.md` and `DOD.md` ticked | code | `docs:` | all |

One PR per checkpoint that merges anything. B, D and E produce data, not commits, apart from B's
verdict and the readings.

**The owner's hours, added up.** A Capture session takes about 30 minutes at the Board with setting
up. One labelling round (§5) takes about 1.5 minutes a Photo, so about 1.1 hours for a Capture
session's 45 Photos; B measures the real figure.

| | Owner's work | Hours |
| --- | --- | --- |
| B | s01 taken; rounds a and b; round c on 10 Photos at about 5 minutes each; QA | about 4 |
| D | the other 17 Capture sessions taken | about 8.5 |
| E | round a on 17 × 45 Photos (19 h); the second review of the 270 held-out Photos, about a minute each (4.5 h), and a further review of each one the second changes, allowed for at one in ten (0.5 h); QA, overlays and sheets, about 15 minutes a Capture session (4 h) | about 28 |
| | **In all**: about 9 at the Board and 31 at the labelling tool | **about 40** |

A further held-out Capture session costs about 2.5 hours: the Board, a round, a second review and
QA. A further training one costs about 2.

**Which work runs in parallel with the owner's hours.** Once A is merged, F needs nothing from the
owner, and C needs only the DeepDarts login, plus one email if DataPort asks for a subscription.
Both run while B, D and E take evenings at the Board and at the labelling tool. The only code that
waits on the owner's hours is G, the freeze, which needs the six held-out Capture sessions labelled
and checked.

**Why A before B.** The gate measures how well hand labels repeat (§1). That needs a homography
fitted to the labels and its error in board millimetres, which is A's code. A is about a day's work.
The gate without it would be a reading nobody can take.

**Why the gate before capture.** It answers "can these labels measure 0.5 mm?" on 45 Photos, before
the protocol is repeated 17 more times. A verdict 3 found after D changes the Calibration point
definition, and every Capture session would then be labelled again.

**Why labelling runs Capture session by Capture session, not after all capture.** Labelling the
first ones finds capture mistakes, such as a blurry Angle or a Score not written down, while there
are still Capture sessions left to take.

**Why F and G are two checkpoints** (`PLAN.md` rule 2). F is a day of code that can merge right
after A. G waits for the last held-out Capture session to be taken, labelled, reviewed twice and
checked. In one PR the harness would sit unmerged through most of D and E, and the table would hide
which half is the one blocking.

**Why D1 was settled before F.** The bar is the owner's (`PLAN.md`), and F turns it into code. Code
written before the answer would be edited after it, and that edit is how a bar drifts towards a
result. D1 was answered on 2026-11-13, before any of F is written.

**No checkpoint cuts a release.** `chore:`, `ci:` and `docs:` bump nothing, and no app code changes.

---

## 1. The gate: do hand labels repeat to well under the bar?

### The question, in the form that can be measured

On the pilot's 45 Photos, labelled in two independent rounds a few days apart, how far apart in
board millimetres are the two label homographies, at the 80 Calibration points? A label homography
is the least-squares fit to every Calibration point on a reviewed Photo (§5). It is the truth B1 is
measured against (§7). Its repeatability is therefore the noise floor under every millimetre figure
this project will report.

Round b starts again from pass 1 on an empty label (`--round b`, §5), not from round a's file.
Re-opening round a's points and accepting them would measure agreement with a file, not
repeatability.

**Pre-fill is shared by both rounds, so two rounds alone can flatter the result.** A crossing the
owner leaves undragged sits where the four Hand points project it. If that projection is off in a
way the eye accepts (lens distortion a plane cannot absorb, or a lenient "on centre" at 200%), the
same offset appears in both rounds and the two agree on it. So 10 pilot Photos get a third round,
**c, with no pre-fill**: every visible crossing is clicked by hand.

### The apparatus

`darts-ml repeatability <capture-session>` (A, `repeatability.py`). For each Photo it maps every
Calibration point through two rounds' label homographies and reports the median and 95th percentile
of the distance, in mm:

- **a–b**, over all crossings, and separately over the crossings dragged in both rounds and those
  left undragged in either. A crossing counts as undragged when it lies within 1 pixel of the
  projection that round's own four Hand points give, which `repeatability` recomputes from the
  review manifest;
- **a–c**, on the 10 Photos of round c. Round c shares no projection with round a, so a bias in the
  pre-fill shows here and nowhere else.

It also reports the minutes per Photo of passes 1 and 3, from the times `label` and `review` record
in the review manifest (§5). They go into R1, because they are the number D3's estimate rests on.

### The verdicts, decided now rather than argued about later

Each verdict is read on the worse of a–b over all crossings and a–c.

1. **Median ≤ 0.25 mm and 95th percentile ≤ 0.5 mm**, half of B1. → The protocol stands as written.
   Capture (D) starts.
2. **Median ≤ 0.5 mm, but over either limit in 1.** → Tighten the protocol: label at full resolution
   with the zoom at 300% or more, and add a reference picture of "the centre of the crossing" to
   `ml/README.md`. Then re-label 10 pilot Photos in two new rounds. If the result is still in this
   band, B1 stands, and the measured repeatability is added to B1's two figures in §7. That
   amendment is written before D starts, so the bar is still set before training.
3. **Median over 0.5 mm.** → Hand labels cannot measure B1. Capture stops. Before any more Capture
   sessions, the Calibration point set is narrowed to the crossings that label best (the outer
   double wire's 20 are the likely ones), with a dated amendment to ADR-0008, and B is taken again.

### The verdict, taken *(date)*

*(Filled in at B: which verdict, R1's figures, minutes per Photo, and D3's estimate re-read against
them.)*

## 2. A — The labelling loop in code

### Toolchain: uv, with a pinned lockfile

`ml/` is a [uv](https://docs.astral.sh/uv/) project: `pyproject.toml`, `uv.lock` and a
`.python-version` of `3.12`. The repo's own scripts stay as they are, plain `python3` with no
dependencies, because they need nothing outside the standard library. `ml/` does, and uv fits it
for four reasons:

- The `.gitignore` allowlist from `d1e24ce` was written for its three files.
- The owner's own interactive scripts already run with `uv run --script`.
- `uv.lock` pins every transitive version with hashes, so a result from M2 can be reproduced.
- `uv sync --locked` in CI fails when the lock and `pyproject.toml` disagree. (`--frozen` would
  install from a stale lock without checking it.)

3.12 is a conservative pin with wheels for every dependency A needs. M2 may move it when it picks
a framework.

Every dependency is permissive (§0): NumPy (BSD-3, its wheel's bundled runtime libraries allowed and
listed by §0's rule), Pillow (MIT-CMU) and tomli-w (MIT), which
writes the review manifest. OpenCV was planned here and left out at A: nothing in the loop needs it.
C adds pandas (BSD-3) for one job: `labels.pkl` is a pickled
pandas DataFrame and cannot be rebuilt without it. It is still loaded only through the restricted
unpickler (§4), never with `pd.read_pickle`. `ml/README.md` keeps a table of each dependency and its
licence, re-read when one is added, because M2 adds to this lockfile. The labelling tool is GPL-3.0
and is therefore kept *out* of the lockfile (§5).

### Layout

```
ml/
  README.md               how to run each step; the dependency licence table; the crossing picture
  pyproject.toml          the project, its pinned dependencies, the `darts-ml` command
  uv.lock
  .python-version         3.12
  src/darts_ml/
    paths.py              DARTS_DATA, and the refusal of any data path inside the repo; `paths`
    board.py              ADR-0008's geometry: the 80 Calibration points in board mm, and scoring
    homography.py         least-squares fit, projection, and the error at the 80 crossings in mm
    ingest.py             phone files → named, losslessly rotated, metadata-stripped Photos
    capture_sessions.py   the sheet: phone, light, Visits and their recorded Scores
    labelme.py            the label list; `label`, the pinned labelme launcher, one Photo at a time
    prefill.py            Hand points → all Calibration points; Entry points across a Visit's Photos
    manifest.py           the review manifest's file (§5), shared by `label`, `prefill` and `review`
    review.py             `review`, pass 3's confirmation, and what counts as reviewed
    check.py              label QA (§5)
    overlay.py            QA renders, written into DARTS_DATA
    repeatability.py      the gate's figures (§1)
    summary.py            counts from the sheets and labels (R4), and the Visits B2 counts (§7)
    deepdarts.py          restricted unpickler and converter (§4)
    records.py            the common record both sources become; `build`
    heldout.py            freeze and verify (§6)
    evaluate.py           the bar's numbers (§7), F
    cli.py                `darts-ml <step>`
  splits/held-out.toml    the frozen manifest, G
  tests/                  unittest, as in scripts/; scoring-cases.toml is shared with phase 1
```

One command, `darts-ml <step>`, is declared in `pyproject.toml`'s `[project.scripts]` and run as
`uv run --directory ml darts-ml <step>`. Tests use `unittest` like `scripts/`, so the repo has one
test idiom.

### The data stays out, three ways

1. **It lives outside the repo.** `DARTS_DATA` names the directory, defaulting to
   `~/darts-scorer-data` (D4). Its layout:
   ```
   $DARTS_DATA/
     inbox/<capture-session>/            files as copied off the phone; emptied once ingest is verified
     photos/<capture-session>/           s03-v07-p2.jpg: Capture session, Visit, Angle
     labels/<capture-session>/           labelme JSON, one per Photo, no image data; review.toml
     rounds/<capture-session>/<b|c>/     the gate's repeat rounds (§1); read only by `repeatability`
     capture-sessions/<capture-session>.toml   the sheet
     deepdarts/                          the download, unpacked, plus the converted records
     overlays/<capture-session>/         QA renders
     build/                              generated records for M2; regenerated, never edited
   ```
2. **`paths.py` refuses a `DARTS_DATA` that resolves inside the repo**, with symlinks followed, and
   says why. The repo is every worktree of the clone, found from git's common directory, and the
   same check runs on each folder under `DARTS_DATA` the loop reads or writes. Without this, the
   `.gitignore` would be the only thing in the way, and `.toml` sheets would get past it.
3. **The `.gitignore` fence** (§0) is the second line.

### Ingest

`darts-ml ingest <capture-session>` reads `inbox/<capture-session>/` in capture order (EXIF
`DateTimeOriginal`). Against the sheet's Visit count it checks that the Photos are exactly three per
Visit, and names them `<capture-session>-v<NN>-p<1|2|3>.jpg`. Like `media/MediaFiles.kt` in the
app, it bakes in the EXIF rotation and strips all metadata, GPS included. Before stripping, it
copies the phone model and the capture time into the sheet. A count that does not add up stops the
ingest and lists the files, and so does a right count whose capture times do not fall three to a
Visit: every gap between two Visits must be longer than every gap inside one. Ingest never guesses
which Photo belongs to which Visit.

**Unlike `MediaFiles.kt`, it does not re-encode.** Photos keep their full resolution and the phone's
own JPEG: what the model is fed is M2's decision, and a second encode adds a second generation of
artefacts at the scale of a wire. Ingest rotates and strips with `jpegtran -copy none`
(libjpeg-turbo, BSD-style and IJG licences, a system tool that `darts-ml paths` checks for and CI
installs). Every rotation passes `-trim`, a 180° turn as much as a quarter-turn: on a size that is
not a whole number of 16-pixel blocks, it drops the partial edge blocks (under 16 pixels at the
frame's edge) rather than re-encode them. An upright Photo is only stripped. A file that is not a
JPEG is refused (§3 sets the camera to JPEG).

### Board geometry, as code

`board.py` holds ADR-0008's table and nothing else invented. It gives each **Calibration point** an
exact definition, which the ADR leaves as "boundary points between segments on the double and treble
wires":

- **A Calibration point is the centre of a crossing**, where the centre line of a radial wire
  between two segments meets the centre line of one of the four ring wires. That is 20 radial wires
  × 4 ring wires, **80 points**. The centre of a crossing is what the eye finds on a Photo, and a
  wire's edge is not.
- **Board positions** come from ADR-0008's bands with *w* = 1.5 mm. The radial wire is at the
  segment boundary angle: 9° plus a multiple of 18°, clockwise from the top. The ring wire's centre
  radius is:

  | Ring wire | Name | Centre radius (mm) |
  | --- | --- | --- |
  | Outer double | `do` | 169.25 |
  | Inner double | `di` | 159.75 |
  | Outer treble | `to` | 106.65 |
  | Inner treble | `ti` | 97.15 |

- **Names** are `<ring>-<a>-<b>`, with `a` and `b` the segments on either side in clockwise order.
  For example, `do-20-1` and `ti-5-20`. The label list labelme validates against is generated from
  this table, so the code has only one source.
- **Scoring** maps a board-mm point to a Score by the bands and WDF §3.03's side-of-the-wire rule.
  The same function scores labels in QA (§5) and predictions in `evaluate` (§7).

### CI

A job `ml` in `ci.yml`: `astral-sh/setup-uv` with its cache, `apt-get install libjpeg-turbo-progs`
for `jpegtran`, `uv sync --locked --directory ml`, then `uv run --directory ml python -m unittest
discover -s tests`. Only uv's downloads are cached; the tests run every time. It needs no data: the
tests build their Photos and labels synthetically from `board.py`.

## 3. The capture protocol

### What is fixed for every Capture session

- **The Board** is the owner's regulation steel-tip Board, hung at regulation height, and the
  owner's own Darts. A second set with different flights, if there is one, goes in some Capture
  sessions.
- **The camera** is each phone's system camera app, because that is what the app fires
  (`TakePicture`, `PLAN.md` *Asks*). Use the main 1× lens with no zoom, and leave the default mode
  and HDR as they are. Portrait mode, filters and the ultra-wide lens are off. Photos are saved as
  JPEG, not HEIF. **Location tagging is off** in the camera's settings; ingest strips GPS anyway.
- **The Photos reach no cloud.** Before s01, turn off each phone's cloud backup of its camera
  folder: Google Photos' backup and the maker's own (Samsung Cloud, Xiaomi Cloud and the like),
  several of which are on by default. Keep the phone in airplane mode from the first Photo of a
  Capture session until its Photos are off it, so a backup that turns itself back on has nothing to
  send. Copy them by USB (`adb pull`, or the phone's file transfer) into `inbox/`. Once ingest is
  verified, delete them from the phone and from its recently deleted folder, and only then leave
  airplane mode.
- **A borrowed phone** (D2) is used only with its owner's agreement, and in airplane mode for the
  whole Capture session, so its backup settings can stay as its owner has them. If it cannot stay
  offline that long (a managed work phone, say), use another phone. Its Photos are deleted, recently
  deleted folder included, before it goes back online or back to its owner.
- **Keep, don't curate.** Keep a mildly blurred or badly framed Photo, because players take them.
  Delete on the phone, and retake at once, only a Photo where you cannot read the Board yourself.
  Then the Visit still has exactly three.

### Each Visit, in order

1. Throw three Darts as in play: at a target, from the oche.
2. Walk up and take three Photos, always in this order:
   - **p1, front:** roughly in front of the Board, 1–2 m away, the phone at chest-to-eye height.
     This is the Photo a player takes first, and the bar is read on it (§7).
   - **p2, left:** 30–60° to the left, 1–2 m away.
   - **p3, right:** 30–60° to the right, 1–2 m away.
3. **Before touching a Dart**, read each one up close and write its Score into the sheet, for
   example `T20 T20 S1`. A Dart that fell out is `out`. Mark `wire` beside any Dart whose Entry
   point is within about 2 mm of a wire. Mark `hidden` beside any Dart you cannot see in p1, and
   `hidden-p2` or `hidden-p3` beside one you cannot see in that Photo.
4. Pull the Darts.

That is about 75 seconds per Visit, and 15 Visits make a Capture session of about 25 minutes, about
30 with setting up.

### Across each Capture session's 15 Visits, deliberately

The hard cases are ADR-0008's own: a Dart hidden by another, a Dart on a wire, Calibration points
covered, oblique Angles, and fewer Darts in the Board than thrown.

| Case | How many per Capture session | How |
| --- | --- | --- |
| **Grouped Darts**: one hides another, and Darts cover Calibration points | ≥ 4 Visits | all three at T20 or T19 |
| **On a wire** | ≥ 2 Visits | aim at a treble or double wire. In training Capture sessions only, a Dart may be **pushed in by hand** at a chosen wire. It is marked `placed` in the sheet, at most 15% of training Visits, never in the Held-out set |
| **Bounce-outs and fall-outs** | whenever they happen | `out` in the sheet; never staged |
| **Far and near** | ≥ 3 Visits each | p1 taken from the oche (2.37 m) instead; p1 from about 0.8 m |
| **Steep Angles** | ≥ 2 Visits | p2 and p3 at about 60°; one Visit from crouching and one with the arm raised |
| **Orientation and framing** | mixed | portrait and landscape both. In two or three Photos per Capture session, part of the Board is out of frame |
| **Ordinary play** | the rest | targets spread over the Board, so every segment is seen |

### The Capture sessions

Each Capture session is one phone and one kind of light, on one day. Light is either **day** (window
light, no lamps), **evening** (the room's ordinary lamps), **flash** (evening, with the flash forced
on for p1), or **harsh** (a single lamp to one side, so the Darts cast long shadows). DeepDarts
names occlusion and Darts on a section edge as its failures, not shadows. The grouped and on-a-wire
Visits cover those two; harsh light is here as a room players will have. The Held-out set is
assigned **now**, before any Capture session is taken, so that it covers both phones and all four
lights:

| Capture session | Phone | Light | Set |
| --- | --- | --- | --- |
| s01 | phone 1 | day | training: the pilot (B) |
| s02 | phone 1 | evening | training |
| s03 | phone 2 | day | training |
| **s04** | phone 1 | flash | **held-out** |
| s05 | phone 2 | evening | training |
| s06 | phone 1 | harsh | training |
| **s07** | phone 2 | day | **held-out** |
| s08 | phone 2 | flash | training |
| s09 | phone 1 | day | training |
| **s10** | phone 1 | evening | **held-out** |
| s11 | phone 2 | harsh | training |
| **s12** | phone 2 | flash | **held-out** |
| s13 | phone 1 | flash | training |
| s14 | phone 2 | evening | training |
| **s15** | phone 1 | harsh | **held-out** |
| s16 | phone 1 | day | training |
| **s17** | phone 2 | harsh | **held-out** |
| s18 | phone 2 | day | training |

That is 12 training Capture sessions, six per phone with all four lights on each, and 6 held-out,
three per phone, taken in this order. In held-out Capture sessions every Dart is thrown and none is
placed. They still carry their share of grouped and on-a-wire Visits, and those are what the bar is
about. With one phone (D2), phone 2's rows become phone 1, and *Known gaps* says so.

**If hours run short**, training rows are dropped from the bottom of the table up, skipping any
whose loss would leave a phone without training in one of the four lights. Held-out rows are never
dropped or moved, so the Held-out set stays the one assigned before capture. The floor is 8
training Capture sessions (14 in all); below it, too little is left to train on, and *Known gaps*
says the bar was read against a thin training set.

The sheet, `capture-sessions/<capture-session>.toml`, holds the phone, the light, the set, the date,
and each Visit in order with its Scores and marks. It is typed up from the notes taken at the Board
on the same day.

## 4. C — The DeepDarts dataset

### What it is, from the primary sources (read 2026-11-13)

- **Paper:** McNally et al., *DeepDarts: Modeling Keypoints as Objects for Automatic Scorekeeping in
  Darts using a Single Camera*, CVSports 2021, [arXiv 2105.09880](https://arxiv.org/abs/2105.09880).
  It has 16,050 Photos with 32,027 Darts. **D1** has 15,000 face-on Photos from an iPhone XR on a
  fixed mount, over 36 Capture sessions, split 12k / 1k / 2k by Capture session. **D2** has 1,050
  Photos from a tripod DSLR at varied angles, over 15 Capture sessions, split 830 / 70 / 150 the
  same way. Every Photo has four Calibration points and up to three Darts. One annotator labelled
  them, and the labels matched the Scores recorded at the Board on 97.6% of the 1,200 Darts checked
  (§5.3).
- **Dataset:**
  [IEEE DataPort, DOI 10.21227/05e7-xs69](https://ieee-dataport.org/open-access/deepdarts-dataset),
  published 2021-06-12 by William McNally. Its files are `cropped_images.zip` (3.35 GB, every Photo
  cropped to 800 × 800 around the Board), `labels_pkl.zip` (340 KB) and `models.zip` (149 MB).
  **Licence: Creative Commons Attribution** (the page links
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en)). Download needs a login.
  The page says both that a free account is enough and that a DataPort subscription is required
  (D5). In a comment (2021-06-18), the author links a Google Drive copy of the cropped images only.
- **Code:** [`wmcnally/deep-darts`](https://github.com/wmcnally/deep-darts) has **no licence file**
  (GitHub API `license: null`, last pushed 2021-06-14), so all rights are reserved. ADR-0008 already
  says so. The method is reimplemented, and no line of it is copied. The code was read on 2026-11-13
  only to learn the label format below. Reading it to learn a file format is not reuse.

### What the licence allows, plainly

CC BY 4.0 grants the right to reproduce the data, adapt it, and share both, **for any purpose,
including commercial** (§2(a)(1)). The condition is attribution (§3(a)):

- name the creator;
- keep the copyright and licence notices and the disclaimer;
- link to the material;
- say that it was modified;
- link to the licence.

It adds no non-commercial, share-alike or no-derivatives terms. So nothing in it stops training on
the data, or shipping weights trained on it inside a free app with a Tip. Whether trained weights
are "Adapted Material" under the licence is legally unsettled. ADR-0008 already answers the question
in the safe direction, by crediting the dataset on the licences screen from the first build that
ships such a model (phase 3 in `PLAN.md`). This phase adds nothing to that.

Two points ADR-0008 does not cover, settled here:

- **Labels come from DataPort's `labels_pkl.zip`, which is CC BY 4.0. They do not come from the
  GitHub repo's `dataset/labels.pkl`** (2.8 MB). That may be the same data, but it is distributed
  under the repo's no-licence status. Recorded in ADR-0008's amendment at A.
- **`models.zip` is not used.** Those weights are YOLOv4-tiny trained with the unlicensed code.
  Their CC BY licence on DataPort would allow it, but M2 starts from its own permissively licensed
  initialisation, and a dependency nobody needs is not added.

### If DataPort asks for a subscription (D5)

The Drive copy holds the images and no labels, and the repo's `labels.pkl` is ruled out above, so
the labels must come from the author. The owner writes to him at the address on the paper and asks
for two things in writing: the labels (`labels_pkl.zip`) under CC BY 4.0, and confirmation that the
Drive copy of `cropped_images` is under the same licence. A reply that grants both brings DeepDarts
in from those two sources, and the reply is kept in `deepdarts/` and named in R2.

**No answer means three weeks from the day the ask is sent** with no reply that grants both. A
refusal, or a grant of less, counts the same. Then M1 goes on with the owner's Photos alone, C
merges as a `docs:` note saying so, and ADR-0008 gets a dated amendment that the dataset is not
used. Nothing else in the phase waits on the three weeks: A, B, D, E and F carry on.

**What the plan loses without DeepDarts:**

- **Most of the training data.** M2 trains on the owner's 540 training Photos (12 × 45) instead of
  about 16,500. A detector trained on so few is the likeliest way to miss the bar. M2 may then need
  more training Capture sessions, about 2 owner hours each, or the synthetic renders M1 leaves out.
- **The outside comparison.** The reading beside the bar on DeepDarts' D2 test set, against the
  paper's 84.0%, cannot be taken. B2 is then compared with nothing but itself.
- **R2 and R3**, which are not taken, and pandas, which never enters the lockfile. The DeepDarts
  credit on the licences screen (phase 3) falls away with the data.

The bar, the Held-out set and the owner's labelling do not depend on DeepDarts, so none of them
moves.

### The label format, and how it maps

`labels.pkl` is a pickled pandas DataFrame with one row per Photo:

- `img_folder` names the Capture session, for example `d1_02_06_2020`;
- `img_name`;
- `bbox` is the crop in the original;
- `xy` lists up to 7 points normalised to the 800 × 800 crop: four Calibration points, then the
  Darts.

The four are on the outer edge of the double wire, at the 5|20, 17|3, 8|11 and 13|6 boundaries
(paper §4.2). Their order follows the target positions in `annotate.py`'s `transform()`. Those map
to the names in §2 as follows:

| DeepDarts | Name here | Board radius used |
| --- | --- | --- |
| `xy[0]` | `do-5-20` | 170.0 mm |
| `xy[1]` | `do-17-3` | 170.0 mm |
| `xy[2]` | `do-8-11` | 170.0 mm |
| `xy[3]` | `do-13-6` | 170.0 mm |
| `xy[4:]` | Entry points | — |

That order is read from the code, so C checks it on 10 Photos by overlay (R3) before the converter
is trusted. DeepDarts measures to the outer edge (`r_double=0.17`), 0.75 mm outside this repo's
crossing centre. The converter keeps their radius, and the record notes the source, so the 0.75 mm
never becomes silent label noise. From the four, a homography projects the other 76 points. Each one
is marked `source = "deepdarts-projected"`. A four-point fit has no redundancy: one bad click warps
all 76 projected points. So M2 decides whether to train on them, weight them, or use only the four.
DeepDarts' own test folders (`d1_test` and `d2_test` in `dataloader.py`, by Capture session) are
kept out of training. This keeps one reading comparable with the paper's 84.0%.

### Opening a downloaded pickle safely

Unpickling runs code named in the file. `deepdarts.py` therefore loads `labels.pkl` with a
`pickle.Unpickler` whose `find_class` admits only the pandas and NumPy classes a DataFrame needs.
It loads no other class and never calls `pd.read_pickle`. If the file asks for anything else, the
load stops and names the class. The fix is to look at the file, not to widen the list. The converter
writes plain records once (`deepdarts/records.jsonl`), and nothing reads the pickle again. The
downloads are unpacked into a directory of their own under `DARTS_DATA`, and nothing is run from
inside it.

### The common record

Both sources become one record per Photo, in `build/` (generated). A record holds:

- its source and Capture session;
- the Photo's path and pixel size;
- each Calibration point: name, pixel position, and its source: `hand` (a Hand point), `checked`
  (pre-filled, on a Photo whose review matches its label, §5), `deepdarts` or
  `deepdarts-projected`;
- each Entry point: pixel position, and whether it was `inferred`;
- the Visit's recorded Scores, where there are any.

Pixels and names, not a framework's format, so M2 can write whichever format it picks from this.

## 5. E — Labelling, and its QA

### The tool: labelme, pinned, run outside the lockfile

[labelme](https://github.com/wkentaro/labelme) (GPL-3.0, v7.10.0 current on 2026-11-13) is a local
Qt desktop app. Photos are opened from disk, and labels are written as one JSON file per Photo
beside them, or into `--output`. There is no server, account or upload. In v7 the JSON holds no
image data by default (`with_image_data: false` in its default config). The only network code in its
source (read 2026-11-13) belongs to the optional AI tools, which download models when used and stay
unused here (*What is in*). It was chosen over the others for these reasons:

- **CVAT** handles point sets best, but needs a Docker stack to self-host.
- **Label Studio** is a web server with an analytics setting to remember to turn off.
- **VIA** is a single offline HTML file, but has been unmaintained since about 2021, and its point
  labels need a hand-built attribute scheme.

labelme takes a validated label list (`--labels`, `--validate-label exact`) and per-label flags
(`--label-flags`), which is exactly the shape needed here.

`darts-ml label <capture-session>` opens the Capture session's Photos one at a time, each in its own
`uvx labelme==<pinned>` window. It passes the label list generated from `board.py`, `--output
labels/<capture-session>/`, `--validate-label exact` and the flag `inferred` on `entry`. Running it
through `uvx` keeps GPL code out of `ml/`'s lockfile, out of anything that trains, and out of the
app. What labelme writes is the owner's data, not labelme's. The pin is the newest release at least
two weeks old on the day A merges, and it is recorded in `ml/README.md`. At A that is **7.9.1,
resolved as of 2026-10-26** (`uvx --exclude-newer`): labelme's own dependencies are unbounded, and on
2026-11-13 a fresh `uvx labelme==7.9.1` pulled osam 0.11.3, released that day, which crashes 7.9.1 at
start-up. `label` also passes `with_image_data: false` through `--config`, so a `~/.labelmerc`
cannot turn it on. 7.9.1 has no setting that switches the AI tools off; their download runs only on
a click, and the windows run with uv offline and every proxy pointed at an unreachable address, so a
click by mistake fails. One window per Photo costs
a few seconds of start-up each, and buys a measured time and a confirmation per Photo (*The
passes*).

### What is labelled

- **Calibration points**: the 80 named crossings (§2), each placed on the centre of its crossing.
  **A crossing hidden by a Dart is deleted, not guessed**: the model is meant to find the visible
  ones (ADR-0008), and a guess would teach it to invent them.
- **Entry points**: label `entry`, one per Dart, where its shaft enters the Board.
  - **Visible:** the point is clicked.
  - **Hidden, with the Dart's line visible:** the point is placed where the shaft meets the Board
    and flagged `inferred`.
  - **Not visible at all:** no point. The sheet's `hidden`, `hidden-p2` or `hidden-p3` explains the
    missing one.

### The passes

1. **Hand points and Entry points.** `darts-ml label`. Click the four **Hand points**, the
   outer-double crossings `do-5-20`, `do-17-3`, `do-8-11` and `do-13-6`, so every label names
   DeepDarts' four too. If one is covered, click the nearest visible outer-double crossing under its
   own name. Then click the Entry points.
2. **Pre-fill.** `darts-ml prefill <capture-session>` fits a homography to the Hand points, writes
   all 80 crossings into each label, records the Hand points in the review manifest, and projects
   each Entry point into the Visit's other two Photos as a suggestion. The Board is a plane, and an
   Entry point lies on it.
3. **Review.** `darts-ml review <capture-session>` opens each Photo again. At 200% zoom or more,
   drag every crossing that is not on its centre, and delete every covered one. Accept, move or
   delete each suggested Entry point. When the window closes, `review` asks whether every crossing
   was looked at, and a yes records the date and the label's SHA-256 in the review manifest. On
   **held-out Photos every crossing is checked at 300%**, and `review` is run twice, on different
   days (§6).

**What makes a crossing `checked` is the review manifest, not labelme.** labelme cannot mark one: it
writes unknown keys back unchanged, and with its default `auto_save` a Photo whose crossings were
all right is never saved at all. So a Photo is reviewed when the manifest holds a review whose
SHA-256 matches its label as it is now. Any later edit makes it unreviewed again, and `check` says
so. A held-out Photo is reviewed twice when two reviews on different days both match its label as it
is now. So if its second review moves or deletes anything, the first no longer matches, and the
Photo needs one more review on a later day, repeated until two match. The manifest,
`labels/<capture-session>/review.toml`, also holds each Photo's Hand points as pre-fill read them
and the seconds its windows were open in passes 1 and 3.

**A labelling round** is passes 1–3 over a Capture session, and round a is the label of record. Only
the gate repeats one. `--round b` on `label`, `prefill`, `review` and `check` starts from empty
labels in `rounds/<capture-session>/b/`. `--round c` does the same with no pre-fill: pass 2 is
skipped, and pass 1 clicks every visible crossing. Nothing but `repeatability` reads a repeat round,
and none becomes a record.

B measures the minutes per Photo, from the review manifest. The estimate in D3 assumes about 1.5
minutes for passes 1 and 3 together; pass 2 is the machine's.

### The QA step, before a Capture session counts as labelled

`darts-ml check <capture-session>` must come back clean. Every finding is fixed, in the label or in
the sheet. One that cannot be fixed, such as a Dart that fell out between the Photo and the reading,
is recorded in the sheet as an **open mismatch**, with the Photo it is on and its reason:

1. **Lint.** Every label name is from the list, with no duplicates. There are at least 4 Calibration
   points. The image data is empty, and the image size matches the Photo. Entry points number no
   more than the Darts recorded in the Board. Every Photo is reviewed, as above, and a held-out one
   by two reviews on different days that both match its label as it is now.
2. **Fit.** The label homography is fitted to all Calibration points by least squares. Any point
   whose residual exceeds 1.0 mm is listed: either a misclick, or lens distortion a plane cannot
   absorb (*Known gaps*).
3. **Score.** Every Entry point is scored through its label homography. The Scores in each Photo
   must match the Scores recorded at the Board, as multisets, with hidden Darts allowed to be
   missing. A p2 or p3 label with fewer Entry points than the Darts in the Board is a finding unless
   the sheet marks the missing ones `hidden-p2` or `hidden-p3` for that Photo, or an open mismatch
   names it; a missing Dart in p1 is step 4's. Every mismatch is opened and looked at. DeepDarts' 2.4% says some will be the label and
   some the note.
4. **Hidden in p1, from the labels.** A Visit is **hidden in p1** when p1's label has fewer Entry
   points than the Visit has Darts in the Board: its recorded Scores, less any `out`. An `inferred`
   Entry point counts as visible, because its Dart is. This rule, not the sheet, decides which
   Visits B2 counts (§7), so the split is never a judgement call. The sheet's `hidden` marks, which
   are p1's alone, must agree with it, and a disagreement is a finding. `hidden-p2` and `hidden-p3`
   play no part in B2.
5. **Across Angles.** In each Visit, every Dart's Entry points from p1, p2 and p3 must land within
   2 mm of each other in board millimetres. Otherwise either a label or a calibration is wrong.
6. **Overlay.** `darts-ml overlay <capture-session>` draws the rings and all 80 crossings from the
   label homography onto each Photo, plus each Entry point with its Score, into `overlays/`. Flip
   through them, about two seconds a Photo. That catches the gross error the numbers can miss, such
   as a homography that fits its points and is mirrored.

## 6. F and G — The Held-out set

- **Share:** 6 of 18 Capture sessions, a third: s04, s07, s10, s12, s15 and s17, assigned in §3
  before capture. That is 90 Visits and 270 Photos. The split is by Capture session, never by Photo
  or Visit (*the second tempting one*).
- **Why six, not four.** B2 counts only the held-out Visits not hidden in p1 (§7), and needs at
  least 60 of them. The grouped Visits, at least four in each Capture session, are where Darts
  hide, and the framing Visits can leave a Dart out of p1's frame. Four Capture sessions would give
  60 Visits before any is left out. Six leave 60 counted even if a third of the 90 are hidden in p1.
- **If E counts fewer than 60** (`darts-ml summary --held-out`), another held-out Capture session is
  taken, with the phone and light the held-out ones have least of, and labelled before G freezes.
  Its row is added to §3's table in a `docs:` commit before it is taken. This repeats, one Capture
  session at a time, until `summary --held-out` counts at least 60.
- **Chosen** so that it covers both phones and all four lights, with only thrown Darts. Its Capture
  sessions are taken interleaved with training ones, not last, so it is not all from the owner's
  best-practised evenings.
- **Reviewed twice.** Every held-out Photo goes through `review` at 300% a second time, on a
  different day. A Photo that review changes gets a further one on a later day (§5). `check` must be
  clean. This is the truth the bar is read against, so it gets the hours.
- **Frozen** at G by `ml/splits/held-out.toml`, committed. `darts-ml freeze-held-out` writes it, and
  only once `check` is clean on every held-out Capture session. For every held-out Photo it records the
  file name, the SHA-256 of the Photo and of its label, and the SHA-256 of each sheet and review
  manifest. The files stay in `DARTS_DATA`. The names say only Capture session, Visit and Angle, and
  a hash reveals nothing of a Photo.
- **Enforced in code** (F). `darts-ml verify-held-out` fails on any missing or changed file, and on
  a held-out sheet the manifest does not freeze. `evaluate` runs the same check before it reads.
  `records.py`'s builder refuses to put a held-out Photo into any training or validation record, by
  Capture session and by hash, and its test proves it (*Tests*). It also refuses every Capture
  session an earlier commit of the manifest froze.
- **Changed only on purpose.** A label error found later in a held-out Photo is fixed in a commit
  that updates the manifest and gives the reason in its body. It is never fixed silently. A frozen
  Capture session is only ever added to, never removed: `freeze-held-out` refuses a freeze that
  would leave one out, whether its sheet now says training or the manifest was deleted. M2 tunes
  on a validation split from training Capture sessions and reads the Held-out set only to take the
  bar's reading. Each reading is logged in `phase-M2.md`, so a bar met on the fifth look says so.

## 7. The bar for opening phase 1 — decided 2026-11-13 (D1)

Set now, before any training. Every figure below is computed by `darts-ml evaluate` (F) on the
Held-out set. Photos and Visits are counted from the frozen manifest, never from what a model
happened to process.

### B1 — the Board

Each held-out Photo has a label homography *H*: image to board mm, fitted to the Calibration points
of its reviewed label (§5). A predicted homography *Ĥ* is the model's. For each of the 80 crossings
at board position *X*, the error is |*Ĥ*(*H*⁻¹(*X*)) − *X*| in mm. Checking at every crossing,
covered or not, measures the Board everywhere it matters. It does not depend on what the model
happened to see.

| Figure | Bar |
| --- | --- |
| Board found (a homography fitted from at least 4 points) | **≥ 98% of held-out Photos** |
| Treble wires (`ti`, `to`): median / 95th percentile | **≤ 0.5 mm / ≤ 1.0 mm** |
| Double wires (`di`, `do`): median / 95th percentile | **≤ 0.5 mm / ≤ 1.0 mm** |

A Photo where the Board is not found counts against the first row and is left out of the other two.
Otherwise one lost Photo would hide as a single outlier.

**Why these numbers.** ADR-0008's 2 mm wire margin is the whole error budget for a Dart near a wire.
Giving the Board at most half of it, at the 95th percentile, leaves the other half to the Entry
point, which is the harder detection. A median of 0.5 mm is about one pixel at the 800-pixel crops
DeepDarts trained on. That is ordinary for a keypoint detector, and RANSAC over many points averages
better than one point. The treble wires and the double wires get separate rows, because a homography
fitted mostly on the outer crossings can be right at the double and wrong at the treble, where most
Darts land. If B's verdict was 2, both mm rows grow by the measured repeatability.

### B2 — the Visits

| Figure | Bar |
| --- | --- |
| Held-out Visits not hidden in p1, scored **exactly right from p1 alone** | **≥ 80%, over at least 60 such Visits** |

**Exactly right** means that the predicted Darts, as a multiset of Scores, equal the Scores written
down at the Board. That covers the count and each Dart's ring and number. A Dart recorded `out` is
not in the Board and must not be found. Matching the total alone is not enough, because two wrong
Darts can add up to the right total.

**Which Visits count.** Only those not *hidden in p1*, by the rule in §5's QA step 4, which reads
the labels, not anyone's judgement. A Dart that p1 does not show cannot be found from p1 by any
model, so counting those Visits would put a ceiling on B2 that has nothing to do with the model.
They are not dropped: they get their own figure below, because they are exactly where phase 2 asks
for another Angle.

**Why this number.** DeepDarts reports 84.0% on its angled set (ADR-0008 says why that is
optimistic). That figure is per Photo and counts the total only, and it includes Photos with one or
two Darts. A three-Dart Visit from a handheld front Photo, scored Dart by Dart, is harder. So 80%
here is at least the published state of the art, measured honestly. Below it, phase 1 would put a
mechanism on the phone that players correct more than one Visit in five, before phase 2's other
Angles can help. **60 Visits is a small sample:** 48 of 60 has a 95% interval of about 68–88%. The
bar is therefore a floor on the measured share, not a claim about the true rate. Raising the
confidence needs more held-out Capture sessions, at about 2.5 owner hours each.

### Reported beside the bar, not part of it

- **The Visits hidden in p1**, phase 2's input: how many there are; the share in which p1's
  prediction finds fewer Darts than the Visit had in the Board, which is when phase 2 would ask for
  another Angle; and the share scored exactly right from all three Photos merged.
- B2 on p2 and on p3, and on all three Photos merged. Merging is phase 2's mechanism, read early.
- The share of Darts scored right.
- The share of wrong Visits where one of ADR-0008's triggers would have asked for another Angle.
  This is phase 2's starting reading: a wrong Visit that nothing flags is the costly kind.
- DeepDarts' D2 test set, scored by this repo's model, beside the paper's 84.0%, if C brought
  DeepDarts in (D5).

---

## Tests

`PLAN.md` rule 3's second clause. M1 has no device behaviour. Its safety values are the ones the bar
and the privacy promise rest on, and each test fails in the direction that would flatter the bar or
leak a Photo:

- **`BoardTest`** checks the 80 crossings against ADR-0008's table: count, names, the clockwise
  order from 20, and the radii in §2. It also checks scoring at both edges of every band and on
  both sides of a wire, by WDF §3.03. The cases live in `tests/scoring-cases.toml`, as board-mm
  points and their expected Scores, for phase 1's Kotlin test to read too. It fails towards a Score
  that is wrong at a wire, which is the case the app exists for.
- **`EvaluateTest`** gives `evaluate` four sets of predictions:
  - the labels themselves → 100% found, 0 mm, and B2 at 100%;
  - every homography offset by 1 mm → 1 mm;
  - one Visit with an extra Dart, and one with two compensating wrong Darts → both wrong;
  - a Visit hidden in p1 → left out of B2 and counted in its own figure.

  It also pins the bar's numbers in `BarTest`, each at its edge, reads the treble and double rows
  apart, and counts a Photo missing from the predictions as a Board not found. It fails towards a bar
  that reads better than the model is.
- **`ReviewTest`** checks that a label edited after its review is unreviewed again, so `check`
  fails and its crossings are not `checked`, and that a held-out Photo fails `check` when reviewed
  once, or when its second review changed it and no later review followed.
  It fails towards unchecked labels counting as truth.
- **`HeldOutTest`** checks that the builder, given a held-out Photo by name, by hash or by Capture
  session, refuses it, and that `verify-held-out` fails on one changed byte in a Photo, a label, a
  sheet or a review manifest. It fails towards a Held-out set that leaks into training.
- **`PathsTest`** checks that a `DARTS_DATA` inside the repo or a sibling worktree is refused,
  including through a symlink, and so is a symlinked folder under it. It fails towards Photos
  sitting where git can reach them.
- **`DeepDartsTest`** checks that the restricted unpickler loads a DataFrame built in the test and
  refuses a pickle that names any other class. It fails towards running code from a download.
- **`IngestTest`** checks that a test JPEG with GPS and an orientation tag comes out upright with no
  EXIF and its pixels not re-encoded, and that a Visit with two Photos stops the ingest, even when
  the next Visit's four make the total right. It fails towards a location leaving in a file, or a
  label on the wrong Photo.

## Documents this phase amends

| Document | Change | At |
| --- | --- | --- |
| ADR-0008 | dated amendment: the 80 Calibration points as crossing centres with their names and radii (§2); DeepDarts' labels from DataPort's CC BY `labels_pkl.zip`, not the unlicensed repo's `labels.pkl`; `models.zip` unused; the licence rule worded as permissive licences only for code adapted, trained with or shipped, with runtime libraries bundled in a dev tool's wheel under a runtime exception or the LGPL allowed and listed (§0) | A |
| ADR-0008 | if DeepDarts is left out (D5): a dated amendment saying so, and that its licences-screen credit falls away | C |
| `PLAN.md` | Phase M2's line: "trained with permissively licensed code", as in ADR-0008's amendment | A |
| `CONTEXT.md` | **Capture session**: one phone, one light, one day, the unit the Held-out set is drawn in; not *session* alone, which a game may want later. **Held-out set**: the Capture sessions never trained or tuned on; not *test set*. **Hand point**: one of the four Calibration points clicked by hand on a Photo, from which pre-fill projects the rest; not *anchor*, which Calibration point already rules out | A |
| `CLAUDE.md` | Layout: `ml/`. Commands: `uv run --directory ml darts-ml …` and its tests. Stack: a row for `ml/` (uv, Python 3.12, code only) | A |
| `.github/workflows/ci.yml` | the `ml` job (§2) | A |
| `docs/phase-M1.md` | B's verdict and the readings as they are taken | B to H |
| `docs/DOD.md`, `docs/PLAN.md` | tick M1; `DOD.md`'s M1 items removed once done | H |

Not amended: the privacy policy, `play-app-content.md` and the listing. Nothing about the app
changes, and no player's Photo is involved. The licences screen gains the DeepDarts credit in phase
3, as `PLAN.md` already says, if C brought DeepDarts in.

## Known gaps, deliberately

- **One Board, one room or two, the owner's Darts.** The Held-out set measures how the model copes
  with new Capture sessions, not with new homes. A second Board (D6) is the cheapest way to close
  part of this. The rest closes only with testers' Photos, which never leave their phones. The
  door's feedback hand-off is the signal.
- **One or two phones.** Each make has its own lens and image processing. Closing this costs a
  borrowed phone per make for a Capture session or two.
- **A plane does not model lens distortion.** Phones correct most of it, but not all. `check`'s
  residuals (§5) show how much is left, and M2 decides whether it needs a distortion term.
- **Hand labels have a floor.** B measures it. Below it, no millimetre figure means anything, which
  is why the gate comes first.
- **The Held-out set is small.** At 60 counted Visits, B2 is ±10 points (§7). Each extra held-out
  Capture session costs about 2.5 hours and narrows that.
- **B2 says nothing about Visits hidden in p1.** They are reported beside it (§7), and phase 2 is
  where they are answered.
- **DeepDarts may not come in** (D5). If the ask goes unanswered, M2 trains on the owner's Photos
  alone and B2 has no outside comparison (§4).
- **Whether CC BY reaches trained weights is unsettled.** The credit is given anyway (ADR-0008).
  That costs one line on a screen, and it is the safe answer either way.

## Readings

`PLAN.md` rule 3. M1 changes no app, so its readings are taken off the data and the tools, with the
command that took them. `DARTS_DATA` must be set, or default, to the data directory. Run `darts-ml
paths` first: it prints the directory it resolved, refuses one inside the repo, and checks that
`jpegtran` is installed.

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | **The gate.** Pilot s01: a–b over all, dragged and undragged crossings; a–c on round c's 10 Photos; minutes per Photo | `darts-ml repeatability s01` | *(B)* |
| R2 | DeepDarts as downloaded: file sizes, SHA-256, 16,050 Photos, label rows, the source used; or the ask, its date and the answer, and whether DeepDarts is in (D5) | `sha256sum`, then `darts-ml deepdarts convert` and its summary | *(C)* |
| R3 | DeepDarts' four points are `do-5-20`, `do-17-3`, `do-8-11` and `do-13-6`, in that order | `darts-ml deepdarts overlay --sample 10`, read by eye | *(C)* |
| R4 | What was captured: Capture sessions, Photos, Visits, and each hard case counted from the sheets | `darts-ml summary` | *(D)* |
| R5 | Label QA: `check` clean on every Capture session; Score mismatches found and how each was resolved, and every open one; the 95th percentile of cross-Angle Entry point agreement | `darts-ml check --all` | *(E)* |
| R6 | The Held-out set is frozen and enforced, with at least 60 Visits not hidden in p1 | `darts-ml summary --held-out`; `darts-ml verify-held-out`; `darts-ml build` and its count of refused Photos | *(G)* |
| R7 | The harness reads perfect as perfect | `darts-ml evaluate --predictions labels` → found 100%, 0 mm on both wire rows, and B2 at 100% less the counted Visits with an open mismatch on p1. One on p2 or p3 alone does not lower B2, which reads p1 only | *(G)* |
| R8 | Nothing private is tracked | `git ls-files ml` lists only code and the manifest; `git status --ignored --short ml` has no `??` line, and its only `!!` lines are `ml/.venv/` and `__pycache__/` folders | *(H)* |
