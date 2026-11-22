# Phase 1 — One Photo of the Board scores a Visit on the phone, offline, and a wrong Dart is corrected with a tap

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
relies on ADR-0008 (the model, its 2026-11-19 runtime amendment), ADR-0002 (the media pipeline),
ADR-0005 (no Photo in a backup) and ADR-0007 (the tip's Visit count), and amends ADR-0008 under D1.
[`CONTEXT.md`](../CONTEXT.md) is owed *Miss* and *unsure* (§3), and *Bed*, which C's code needed:
Board, Dart, Visit, Photo, Entry point and Score already cover the rest.

**What closing this phase means.** Today the Visit tab is a placeholder: no Photo is taken and no
model is in the app. After this phase a player takes one Photo of the Board after a Visit, with the
system camera or from the Photo Picker, and within a second or two sees each Dart drawn where it
entered the Board with its Score and the Visit's total, all on the phone with the network removed
from the manifest. A Dart the model got wrong is moved, added or removed with a tap. The difference
a device can be asked about: **on an emulator with no network, a Photo from DeepDarts' val split
pushed with `adb` and picked in the Photo Picker shows the same Darts and total that Python's
`locate()` gives for the file `MediaFiles` wrote from it, as `darts-ml phone-parity` writes them out
(§1), and the phone's reading of real Visits on a real Board is recorded in R3.**

**`PLAN.md` is wrong in two places, said here first.**

- Its phase 1 paragraph says "tapping the board to correct a dart". With D3, a tap picks a Dart or
  proposes a new one, and a keypad sets its Score: a treble bed is about 8 dp wide on a 5.5" phone,
  which no finger hits reliably.
- Phase 3 lists "the DeepDarts attribution on the licences screen". It moves here: ADR-0008's
  2026-11-19 amendment puts it on the Credits screen from the first build that ships the model,
  beside LiteRT, Eigen and the libraries compiled into LiteRT. Phase 3 keeps the first-run path.

---

## Decisions for the owner

All six were decided on **2026-11-20**, each as recommended.

| # | Decision | Decided 2026-11-20 |
| --- | --- | --- |
| **D1** | **Where the model file the app ships lives** (§2) | **Committed to git, at `app/src/main/assets/model/`, beside its export record.** CLAUDE.md and ADR-0008 keep weights out of git, but they were written about `ml/`'s training weights (`best.pt`) and the data; the exported `.tflite` is a build input like an icon, and anyone can unzip it from the public APK anyway. About 12.8 MB per model, and a model is swapped a handful of times. The alternatives cost more: Git LFS's free 1 GiB of bandwidth a month runs out at about 75 CI checkouts; a release asset downloaded by a Gradle task needs a pinned SHA-256, a cache and a network step in every build, local ones included. ADR-0008 and CLAUDE.md's stack line are amended to say training weights stay out and the shipped model is in |
| **D2** | **Is the Photo kept after scoring?** (§4) | **No.** The first version stores no Visit history (phase 0), so the Photo lives only while its Visit is on screen: written through `MediaFiles` as the `photos` kind (2048 px long edge, q85), deleted when the next Visit's Photo arrives, and any left over swept at start, except the one whose path `SavedStateHandle` still holds after process death (§4). Already outside Auto Backup (ADR-0005). Keeping Photos comes with history, in its own phase and ADR |
| **D3** | **Where a result is shown and corrected** (§3) | **On the Photo, cropped to the Board, and corrected with a keypad.** The crop shows what the model saw, so a phantom Dart or a wall hole read as a Miss is obvious. A tap on a Dart's marker or its chip opens a sheet with Single / Double / Treble, 1–20, Bull 25, Bull 50 and Miss, the current Score preselected, so a wrong ring or neighbour is one tap. A tap on an empty spot proposes a new Dart with the bed under the finger. The Photo zooms and pans for viewing (pinch, double-tap), but a point is never dragged: nothing later needs the corrected point in millimetres. The alternative, a drawn Board that snaps to beds, still has the 8 dp problem and needs the ring chosen anyway. **Amended 2026-11-20:** now that the Photo zooms, a Dart's ring can be long-pressed and dragged onto its Entry point, its Score read through the homography from where it is dropped (§3, *Moving a Dart's ring*). The model's point, Score and unsure flag are kept on the Dart as `ShownDart.read`, never written by a correction, so a drop back on that point that scores the same, or the sheet's *Back to the app's reading*, restores them. For a dragged Dart, `read.at` → `at` with both Scores is a point-level correction label; a keypad correction is a Score-only one. Neither is kept (*The tempting one*, below) |
| **D4** | **A game (501, a countdown) in this phase?** | **No: phase 1 scores single Visits.** A game adds its own words (Leg, Checkout, bust), state that has to survive process death, and a screen; it is worth a phase of its own once a Visit's Score is trusted. Each Visit's total is shown, and nothing is carried between Visits |
| **D5** | **Which model ships until M2's bar is met** | **The chosen D run, `2026-11-19-darts-640-s2-ring-ext`** with `ENTRY_THRESHOLD` 0.25: 69.2% of validation Visits exactly right. It is swapped for the run that meets the bar (F); until then no build reaches a track anyone but the owner sees (phase P has not uploaded anything yet) |
| **D6** | **"Enter the Score yourself" when no Board is found** (§3) | **Yes.** The same keypad with no Darts, so a Visit is never lost to a bad Photo. It makes the app usable with no model result at all, which at 69% exactly right is worth one more button |

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
  emulator against Python, Photo by Photo; whether it is good enough on a real Board can only be
  read on the owner's phone, and is bounded by the model rather than by this phase's code.

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
phase S's opt-in may do, with its own ADR and privacy policy. Nothing from a correction is kept: a
dragged Dart's two points and two Scores (D3's 2026-11-20 amendment) would be a point-level label,
and they live only in the ViewModel, gone with the Visit.

---

## Checkpoints

| | Checkpoint | Merges | Depends on |
| --- | --- | --- | --- |
| **A** | **The gate** — does the Kotlin pipeline give Python's Darts on the same Photos? With it, the model, LiteRT and their Credits (§2) | `feat:` for the pipeline, the model and the Credits, which ship in the app; the apparatus beside it; the verdict is a reading | D1 |
| **B** | **A Visit scored from one Photo**: camera or Picker in, Darts and total out, the no-Board and no-camera paths, the Visit count | `feat:` | A, D2, D5 |
| **C** | **Correcting a Dart** | `feat:` | B, D3 |
| **D** | **Readings**: the thread count chosen, `minSdk` decided (§5), R3's Visits | `docs:`, `chore:` if `minSdk` moves | C |
| **E** | **The model that met the bar** swapped in, R3 read again | `feat:` | D, M2's G |

**A comes first** because a port that differs from Python in its resampling or its RANSAC would make
every later reading measure the port rather than the model, and nothing on screen would show it. **C
after B** because correcting needs a result to correct, and B alone is already a usable build for
the owner. **E is the only checkpoint that waits on M2.**

---

## 1. The gate: does the phone pipeline match Python?

### The question, in the form that can be measured

On Photos from DeepDarts' val split (no owner Photos exist yet), each first written through
`MediaFiles` on the emulator as the app writes a picked Photo, run through the app's Kotlin pipeline
there and through Python's `locate()` on this machine, from the same written files:

1. Is the Board found in the same Photos, with the 80 projected crossings within 0.1 mm of Python's?
2. Are the kept Darts' Scores the same, as a multiset, in at least 99% of Photos?

A second question rides along, answered in Python alone: does storing the Photo as `MediaFiles`'
2048 px q85 JPEG (D2) move the exactly-right share by more than one point? Read with `darts-ml
deepdarts score --split val`, once on the val Photos as they are and once on a copy of them
re-encoded to 2048 px q85 (`--as-stored`, which writes the copies as `MediaFiles` writes the
`photos` kind and scales the labels with them).

### The apparatus

- `darts-ml phone-parity --run <run> --photos <n>`: picks the Photos, pushes them with `adb`, has
  the instrumented test write each through `MediaFiles` as the `photos` kind and pulls the written
  files back, then writes Python's `locate()` result for each written file (Board found, the 80
  crossings in Photo pixels, the kept Darts' Scores) to a JSON file and pushes it. A crossing is
  compared by mapping Python's pixel through the phone's homography and measuring how far it lands
  from the crossing's own millimetres.
- An instrumented test in `app/src/androidTest/` that reads the written Photos and the JSON, runs
  the app's own pipeline class on each, and fails on any difference beyond the bounds above,
  printing the Photo's name. The pipeline class is the one B's screen calls; the test does not get
  its own copy, and the `MediaFiles` call is the one the Picker's path makes. Both methods are
  skipped when nothing was pushed, so CI's instrumented legs stay green without `DARTS_DATA`.
- **Running it** (`ml/README.md`, *phone-parity*, says what each step moves where):

  ```bash
  emulator -avd pixel-api36 -no-window -no-audio &
  export ANDROID_SERIAL=emulator-5554
  ./gradlew assembleDebug assembleDebugAndroidTest
  adb install -r -t app/build/outputs/apk/debug/app-debug.apk
  adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
  uv run --directory ml darts-ml phone-parity --run 2026-11-19-darts-640-s2-ring-ext --photos 200
  adb emu kill
  ```

  `adb install` rather than `connectedAndroidTest`, which uninstalls the app and the pushed files
  when it finishes. By hand, the same run is: `adb push` the Photos to
  `/sdcard/Android/data/com.maksforge.dartsscorer.debug/files/parity/source/`; `adb shell am
  instrument -w -e class app.dartsscorer.scoring.PhoneParityTest#writesEachPhotoThroughMediaFiles
  com.maksforge.dartsscorer.debug.test/androidx.test.runner.AndroidJUnitRunner`; `adb pull` the
  folder's `written/`; write `expected.json` from them and `adb push` it beside `source/`; the same
  `am instrument` with `#matchesPythonOnEachPhoto`; `adb pull` the folder's `report.txt`.

### The verdicts, decided now

RANSAC samples its sets of four at random, and numpy's generator and Kotlin's draw different sets
from the same seed, so question 1 is read with that in mind: a Board found by one side and not the
other, where both are near `MIN_INLIERS` (8), is investigated, not counted as a failure on its own.

1. **Both hold** → B.
2. **The Board matches and Darts differ in more than 1% of Photos, traced to resampling** (Android's
   bilinear filter against PIL's) → the warp is written in Kotlin to PIL's arithmetic, read again.
3. **Still apart after that, or the Board differs** → stop, and the figures go to the owner with the
   cause; nothing is built on a port that disagrees with the model it runs.

### The verdict, taken 2026-11-20: 1, both hold → B

On 200 of DeepDarts' 1,070 val Photos, every 5th or so in the split's order
(`darts-ml phone-parity --run 2026-11-19-darts-640-s2-ring-ext --photos 200`), on two emulators:

| | `pixel-api36` (API 36) | `urgent-api26` (API 26) |
| --- | --- | --- |
| Board found by both / neither / one only | 200 / 0 / 0 | 200 / 0 / 0 |
| Worst crossing, phone's homography against Python's | 0.00513 mm | 0.00513 mm |
| Photos with a crossing over 0.1 mm | 0 | 0 |
| Kept Darts' Scores the same, as a multiset | 200 of 200 | 200 of 200 |
| Both passes per Photo, median, debug build, 4 threads | 560 ms | 341 ms |

- **The RANSAC caveat above did not arise.** The port draws its sets of four from a replica of
  numpy's `default_rng(0)` and `choice`, checked against numpy's own draws (`rng.json`), so both
  sides fit the same sets and the Board is compared without the allowance near `MIN_INLIERS`.
- **Verdict 2's remedy was taken up front.** The warp follows Pillow's arithmetic (its antialiased
  bilinear reduce in fixed point, then its perspective sample truncated to a byte), and a unit test
  holds it to Pillow's bytes (`warp.json`). What is left between the two sides is the JPEG decoder
  (Android's against Pillow's libjpeg-turbo) and float order; it moved no crossing by more than
  0.006 mm.
- **The second question: 0.5 points, so D2 holds.** On all 1,070 val Photos, exactly right read
  740 (69.2%) as they are and 735 (68.7%) as stored; Darts right 1,857 and 1,845 of 2,114; the
  Board found in all 1,070 both times, wire medians 0.282 and 0.285 mm (treble), 0.320 and
  0.324 mm (double). Every val Photo is 800 px square with no EXIF rotation, so this reads the q85
  re-encode alone: the 2048 px cap on a phone's 12 MP Photo is not exercised here, and R3's real
  Visits are where it is.
- **The times are not R2 or R4.** They are a debuggable build on an emulator's CPU, with the warp
  and decoding in Kotlin counted in. The same pipeline in a release-shaped build (R8 on, not
  debuggable) read about 260 ms a Photo on `urgent-api26`, and LiteRT ran there with no keep rule
  of our own: its AAR's consumer rules cover it.

### Colour-profiled Photos (2026-11-21)

The 17 Visits the owner marked on 2026-11-20 (`darts-ml pull-marked`) read differently in Python
than on the phone: `locate()` on the stored Photos gave the app's kept Scores in 4 of 17 Visits, and
not one with every Dart within a pixel of the app's. The cause was colour, not the port. The
owner's Xiaomi tags its Photos Display P3; `MediaFiles` decoded them in P3, and `Bitmap.compress`
wrote the P3 profile into the stored Photo. The phone's `decodePhoto` reads through `getPixels`,
which hands back sRGB; Pillow's `convert("RGB")` ignores the profile and hands back the raw P3
numbers. The two differ by 1.2 levels on average and up to 55, enough to move an Entry peak that
was a near-tie. DeepDarts' JPEGs carry no profile, so R1 never met one. Two checks proved it:
Python on LittleCMS-converted sRGB copies gives the app's Scores in 13 of 17 Visits, every Dart
within 0.1 px; and with only the profile's APP2 segment stripped from the files, the emulator and
Python agree on all 18 Photos.

The fix has three parts:

- **The app stores sRGB.** `MediaFiles` decodes with `inPreferredColorSpace` sRGB, so a stored
  Photo or thumbnail is sRGB with no P3 profile, and both sides read the same numbers from it.
  Photos already stored in P3 still read as before: `getPixels` converts them.
- **`ml/` reads sRGB.** Every step opens a Photo through `images.open_srgb`, which converts a
  profiled Photo with LittleCMS. On the 17 marked Visits it gives the app's Scores in 13; the other
  4 differ by one Dart each, a near-tie that Android's conversion (Skia) and LittleCMS settle one
  level apart. Those Photos were stored in P3; new ones are sRGB and need no conversion (the sRGB
  profile Android writes into every JPEG counts as none: LittleCMS would move a colour by one level
  at most, so `open_srgb` leaves those pixels as they are). `ingest`
  now keeps the profile (`jpegtran -copy icc`) rather than strip it and leave P3 numbers untagged.
- **The gate carries a profiled Photo through `MediaFiles`.** `phone-parity` also pushes
  `--display-p3` of its val Photos (default 20) rewritten in Display P3's numbers and tagged with
  its profile. They check the app's half: `MediaFiles` stores them as sRGB, and the app reads the
  stored files as Python reads them. They never reach Python as P3, since `locate()` there reads
  only the files `MediaFiles` wrote. Python's half is held by `test_locate.py`
  (`ColourProfiledPhotoTest`: `locate()`'s loader gives a P3 Photo the same input as its
  `open_srgb` conversion) and `test_images.py`. `MediaFilesTest` holds the storing on every API
  level from a committed P3 JPEG that `darts-ml phone-fixtures` writes, because API 26's
  `Bitmap.compress` embeds no P3 profile in a source the test encodes itself. On `pixel-api36`,
  200 val Photos and 20 P3 copies: Board found by both in 220 of 220, worst crossing 0.00513 mm,
  kept Darts' Scores the same in 220 of 220.

## 2. The model in the app (D1)

- **Where:** `app/src/main/assets/model/darts.tflite` and `darts.json` (the export record: run,
  weights SHA-256, size, operations), stored uncompressed (`androidResources.noCompress`) so LiteRT
  maps it instead of copying 12.8 MB onto the heap.
- **Swapping it** is a commit that replaces both files and changes nothing else; the app reads the
  input size and the heads' shapes from the model and the record, never from constants.
- **Threads:** `Interpreter.Options().setNumThreads(n)`, with *n* chosen on the phone's reading
  (R2), since LiteRT's default of one thread read about three times slower on the emulator. The
  emulator's AVX-only CPU is not a phone's, so the choice is not taken there.
- **Credits** (ADR-0008, ADR-0007's licences screen): LiteRT (Apache-2.0), Eigen (MPL-2.0, link to
  its source), XNNPACK, ruy, gemmlowp, FlatBuffers, fft2d, cpuinfo, pthreadpool, FP16 and FXdiv under
  their own licences, and the DeepDarts dataset (CC BY 4.0) the model was trained on. Those the
  dependency list cannot see go in `SupportConfig.BUNDLED_CREDITS`, with the licence texts in
  `assets/licences/`. **They ship
  in A** (moved from B on 2026-11-20): A's merge is the first build that carries LiteRT and the
  model, and the obligation travels with the binary, not with the screen that first calls it.

## 3. The result and correcting it (D3, D6)

The design brief behind D3 was taken on 2026-11-20; its wireframes go into the checkpoint C PR.

- **The result:** the Photo cropped to the Board (not warped, so Darts still look like Darts), a
  marker at each Entry point, the total in
  `displayLarge`, and a chip per Dart (*1 · T20 · 60*). A marker is a thin ring with its centre
  clear, so the dart tip shows through: a 16 dp hole inside a light, a dark and a light band (1,
  1.5 and 1 dp, about 23 dp across), so it reads on a dark Board and a light wall. Its number sits
  beside it in a `labelMedium` badge touching the ring at 45° up and to the right, flipped to
  whichever side stays inside the crop. Markers are numbered by position, top to bottom, and the
  copy never implies throw order: the Photo cannot know it.
- **Zooming in to check:** pinch (1× to 4×) or double-tap (1× to 2.5× about the tapped point, and
  back) zooms the Photo, and a one-finger drag pans it once zoomed in. The Photo always fills its
  box; the markers keep their screen size, so zooming uncovers the tip. A drag at 1× or at a pan
  edge scrolls the page instead, a pan never adds a Dart, and a tap still opens a marker (on its
  badge or within 24 dp of the Dart, on screen) or proposes the bed under the finger. A new Photo
  starts at 1×; a correction keeps the zoom. With no drag (TalkBack, switch access, a keyboard;
  WCAG 2.5.7), the Photo's accessibility actions do the same: *Zoom in* and *Zoom out* step ×2
  about its centre, and while zoomed *Move left*, *right*, *up* and *down* show a third of the box
  further that way. The Photo stays one node and the chips are still the path to each Dart. A
  finger held still on a marker for a long press drags its ring instead (*Moving a Dart's ring*).
- **Unsure Dart** (confidence below 0.5): a dashed ring (4 dp on, 3 dp off) and an *n?* badge in
  `tertiaryContainer`, where a measured Dart's badge is a plain *n* in `surfaceContainerLowest`; an
  outlined chip with *Check*, and *Check Dart 2* under the total. Shape and text, never colour alone
  (phase T reuses this). Opening it and pressing *Done* confirms it. Nothing blocks *Next Visit*.
- **Changing a Dart:** its marker or chip opens the sheet; *Done* commits; the marker becomes a
  badge alone at the centre of the chosen bed, or for a Miss where it was, so nobody reads it as a
  measured Entry point (*The corrected marker*, §4).
- **Moving a Dart's ring** (2026-11-20): a long press on a marker, on its badge or within 24 dp of its
  point, lifts the ring with a haptic tick: it rises in about 120 ms (at once with animations off) to
  sit 72 dp straight above the finger (2026-11-22; until then it stayed under the finger, which hid
  it) and from then on moves with the finger at that offset, so the Entry point is never under the
  hand. The rise alone moves nothing: a release within touch slop puts the ring back. The ring never
  leaves the Photo (2026-11-22): its centre is held one ring radius inside every edge, or less where the Board's rim lies
  closer to that edge (a tightly framed or zoomed Photo), so every bed stays reachable; within 72 dp
  of the top the lift shortens and the ring waits at the edge while the finger closes in beneath it;
  it is neither flipped nor tilted. The drop is the point drawn. The finger may leave the Photo to
  reach its bottom. While held it is drawn as a
  solid ring with four 24 dp arms outside it and four 4 dp ticks inside it that leave an 8 dp clear
  centre, in `inverseSurface` at the ring's weight over a `surfaceContainerLowest` keyline, its badge
  showing the live Score. The chip and the total
  follow it, and a faint ring stays at the model's point while the finger is down. The drop moves
  the Dart there, scored through the homography, no longer unsure, drawn as a solid ring with its
  badge beside it (*The corrected marker*, §4). A release within touch slop moves nothing, and a
  drop within the ring's outer radius of the model's point snaps back to the model's reading whole,
  with a lighter tick, but only where it scores the same: a drop a few millimetres across a wire
  (a treble 20 read where the Dart is in the single) keeps the move and its new Score. A keypad-corrected Dart can be dragged too. The sheet's *Back to the app's
  reading*, shown only while a Dart differs from the model's reading, does the same without a drag
  and also undoes a keypad change. Dragging fixes a misplaced Dart, not a misplaced Board: the
  Score still comes through the same homography. There is no drag accessibility action; the chips
  and the keypad stay the complete path, and the Photo stays one node.
- **The keypad sheet:** each key is a selectable item that exposes its selected state; Single /
  Double / Treble and 1–20 (with the Bulls and *Miss*) are two labelled groups, so two picks read
  as one Score; the preselected key shows a check and a fill, never tint alone; every key is at
  least 48 dp.
- **Adding a Dart:** *Add a Dart* while fewer than three are shown, or a tap on an empty spot of the
  Photo while fewer than three are shown or a filled Miss remains to take over, which preselects the
  bed under the finger through the homography.
- **Removing a Dart:** *Remove Dart* in the sheet, with *Undo*. It is not *Miss*: a Miss is a thrown
  Dart that scored 0, a removed one was never there.
- **Fewer than three found** is made up to three with Misses (2026-11-22; until then it was shown
  as found and said nothing). A Visit is three Darts, so a Dart the model did not find counts 0
  rather than vanishing: each filled Miss has a chip, no marker, and is flagged *Check*, since an
  unfound Dart is as often hidden behind another as off the Board. *Done* on it confirms the Miss;
  a tap on the Photo, which proposes a new Dart, takes the last filled Miss's place instead of
  needing room; *Remove Dart* still drops one for a Visit that really had fewer (a checkout). More
  than three cannot come back: the ported pipeline keeps at most `MOST_ENTRIES` (3), and A holds it
  to that. A later model that changes `MOST_ENTRIES` brings its own state for more.
- **Board found, no Darts:** three filled Misses, Score 0, and *No Darts found*. Not an error.
- **No Board found:** the whole Photo with no markers, a warning banner with one hint (the whole
  Board in the frame, more light), and *Take another Photo*, *Choose a Photo*, *Enter the Score
  yourself* (D6).
- **The flow:** empty → camera → *Reading the Photo…* → result → *Next Visit*, which opens the
  camera directly, so a Visit costs one tap. The previous result stays until a new Photo comes back,
  so a cancelled camera loses nothing. Controls sit in the bottom third. The tip ask stays on the
  empty state only.
- **TalkBack:** the Score is a heading and a polite live region (*Visit Score 81. Three Darts:
  treble 20, single 20, single 1. Dart 2 is unsure.*); *Reading the Photo…*, the *No Board found*
  banner and *No Darts found* are polite live regions too, so nothing that comes back waits for a
  swipe. The Photo is one node with that summary and its markers are not focusable; the chips are
  the focus targets, with *Remove Dart* as a custom action. Each chip's accessible name starts with
  its visible text (*1 · T20 · 60, treble 20, 60 points*, then *check* when unsure), so voice
  control's "tap T20" or "tap Check" finds it. The keypad is the path that needs no precise tap, for
  everyone, so there is no separate accessible mode.
- **Focus:** opening the sheet moves focus into it, and *Done* returns it to the Dart's chip; after
  *Remove Dart* it goes to the next chip, or to *Add a Dart* when none is left; a new result puts it
  on the Score heading, and no Board found on the banner.

`CONTEXT.md` gains **Miss** (a thrown Dart that scored 0; not *removed*) and **unsure** (a Dart
below the model's confidence of 0.5, shown with *Check*; not *low confidence* in the UI).

## 4. A Visit's life

| Moment | What happens |
| --- | --- |
| *Take a Photo* tapped | `TakePicture` into a `FileProvider` URI in `cacheDir`. No `CAMERA` permission (PLAN.md *Asks*). No camera app: the button says so and the Picker stays |
| *Pick a Photo* tapped | The Photo Picker, one image. No permission on any API level |
| Photo arrives | Through `MediaFiles` as the `photos` kind, the camera's file deleted; then both passes off the main thread |
| No Board found | §3's: the whole Photo with no markers, the banner with its hint (the whole Board in the frame, more light), and *Take another Photo*, *Choose a Photo*, *Enter the Score yourself* (D6). Nothing is counted |
| Board found | §3's result. The first time a Photo's result is shown, `incrementVisitsScored()` is called once for it, so the last Visit of a session counts too. A Visit entered by hand (D6) counts once, when its first Dart is committed (*What moved while building C*) |
| *Next Visit* | The camera opens directly and the result stays on screen. When a new Photo arrives, the previous one is deleted; a cancelled camera changes nothing |
| Process death mid-Visit | The Photo's relative path survives in `SavedStateHandle`, and the last counted Photo's path is in DataStore; the result is recomputed from it and not counted again, and the start-up sweep (D2) skips that path. Corrections made before the death are lost, and that is accepted (Known gaps) |
| The start-up sweep | Runs when the Visit ViewModel is created, not in `Application.onCreate`: only the ViewModel's `SavedStateHandle` knows which Photo survived process death, so only it can tell a leftover from the Photo on screen |

### What moved while building B (2026-11-20)

- ***Enter the Score yourself* is not in B.** It opens C's keypad with no Darts, and B has no keypad,
  so the button would do nothing. No Board found shows *Take another Photo* and *Choose a Photo*; C
  adds the third button with its sheet, as `DOD.md` already says.
- **The chips are not buttons yet.** They are TalkBack's focus targets with the names §3 gives them,
  but a tap does nothing until C opens the sheet from them, so B does not make them clickable.
- **No camera app is found by launching, not by asking first.** `TakePicture` throws
  `ActivityNotFoundException`, and the banner (*No camera app*) appears above the result, which stays.
  A pre-check would need a `<queries>` entry for `IMAGE_CAPTURE`; launching needs none.
- **The sweep clears the camera's files too.** A camera file in `cacheDir/camera/` left by a death
  between the camera returning and `MediaFiles` writing the Photo is deleted, except the one the camera
  is still writing, whose Uri `SavedStateHandle` holds while the camera is open. A Photo arriving waits
  for the sweep, so a new file is never taken for a leftover, and the sweep reads the handle when the
  ViewModel is created, before a camera result can clear it.
- **The last counted Photo is kept in DataStore, in the same edit as the count,** so no process death,
  even one after `onStop` saved the handle, can count a Visit twice or lose one.
- **The crop** is the window the second pass read the Darts in (the outer double ring's extent over
  `Warp.CROP_FILL`), clamped to the Photo, and at most two fifths of the window high, so the Score and
  the chips stay on screen beside it.
- **Focus on a new result waits for the window and 600 ms.** A result arrives while the Picker or the
  camera still holds the window, and TalkBack puts its own focus on the first node when the window comes
  back; a request made before that is lost. Read on `pixel-api36` with TalkBack on: focus lands on the
  Score heading, and on the banner when no Board is found.
- **A marker's number grows with the font scale up to 1.3** and no further, so at 2.0 its badge does
  not cover the Darts; the ring stays 23 dp, and the chips carry the Score at full size.
- **The debug build's timing line** R2 and R4 read is `PhotoReader: both passes: <n> ms at <t>
  threads`, from `scoring/ReadTiming.kt` in `src/debug/` with a no-op in `src/release/`.
- **R2's count is picked in the debug build**, in Settings' Debug section (1, 2, 4 or 6), so one
  install reads every count. The next Photo builds a new interpreter at that count; a release build
  always reads at `LiteRtModel.DEFAULT_THREADS` (`scoring/ReadThreads.kt`, one per variant).
- **`scripts/edge-to-edge.py`'s scenes are unchanged.** The empty state is still `visit`; a result
  needs a Photo picked through the Picker, which the driver cannot seed.

### What moved while building C (2026-11-20)

- **A Visit entered by hand counts toward the tip's Visit count**, once, when its first Dart is
  committed; §4 said it would not. ADR-0007's count measures use, and a player who scores a Visit on
  the keypad after a bad Photo has used the app as much as one whose Photo was read. It goes through
  the same `incrementVisitsScored(photo)` with the No Board Photo's path, so committing more Darts,
  re-entering after process death, or a later Photo cannot count it twice.
- **A Dart keeps its number through corrections.** The top-to-bottom rule numbers the model's Darts
  when a result arrives; a corrected marker that moves does not renumber them, and a new Dart takes
  the lowest free number, so a chip never changes under the player's finger.
- **The corrected marker** has no ring, only its badge centred on its place, in `inverseSurface` with
  an `inverseOnSurface` number (a corrected Dart is never unsure). No ring means the player set the
  Score; it sits on a bed's centre, not a tip, so it hides nothing, and it is kept inside the crop.
  **A Miss has no bed, so it keeps its place**: a Dart set to Miss stays where it was, and one added
  by a tap sits at the tap, both as a badge (2026-11-20; until then a Miss set by hand lost its
  marker while a measured one kept it). A Dart with no place, a Miss from *Add a Dart*, a filled Miss
  or a Visit entered by hand, has no marker. **A dragged Dart keeps a ring** (2026-11-20): the player put its
  point on the Entry point, so it is drawn as a solid ring there with its badge beside it, in
  `inverseSurface` with an `inverseOnSurface` number. A keypad commit after a drag deliberately
  clears that and draws the badge alone at the new bed's centre, like any keypad change.
- **Which bed's centre:** a single goes to the one of its segment's two single beds nearer where the
  Dart was or the tap landed, and to the outer one from *Add a Dart*; an outer bull keeps that point's
  direction. *Done* on an unchanged Score confirms the Dart where it was measured: it is not moved
  and keeps its ring.
- **The keypad's two picks.** While a Bull or *Miss* is picked the ring row shows nothing selected; a
  ring tapped then waits for a number (*Pick a number*, *Done* disabled), and a number tapped then is
  a single. *Add a Dart* opens with Single and no number.
- **The keypad at large text.** No key label is cut to one line; when a ring's name would wrap
  inside the segmented row (Polish *Pojedyncze* at 200%), the row stacks as three full-width keys.
  TalkBack reads each group's name with its keys (*5, radio button, in list Number*); the visible
  labels are hidden from it so they are not read twice. Unselected keys are outlined in `outline`.
- **A tap on the Photo** on a marker's badge, or within 24 dp of its point, opens that Dart, at any
  zoom, and a long press there drags its ring (§3, *Moving a Dart's ring*); anywhere else, held or
  not, proposes a new one while fewer than three are shown or a filled Miss remains to take over,
  *Miss* when it lands off the Board.
- ***Undo* is a snackbar with no timer** (WCAG 2.2.1: nothing to adjust): it stays until *Undo*, its
  dismiss button, or the Visit's next change (a commit, another removal, a new Photo). The screen
  leaves room for it at the end of its scroll, so it never hides *Next Visit* for good. *Undo* puts
  the Dart back with its number unless a new Dart has taken it.
- **Focus.** After *Remove Dart* it goes to the next chip in order, else *Add a Dart*; closing the
  sheet without *Done* returns it to the Dart's chip, or to *Add a Dart* for a new one (with three
  shown, where it is hidden, to the filled Miss a tap would have taken), or to *Enter the Score
  yourself* on *No Board found*. Those three are made focusable in touch mode, since a
  button is not, and focus could not be moved back to them otherwise. The sheet's drag handle is drawn without its semantics: as the sheet's first
  node it took TalkBack's focus on opening, where §3 puts it on the title. Read on `pixel-api36` with
  TalkBack on: into the sheet on *Dart 1*, back to its chip on *Done*.
- **A Visit entered by hand** replaces the *No Board found* banner with the Score, *Entered by hand*
  under it, the whole Photo and *Next Visit*. Removing every Dart again stays there at 0 with *Add a
  Dart*; a keypad closed without *Done* leaves *No Board found* as it was.
- ***Add a Dart*** is a borderless button at the end of the chip row: filled is a Dart, outlined is
  unsure, no container is an action.
- **Landscape (QA's B follow-up).** A window under 480 dp high puts the Photo beside the Score at the
  full height left, at most half the window wide, and scrolls the Score, the chips and the buttons
  beside it; the keypad sheet splits into two panes. In the same short window the shell's tabs move
  to a navigation rail and the Visit result drops its title, so the Photo gets the window's height
  less the system bars (2026-11-20; until then a top bar and a bottom bar left it about 210 dp on
  `pixel-api36`). `ui/common/Windows.kt` holds the one 480 dp breakpoint all three read.
- **Corrections are still lost on process death** (Known gaps). Keeping them in `SavedStateHandle`
  means a saveable Visit replayed onto the recomputed reading, which is not trivial, so they stay in
  the ViewModel's state alone.
- **The debug build keeps each marked Visit** (2026-11-20), so the owner's corrections become labels
  for checking the model and for training later. A Visit with a result (a Board found, or Darts
  entered by hand) is kept each time the Visit screen stops, which every close, trip to the camera,
  move to the background and kill passes through, and again when a new Photo ends it, before its
  Photo is deleted. The Photo is copied byte for byte into `filesDir/marked/<photo-uuid>.jpg`, beside
  `<photo-uuid>.json` with the time it was kept, the app's version, the Photo's size, the homography
  and crop, each Dart's reading (`read`, in Photo pixels, null for one added by hand) and its final
  place, Score and flags, and the Darts read that the player removed. Each is written aside and
  renamed, so a later keep of the same Visit replaces the earlier snapshot whole.
  `ui/visit/KeepMarked.kt`, one per variant: a release build keeps nothing. `marked/` is outside Auto
  Backup's include list (ADR-0005), and Settings' Debug section counts the Visits kept.
  `uv run --directory ml darts-ml pull-marked --serial <serial>` copies them into
  `$DARTS_DATA/phone-captures/<date>/` over `adb run-as`, again for a record whose size or time
  changed on the phone (into the folder its first copy went to), and deletes on the phone only with
  `--delete-after`. Corrections made after the last stop and lost to a process death are not kept.

## 5. `minSdk`

Phase 0 left it here (`phase-0.md`, `DOD.md`): decided before the door, on the runtime's own floor
and an inference time on a low-end emulator image. The runtime's floor is no constraint: LiteRT
1.4.2's AAR declares `minSdkVersion` 21, below today's 26. So the question is speed alone, read as
R4: both passes on an API 26 emulator image with 2 GB of RAM and 2 cores, at the thread count R2
chose.

1. **Under 2 s per Photo** → `minSdk` stays 26, and the reason is written beside it in
   `app/build.gradle.kts`.
2. **2 s or more** → the floor rises to the lowest level whose image reads under 2 s, CI's floor
   legs move with it in the same commit, and the reason is written beside it.

An emulator's CPU is not a 2018 phone's, so this bounds the decision rather than proving it; the
direction is still asymmetric, and lowering later is free.

### The verdict, taken 2026-11-20: 1, under 2 s → `minSdk` stays 26

R4 read both passes at about 0.36 s a Photo on `urgent-api26` held to 2 GB and 2 cores, a fifth of
the bound, at 4 threads and at 2 alike (Readings). R2 has not been read yet, so the verdict holds
for an R2 choice of 2 or 4 threads: on two cores, 4 buys nothing over 2, and neither is near 2 s.
If R2 picks 1 or 6, R4 is read again at that count, since 6 oversubscribes two cores.

- **The worst Photo is the first.** The reader is created lazily inside the timed region, so the
  first Photo after a start carries the interpreter's creation, 65 to 90 ms more on this image.
- **2 threads was a local build,** `DEFAULT_THREADS` set to 2 and not committed: the count is a
  constant, and nothing in the debug seam sets it.
- **API 26's DocumentsUI crashed once** in 20 picks (`removeContentProvider: … not a
  ContentProviderConnection`, in the system's process) and took the app's activity with it, its
  Visit unsaved; the app's process lived and the next picks read normally. A platform bug of that
  image, not ours; noted in case a real API 26 phone shows it.

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
- **`CONTEXT.md`:** Miss and unsure (§3), Bed (C).
- **`PLAN.md`'s phase 1 paragraph:** the tap picks, the keypad sets (D3).
- **`DOD.md`:** a Phase 1 section with A–E; the `minSdk` and runtime items under *Before the first
  upload* point here.
- **`PLAN.md`:** phase 3 loses the DeepDarts attribution; phase 1 is ticked at E.
- **Privacy policy, Data safety:** no change. Both already say the Photos are processed on the phone
  and never sent; this phase makes that true rather than promised. Re-read at B, not edited.
- **`docs/store-listing.md`:** nothing until phase N.

## Known gaps, deliberately

- **Corrections are lost on process death.** Keeping them means storing a Visit, which D2 defers.
  The Photo itself is recomputed, so the cost is a few taps.
- **The model before E misreads about one Visit in three.** That is what correcting is for, and why
  no build reaches a track anyone but the owner sees before E (D5).

## Readings

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | A's gate: Board and Darts against Python's `locate()` on DeepDarts' val Photos, after `MediaFiles` | `darts-ml phone-parity`, which runs the instrumented test | **2026-11-20**, 200 val Photos, run `2026-11-19-darts-640-s2-ring-ext`, on `pixel-api36` and `urgent-api26`: Board found by both in 200 of 200 on each; worst crossing 0.00513 mm against the 0.1 mm bound; kept Darts' Scores the same in 200 of 200. Verdict 1 (§1) |
| R2 | Time per Photo, both passes, at 1, 2, 4 and 6 threads, on the owner's phone | the debug build's timing line in `logcat`, each count picked in Settings' Debug section | |
| R3 | Real Visits on a real Board in room light: exactly right, corrected, and taps per correction | by hand, at the Board | |
| R4 | Both passes on a low-end API 26 emulator image (2 GB, 2 cores), at R2's thread count | the debug build's timing line in `logcat`, on `emulator -avd urgent-api26 -memory 2048 -cores 2 -no-window -no-audio -no-snapshot-save`, 10 val Photos (every 107th in the split's order) through the Picker | **2026-11-20**, R2 not yet read, so at 4 threads (today's `DEFAULT_THREADS`) and 2: median 360 ms and worst 450 ms at 4, median 364 ms and worst 429 ms at 2; the worst both times the first Photo, with the interpreter's creation (warm worst 377 and 372 ms). Under 2 s: `minSdk` stays 26 (§5) |
| R5 | A's second question: the exactly-right share on DeepDarts' val Photos as they are and as `MediaFiles` stores them (D2) | `darts-ml deepdarts score --split val`, then the same with `--as-stored` | **2026-11-20**, run `2026-11-19-darts-640-s2-ring-ext`, `ENTRY_THRESHOLD` 0.25, all 1,070 val Photos: 740 (69.2%) as they are, 735 (68.7%) re-encoded at q85, 0.5 points down against the 1-point bound. D2 holds (§1) |
