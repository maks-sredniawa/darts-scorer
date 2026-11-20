# Phase 1 — One Photo of the Board scores a Visit on the phone, offline, and a wrong Dart is corrected with a tap

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
relies on ADR-0008 (the model, its 2026-11-19 runtime amendment), ADR-0002 (the media pipeline),
ADR-0005 (no Photo in a backup) and ADR-0007 (the tip's Visit count), and amends ADR-0008 under D1.
[`CONTEXT.md`](../CONTEXT.md) is owed *Miss* and *unsure* (§3), and nothing else: Board, Dart,
Visit, Photo, Entry point and Score already cover the rest.

**What closing this phase means.** Today the Visit tab is a placeholder: no Photo is taken and no
model is in the app. After this phase a player takes one Photo of the Board after a Visit, with the
system camera or from the Photo Picker, and within a second or two sees each Dart drawn where it
entered the Board with its Score and the Visit's total, all on the phone with the network removed
from the manifest. A Dart the model got wrong is moved, added or removed with a tap. The difference a
device can be asked about: **on an emulator with no network, a DeepDarts validation Photo pushed with
`adb` and picked in the Photo Picker shows the same Darts and total that `darts-ml locate` gives for
it, and the phone's reading of real Visits on a real Board is recorded in R3.**

**`PLAN.md`'s paragraph is wrong in two places, said here first.**

- It reads as if phase 1 waits for M2. Since 2026-11-20 it is built alongside M2 with the best model
  so far, and closes only on a model that met phase-M1.md §7's bar (PLAN.md, phase-M1.md §7).
- It says "tapping the board to correct a dart". With D3, a tap picks a Dart or proposes a new one,
  and a keypad sets its Score: a treble bed is about 8 dp wide on a 5.5" phone, which no finger hits
  reliably.
- Phase 3 lists "the DeepDarts attribution on the licences screen". It moves here: ADR-0008's
  2026-11-19 amendment puts it on the Credits screen from the first build that ships the model,
  beside LiteRT, Eigen and the libraries compiled into LiteRT. Phase 3 keeps the first-run path.

---

## Decisions for the owner

| # | Decision | Recommended |
| --- | --- | --- |
| **D1** | **Where the model file the app ships lives** (§2) | **Committed to git, at `app/src/main/assets/model/`, beside its export record.** CLAUDE.md and ADR-0008 keep weights out of git, but they were written about `ml/`'s training weights (`best.pt`) and the data; the exported `.tflite` is a build input like an icon, and anyone can unzip it from the public APK anyway. About 12.8 MB per model, and a model is swapped a handful of times. The alternatives cost more: Git LFS's free 1 GiB of bandwidth a month runs out at about 75 CI checkouts; a release asset downloaded by a Gradle task needs a pinned SHA-256, a cache and a network step in every build, local ones included. ADR-0008 and CLAUDE.md's stack line are amended to say training weights stay out and the shipped model is in |
| **D2** | **Is the Photo kept after scoring?** (§4) | **No.** The first version stores no Visit history (phase 0), so the Photo lives only while its Visit is on screen: written through `MediaFiles` as the `photos` kind (2048 px long edge, q85), deleted when the next Visit starts, and any left over swept at start. Already outside Auto Backup (ADR-0005). Keeping Photos comes with history, in its own phase and ADR |
| **D3** | **Where a result is shown and corrected** (§3) | **On the Photo, cropped to the Board, and corrected with a keypad.** The crop shows what the model saw, so a phantom Dart or a wall hole read as a Miss is obvious. A tap on a Dart's marker or its chip opens a sheet with Single / Double / Treble, 1–20, Bull 25, Bull 50 and Miss, the current Score preselected, so a wrong ring or neighbour is one tap. A tap on an empty spot proposes a new Dart with the bed under the finger. No loupe, no dragging: nothing later needs the corrected point in millimetres. The alternative, a drawn Board that snaps to beds, still has the 8 dp problem and needs the ring chosen anyway |
| **D6** | **"Enter the Score yourself" when no Board is found** (§3) | **Yes.** The same keypad with no Darts, so a Visit is never lost to a bad Photo. It makes the app usable with no model result at all, which at 69% exactly right is worth one more button |
| **D4** | **A game (501, a countdown) in this phase?** | **No: phase 1 scores single Visits.** A game adds its own words (Leg, Checkout, bust), state that has to survive process death, and a screen; it is worth a phase of its own once a Visit's Score is trusted. Each Visit's total is shown, and nothing is carried between Visits |
| **D5** | **Which model ships until M2's bar is met** | **The chosen D run, `2026-11-19-darts-640-s2-ring-ext`** with `ENTRY_THRESHOLD` 0.25: 69.2% of validation Visits exactly right. It is swapped for the run that meets the bar (F); until then no build reaches a track anyone but the owner sees (phase P has not uploaded anything yet) |

---

## 0. What this phase inherits

- **The model and its runtime** (phase-M2.md §5, R4): `best.tflite`, 640 px input, two heads (Board
  1×82×160×160 at stride 4, Entry 1×3×320×320 at stride 2), float32. LiteRT 1.4.2's Interpreter API,
  bundled; no Play part, no manifest change. Parity with PyTorch: 0 of 1,070 Visits differ.
- **The pipeline is two passes, and only Python runs it today** (`ml/src/darts_ml/locate.py`): the
  Photo letterboxed into 640 px, the Board found, the Photo re-framed on the Board
  (`augment.framing`) and run again, the Darts read from the second pass. Between the passes and
  after them: sigmoid, a per-channel argmax for the 80 Calibration points, local-maximum peaks for
  Entry points, RANSAC (500 rounds, 3 mm, at least 8 inliers), a least-squares refinement, at most
  three Entry points kept. All of it is ported to Kotlin here; none of it is new.
- **The photo path survived phase 0** without a caller: `MediaFiles` writes and downsamples a
  `photos` kind; nothing calls `TakePicture` or the Photo Picker yet.
- **The Visit count for the tip** (ADR-0007): `AppPreferences.incrementVisitsScored()` exists, and
  nothing calls it until this phase.
- **The asymmetry that shapes the phase:** the mechanism (pixels in, Score out) can be proven on the
  emulator against Python, Photo by Photo; whether it is good enough on a real Board can only be read
  on the owner's phone, and is bounded by the model rather than by this phase's code.

## What is in, and what is deliberately not

**In:** taking a Photo with the system camera or picking one, the two-pass inference on LiteRT with
a chosen thread count, the Darts drawn with their Scores and the Visit's total, correcting a Dart
(D3), the paths for no Board found and no camera app, the Credits entries the model owes, and the
Visit count the tip reads.

**Not in, each with a reason:**

- **Several Angles of one Visit, and asking for another.** That is phase 2, and it needs merging in
  Board millimetres, which needs this phase's single-Photo result to merge.
- **A game (D4).**
- **Visit history and keeping Photos (D2).** Nothing is stored that a later phase would have to
  migrate before its own ADR says how.
- **A GPU or NNAPI delegate.** About 60–70 ms per Photo for both passes on the emulator's CPU is
  already under the time a player waits for the camera to close; a delegate is a per-vendor test
  matrix bought for nothing the player sees.
- **A live camera view.** `PLAN.md`'s *Not in this plan*.

**The tempting one: sending a corrected Visit back to train the model.** A correction is exactly the
label M1 is short of, and storing it would look free. It is a Photo leaving the phone, which only
phase S's opt-in may do, with its own ADR and privacy policy. Nothing from a correction is kept.

---

## Checkpoints

| | Checkpoint | Merges | Depends on |
| --- | --- | --- | --- |
| **A** | **The gate** — does the Kotlin pipeline give Python's Darts on the same Photos? | `test:` and `chore(ml):` for the apparatus; the verdict is a reading | D1 |
| **B** | **A Visit scored from one Photo**: camera or Picker in, Darts and total out, the no-Board and no-camera paths, Credits, the Visit count | `feat:` | A, D2, D5 |
| **C** | **Correcting a Dart** | `feat:` | B, D3 |
| **D** | **Readings on a real Board**: the thread count chosen, R3's Visits | `docs:` | C |
| **E** | **The model that met the bar** swapped in, R3 read again | `feat:` | D, M2's G |

**A comes first** because a port that differs from Python in its resampling or its RANSAC would make
every later reading measure the port rather than the model, and nothing on screen would show it.
**C after B** because correcting needs a result to correct, and B alone is already a usable build for
the owner. **E is the only checkpoint that waits on M2.**

---

## 1. The gate: does the phone pipeline match Python?

### The question, in the form that can be measured

On DeepDarts' validation Photos (no owner Photos exist yet), run through the app's Kotlin pipeline on
an emulator and through `darts-ml locate` on this machine, from the same files:

1. Is the Board found in the same Photos, with the 80 projected crossings within 0.1 mm of Python's?
2. Are the kept Darts' Scores the same, as a multiset, in at least 99% of Photos?

A second question rides along, answered in Python alone: does storing the Photo as `MediaFiles`'
2048 px q85 JPEG (D2) change `darts-ml evaluate`'s exactly-right share on the Validation set by more
than one point against the camera original?

### The apparatus

- `darts-ml phone-parity <run> --photos <n>`: picks the Photos, writes Python's result for each
  (Board found, the crossings in mm, the kept Darts' Scores) to a JSON file beside them.
- An instrumented test in `app/src/androidTest/` that reads the Photos and the JSON pushed with
  `adb`, runs the app's own pipeline class on each, and fails on any difference beyond the bounds
  above, printing the Photo's name. The pipeline class is the one B's screen calls; the test does not
  get its own copy.

### The verdicts, decided now

1. **Both hold** → B.
2. **The Board matches and Darts differ in more than 1% of Photos, traced to resampling** (Android's
   bilinear filter against PIL's) → the warp is written in Kotlin to PIL's arithmetic, read again.
3. **Still apart after that, or the Board differs** → stop, and the figures go to the owner with the
   cause; nothing is built on a port that disagrees with the model it runs.

### The verdict, taken *(date)*

## 2. The model in the app (D1)

- **Where:** `app/src/main/assets/model/darts.tflite` and `darts.json` (the export record: run,
  weights SHA-256, size, operations), stored uncompressed (`androidResources.noCompress`) so LiteRT
  maps it instead of copying 12.8 MB onto the heap.
- **Swapping it** is a commit that replaces both files and changes nothing else; the app reads the
  input size and the heads' shapes from the model and the record, never from constants.
- **Threads:** `Interpreter.Options().setNumThreads(n)`, with *n* chosen on the phone's reading (R2),
  since LiteRT's default of one thread read about three times slower on the emulator. The emulator's
  AVX-only CPU is not a phone's, so the choice is not taken there.
- **Credits** (ADR-0008, ADR-0007's licences screen): LiteRT (Apache-2.0), Eigen (MPL-2.0, link to
  its source), XNNPACK, ruy, gemmlowp, FlatBuffers, fft2d and cpuinfo under their own licences, and
  the DeepDarts dataset (CC BY 4.0) the model was trained on. Those the dependency list cannot see go
  in `SupportConfig.BUNDLED_CREDITS`. They ship in B, the first build carrying the model.

## 3. The result and correcting it (D3, D6)

The design brief behind D3 was taken on 2026-11-20; its wireframes go into the checkpoint C PR.

- **The result:** the Photo cropped to the Board (not warped, so Darts still look like Darts), a
  numbered marker at each Entry point with the white and black keyline, the total in
  `displayLarge`, and a chip per Dart (*1 · T20 · 60*). Markers are numbered by position, top to
  bottom, and the copy never implies throw order: the Photo cannot know it.
- **Unsure Dart** (confidence below 0.5): a dashed keyline and a *?* badge on the marker, an outlined
  chip with *Check*, and *Check Dart 2* under the total. Shape and text, never colour alone (phase T
  reuses this). Opening it and pressing *Done* confirms it. Nothing blocks *Next Visit*.
- **Changing a Dart:** its marker or chip opens the sheet; *Done* commits; the marker moves to the
  centre of the chosen bed and becomes a hollow ring, so nobody reads it as a measured Entry point.
- **Adding a Dart:** *Add a Dart* while fewer than three are shown, or a tap on an empty spot of the
  Photo, which preselects the bed under the finger through the homography.
- **Removing a Dart:** *Remove Dart* in the sheet, with *Undo*. It is not *Miss*: a Miss is a thrown
  Dart that scored 0, a removed one was never there.
- **More than three found:** all shown, with *4 Darts found. A Visit has three.* None is dropped
  for the player. Fewer than three is a legitimate Visit and says nothing.
- **Board found, no Darts:** Score 0, *No Darts found*, and *Add a Dart*. Not an error.
- **No Board found:** the whole Photo with no markers, a warning banner with one hint (the whole
  Board in the frame, more light), and *Take another Photo*, *Choose a Photo*, *Enter the Score
  yourself* (D6).
- **The flow:** empty → camera → *Reading the Photo…* → result → *Next Visit*, which opens the camera
  directly, so a Visit costs one tap. The previous result stays until a new Photo comes back, so a
  cancelled camera loses nothing. Controls sit in the bottom third. The tip ask stays on the empty
  state only.
- **TalkBack:** the Score is a heading and a polite live region (*Visit Score 81. Three Darts: treble
  20, 20, 1. Dart 2 is unsure.*); the Photo is one node with that summary and its markers are not
  focusable; the chips are the focus targets, with *Remove Dart* as a custom action. The keypad is
  the path that needs no precise tap, for everyone, so there is no separate accessible mode.

`CONTEXT.md` gains **Miss** (a thrown Dart that scored 0; not *removed*) and **unsure** (a Dart
below the model's confidence of 0.5, shown with *Check*; not *low confidence* in the UI).

## 4. A Visit's life

| Moment | What happens |
| --- | --- |
| *Take a Photo* tapped | `TakePicture` into a `FileProvider` URI in `cacheDir`. No `CAMERA` permission (PLAN.md *Asks*). No camera app: the button says so and the Picker stays |
| *Pick a Photo* tapped | The Photo Picker, one image. No permission on any API level |
| Photo arrives | Through `MediaFiles` as the `photos` kind, the camera's file deleted; then both passes off the main thread |
| No Board found | The Photo is shown with a line saying the Board was not found and how to take one that works (the whole Board, face-on or from the side, in light); *Take another* |
| Board found | §3's result |
| *Next Visit* | The Photo deleted, `incrementVisitsScored()` called once, the screen empty again |
| Process death mid-Visit | The Photo's relative path survives in `SavedStateHandle`; the result is recomputed from it. Corrections made before the death are lost, and that is accepted (Known gaps) |

## Tests

- **Scoring** (`board.score` ported): every segment, ring and both bulls, and points 0.1 mm either
  side of each wire, against a table written by `ml/` from the Python function, so the two cannot
  drift. Fails toward a wrong Score.
- **Homography and RANSAC:** a fit on exact points returns them to 1e-9 mm; with 30% of points moved
  50 mm, RANSAC keeps the rest; fewer than 8 inliers is "not found", never a Board. Fails toward a
  Board found where there is none.
- **Decoding:** saved heads from three Photos (one with no Board, one with two Darts in one bed)
  decode to Python's peaks to 1e-4 px.

## Documents this phase amends

- **ADR-0008:** the shipped model is committed (D1); the Credits list is final.
- **`CLAUDE.md`:** the `ml/` stack line (D1), and the Layout gains the inference package.
- **`CONTEXT.md`:** Miss and unsure (§3).
- **`PLAN.md`'s phase 1 paragraph:** the tap picks, the keypad sets (D3).
- **`PLAN.md`:** phase 3 loses the DeepDarts attribution; phase 1 is ticked at E.
- **Privacy policy, Data safety:** no change. Both already say the Photos are processed on the phone
  and never sent; this phase makes that true rather than promised. Re-read at B, not edited.
- **`docs/store-listing.md`:** nothing until phase N.

## Known gaps, deliberately

- **Corrections are lost on process death.** Keeping them means storing a Visit, which D2 defers.
  The Photo itself is recomputed, so the cost is a few taps.
- **The model before E misreads about one Visit in three.** That is what correcting is for, and why
  no build reaches a tester before E.

## Readings

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | A's gate: Board and Darts against Python on DeepDarts validation Photos | `darts-ml phone-parity`, then the instrumented test | |
| R2 | Time per Photo, both passes, at 1, 2, 4 and 6 threads, on the owner's phone | the debug build's timing line in `logcat` | |
| R3 | Real Visits on a real Board in room light: exactly right, corrected, and taps per correction | by hand, at the Board | |
