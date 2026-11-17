# Phase M2 — A model trained here finds the Board and the Darts in a handheld Photo, and the bar for phase 1 is read on the Held-out set

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
serves [ADR-0008](adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md) and
settles the two things it left to M2 "by measurement": the training framework and the on-device
runtime. That is one dated amendment, at E. [`CONTEXT.md`](../CONTEXT.md) is owed one term at B,
**Validation sessions**, because the training code names it and it must never be confused with the
Held-out set.

**What closing this phase means.** Today `ml/` prepares data and nothing learns from it: DeepDarts'
16,050 Photos are converted (phase-M1.md R2), the owner's Capture sessions are being taken, and the
bar is code (`darts-ml evaluate`). After this phase, `ml/` trains one keypoint model that finds the
80 Calibration points and every Entry point in a Photo, exports it to a file a phone can run, and
writes its predictions in the format `evaluate` reads. The difference a reader can check:
**`darts-ml evaluate --predictions <the final model's file>` exits 0 on the frozen Held-out set**,
or, if it does not, the phase closes with the figures it reached and the decision that follows
(§7). Phase 1 opens only on the first.

**`PLAN.md`'s paragraph holds, with two additions said here first.** It says the Board comes first
and the Darts second; that is checkpoints C and D. It does not say that most of M2 can run before
M1's Photos exist: everything up to E trains and measures on DeepDarts alone, which holds none of the
owner's Photos and so cannot leak the Held-out set or flatter the bar. Only F and G wait for M1.
And it does not say how often the bar may be read; §7 limits that, because a bar read after every
change is a bar being fitted to.

---

## Decisions for the owner

All six were decided on **2026-11-17**, each as recommended. A–E need D1–D5; F and G need D6.
None of them moves the bar, which M1 fixed on 2026-11-13.

| # | Decision | Decided 2026-11-17 |
| --- | --- | --- |
| **D1** | **The model, and the code that trains it** (§2) | **A heatmap keypoint model written here in PyTorch** (BSD-3-Clause): a small convolutional backbone from torchvision (BSD-3-Clause), 80 heatmap channels for the Calibration points and one for Entry points, with a sub-pixel offset. About 300 lines we own, three dependencies, and an export path every runtime takes. The alternative is DeepDarts' own method, keypoints as tiny boxes, through a permissive detector (YOLOX, Apache-2.0, or `MultimediaTechLab/YOLO`, MIT): proven on this data, but a larger codebase to vendor and a box head that has to be bent into a point. RTMPose is the wrong shape: it wants one box per object first |
| **D2** | **Where the weights start** (§2) | **From scratch.** ImageNet-pretrained backbones learn faster, but their weights come from a dataset whose terms are research-only, and the app is public with a Tip. DeepDarts gives 12,830 training Photos of one narrow subject, which is a reasonable amount to start from nothing. If C misses its reading by a wide margin, this comes back to you with the licence question written out, before any pretrained weight is downloaded |
| **D3** | **Where training runs** (§1) | **On this machine.** Its Radeon 8050S (gfx1151, 16 GiB carve-out plus shared memory) through PyTorch's ROCm build if the gate (A) shows it works, its 24 CPU cores if not. A rented cloud GPU only for DeepDarts-only runs, and only if both local routes are too slow. **The owner's Photos never go to a cloud machine**: M1's D4 already rules out a cloud drive for them, and a rented GPU is the same thing with a bill |
| **D4** | **The on-device runtime** (§5) | **LiteRT tried first, ONNX Runtime second**, chosen by E's readings (size, parity with PyTorch, latency on the emulator). Both are bundled in the app, not taken from Play services (ADR-0008). ncnn stays a fallback: fastest on CPU, but a C++ build to own |
| **D5** | **The Validation sessions** (§3) | **s05 (phone 2, evening) and s09 (phone 1, day)**: one per phone, from the training rows, chosen now and high enough in M1's table that no shortfall drops them. Models are compared on these and on DeepDarts' own val split, never on the Held-out set. They cost a sixth of the owner's training Photos, about 90 |
| **D6** | **How often the bar may be read** (§7) | **At most three times**, each on a model the Validation sessions already say is ready, each recorded with its date, commit and weights hash. A third miss stops the phase and comes back to you; it is not a fourth try |

---

## 0. What this phase inherits

- **The records.** `darts-ml build` writes the owner's reviewed training Photos to
  `build/records.jsonl` and refuses every held-out one; `darts-ml deepdarts convert` writes
  DeepDarts' to `deepdarts/records.jsonl`, each with DeepDarts' own `split`. Both are phase-M1.md
  §4's common record: pixels and names, no framework's format. M2 reads only these two files. It
  never reads a label, a sheet or the pickle.
- **The bar, as code.** `darts-ml evaluate --predictions FILE` reads the Held-out set from the frozen
  manifest and the predictions file in `ml/README.md`'s format. M2's job ends in writing that file;
  it adds nothing to `evaluate`.
- **DeepDarts' 76 projected points.** Each DeepDarts Photo has four clicked points; the other 76
  crossings are projected through a four-point fit, which has no redundancy (phase-M1.md §4). M1 left
  whether to train on them to M2. §3 decides.
- **The asymmetry that shapes the phase:** DeepDarts is 16,050 Photos, nearly all face-on from a
  fixed mount, and is here today; the owner's Photos are about 540 handheld training Photos and are
  weeks away. So the code, the toolchain and the board-finding are proven on DeepDarts first, and the
  owner's Photos are what teach the model the handheld case and what the bar is read on.

## What is in, and what is deliberately not

**In:** the training code in `ml/`; the gate on where it runs; the Board, then the Darts, trained and
measured on DeepDarts; export to the runtime D4 picks, with its size and parity read; training on
DeepDarts plus the owner's training Capture sessions; the bar read on the Held-out set within D6's
budget; the ADR amendment.

**Not in, and each with a reason rather than a phase:**

- **Anything on the phone.** The app loading the model, the camera ask and the tap-to-correct are
  phase 1. E measures latency on an emulator only to choose the runtime; phase 1 takes the device
  readings and sets `minSdk` on them.
- **Merging several Angles.** `evaluate` already reads B2 on all three Photos merged, beside the bar;
  using the merge to decide anything is phase 2.
- **Synthetic renders.** M1 left them out; they come back only if F misses B2 and the misses are the
  hard cases renders could cover, and then as a decision for the owner.
- **A model per job.** One network finds both kinds of point (ADR-0008). Two networks would double
  the app's model size and its latency to buy nothing the gate has shown is needed.
- **Hyper-parameter search against the Held-out set.** The Held-out set is read under D6's budget
  only. Every comparison between runs is made on the Validation sessions and on DeepDarts' val split.

**The tempting one: ImageNet-pretrained weights.** One line of torchvision, and the first numbers
would come faster. It is out because the licence question (D2) is real and unanswered, not because
it would not work. If a later session adds it back, it adds it as an answered D2, not as a default
argument.

---

## Checkpoints

| | Checkpoint | Who | Merges | Depends on |
| --- | --- | --- | --- | --- |
| **A** | **The gate**: does a training step run on this machine, and how fast | code | `chore(ml):` (the probe), `docs:` (the verdict) | D1, D3 |
| **B** | **The training code**: dataset from the records, model, loss, decode, the predictions writer, `darts-ml train` and `darts-ml predict`, tests | code | `chore(ml):` | A |
| **C** | **The Board, on DeepDarts**: Calibration points only; the error in mm at the wires on DeepDarts' val and test splits | code + compute | `docs:` (readings) | B |
| **D** | **The Darts, on DeepDarts**: Entry points added; DeepDarts' D1 and D2 test splits scored beside the paper's 94.7% and 84.0% | code + compute | `docs:` (readings) | C |
| **E** | **Export**: the model in D4's runtime, its size, its parity with PyTorch, its latency on an emulator; ADR-0008 amended | code | `chore(ml):` + `docs(adr):` | D |
| **F** | **The owner's Photos**: trained on DeepDarts plus the owner's training Capture sessions, chosen on the Validation sessions | code + compute | `docs:` (readings) | E, and M1's G (the freeze) |
| **G** | **The bar**: `evaluate` on the Held-out set, within D6's budget | code | `docs:` (the verdict) | F |
| **H** | **Close**: readings, `PLAN.md` and `DOD.md` ticked, phase 1's inputs (model size, runtime, latency) handed over | code | `docs:` | all |

**No checkpoint cuts a release.** `chore:` and `docs:` bump nothing, and no app code changes.

**Why A first.** Every later checkpoint is training runs, and how long a run takes decides how many
the phase can afford. If this machine cannot train in reasonable time, that is D3 again before any
model code is written for it.

**Why C before D.** `PLAN.md` says so, and the reason is mechanical: an Entry point is scored through
the homography the Calibration points give. A model that cannot place the Board produces Dart errors
that are Board errors in disguise.

**Why E before F.** The runtime's limits (supported operations, input size, quantisation) can force a
change to the model. Finding that after the owner's Photos are in would mean training on them twice.

**Why F waits for M1's G, not just M1's data.** Training must never see a held-out Photo, and
`darts-ml build` refuses them only once the manifest is frozen. F trains on `build/records.jsonl`,
which `build` will not write before then.

**Why G is its own checkpoint.** It is a reading, cheap in compute and expensive in budget (D6). In
one PR with F, the temptation is to read the bar after every training change.

---

## 1. The gate: can this machine train the model at a usable speed?

### The question, in the form that can be measured

On this machine (AMD Ryzen AI Max PRO 390, Radeon 8050S, 24 cores, 45 GiB), with the D1 model at the
input size §2 settles on: **how many seconds does one epoch over DeepDarts' 12,830 training Photos
take**, on the GPU through PyTorch's ROCm build and on the CPU alone? And does the GPU run give the
same loss curve as the CPU over the first 200 steps, so it is the same computation and not a silently
different one?

### The apparatus

`darts-ml train --probe`: 200 steps on DeepDarts' training split, the real model and loss, reporting
the device, images per second and the projected epoch time. Run once with the ROCm build of PyTorch
and once on the CPU. PyTorch's ROCm wheels carry the ROCm user-space libraries themselves; the kernel
driver (`amdgpu`, `/dev/kfd`) is already there. Whether the official wheels support gfx1151 is the
question, not an assumption.

### The verdicts, decided now rather than argued about later

1. **ROCm runs and an epoch takes ≤ 15 minutes** → train on the GPU. A 30-epoch run is an evening.
2. **ROCm fails, or is slower, and the CPU takes ≤ 60 minutes an epoch** → train on the CPU, overnight
   runs, and C and D get fewer, longer runs. D2's from-scratch choice is the one most hurt; say so in
   the verdict.
3. **Both are slower** → D3 comes back to you: a rented GPU for DeepDarts-only runs (A–E), and F
   on this machine regardless, since the owner's Photos stay here.

A GPU run whose first 200 losses differ from the CPU's by more than ordinary floating-point noise
counts as failing, whatever its speed.

### The verdict, taken *(date)*

*(Which one, the reading behind it.)*

## 2. The model

**One network, two kinds of point** (ADR-0008). A convolutional backbone (torchvision's MobileNetV3
or EfficientNet family: settled in B on A's speed reading) feeds a small upsampling head that outputs,
at a quarter of the input resolution:

- **81 heatmaps**: one per Calibration point, by name, and one shared by all Entry points, since a
  Photo holds any number of Darts and they have no order;
- **2 offset channels**: the sub-pixel distance from each heatmap cell to the true point, so a point is
  not rounded to a 4-pixel grid.

**Decoding.** A Calibration point is the peak of its channel, if the peak clears a threshold; an
Entry point is every local maximum of its channel above a threshold. The offsets refine each. The
Calibration points then go through RANSAC to a homography (ADR-0008), and the predictions file
carries the inliers only, as `ml/README.md` asks.

**Why heatmaps, not boxes.** A point is what is labelled, what the homography takes and what is
scored. A heatmap predicts a point directly, handles any number of Darts in one channel, and its
uncertainty shows as a spread peak, which is the `low_confidence` flag ADR-0008's triggers want. A
box detector predicts a box and reads its centre, and DeepDarts' method needed tuning for tiny boxes
that a heatmap does not.

**Two passes per Photo.** An owner's Photo is up to 4000 pixels across with the Board in part of it,
and B1's bar (median ≤ 0.5 mm) is about one pixel at DeepDarts' 800-pixel crops. One pass at a size a
phone can afford cannot do both, so the same network runs twice: once on the whole Photo, scaled
down, to find the Board; then on a square crop around it at full detail, which gives the points that
are kept. DeepDarts' Photos are already crops, which is why C and D can train the second pass first.
Training samples both: whole Photos scaled down, and crops jittered in position and scale.

**The input size** is settled in B by A's speed reading and C's first run, starting from 512 pixels for
the crop pass. It is a trade between the bar and the phone's latency, so E reads it again.

**From scratch** (D2). Weights start random; nothing pretrained is downloaded.

## 3. The data the model sees

| Source | Used for | Count |
| --- | --- | --- |
| DeepDarts `train` | training, from B | 12,830 |
| DeepDarts `val` | choosing between runs in C and D | 1,070 |
| DeepDarts `test` | C's and D's readings only, beside the paper | 2,150 |
| The owner's training Capture sessions, less the Validation sessions | training, from F | about 450 |
| The Validation sessions (D5) | choosing between runs in F | about 90 |
| The Held-out set | the bar only, under D6 | about 270 |

The dataset code reads `deepdarts/records.jsonl` and `build/records.jsonl`, and refuses three things
by itself, whatever it is asked: a DeepDarts record whose `split` is `test` in any training or
validation set, an owner record from a held-out Capture session (read from the frozen manifest, as
`build` does), and a Validation session in the training set. That is a second fence behind `build`'s,
because a training loader is exactly the place one gets added back by a flag.

**DeepDarts' projected points are trained on, at a lower weight.** The four clicked points carry full
weight. The 76 projected through them are right only as far as four clicks are, and wrong by the
same warp on every point of a Photo when one click is off. Training on all 80 teaches the model the
inner wires DeepDarts never clicked; weighting them at half lets the clicked points win where they
disagree. C reads whether that holds: its error at the treble wires, where only projected labels
exist, against its error at the double wires.

**DeepDarts' four are on the outer edge of the double wire, at 170.0 mm**, not on this repo's crossing
centres at 169.25 mm (phase-M1.md §4). The record keeps them there; the training target for those
four channels is moved to the crossing centre through the record's own homography, so the model
learns one definition of a Calibration point, not two.

**Augmentation** follows what a handheld phone does and DeepDarts' fixed mount does not: rotation of
the whole Photo, perspective warps up to the Angles of M1's protocol, scale, blur, brightness and
colour. A rotation or warp moves the labels with it. Flips are not used: a mirrored Board has its
numbers the wrong way round, and the model would learn a Board that does not exist.

## 4. Training and choosing a model

`darts-ml train` writes each run to `$DARTS_DATA/runs/<date>-<name>/`: the config, the loss per step,
the validation figures per epoch, and the weights. Weights never enter git (ADR-0008). A run is chosen
by its validation figures: on DeepDarts' val split in C and D, on the Validation sessions in F, using
the same B1 and B2 figures `evaluate` computes, so the number that chooses is the number that is
judged.

`darts-ml predict --run <run> --photos held-out` writes the predictions file `evaluate` reads. It is
the only way a model's output reaches the Held-out set, and it records in the file which run made it.

## 5. Export and the runtime

E converts the chosen model to D4's runtime and reads, per runtime tried:

- **size** of the model file, and of the runtime library per ABI, since both ship in the app;
- **parity**: the exported model's points against PyTorch's on the 1,070 DeepDarts val Photos, in mm
  after the homography. A runtime that moves a point by more than 0.05 mm is changing the model;
- **latency** of both passes on an emulator image (phase 1 repeats this on a low-end image and on the
  phone, and sets `minSdk` from it);
- **which operations failed to convert**, if any, and what replaced them.

The ADR-0008 amendment records the runtime picked and these figures.

## 6. The owner's Photos (F)

The model from E is trained further on DeepDarts' training split plus the owner's training Capture
sessions, sampled so the owner's Photos make up about half of each batch despite being a twentieth of
the data: they are the handheld case the bar is about. Runs are compared on the Validation sessions'
B1 and B2. When one is ready, G reads the bar.

## 7. The bar (G)

The bar is phase-M1.md §7, unchanged, read by `evaluate` on the frozen Held-out set. D6 limits it to
three readings in this phase.

- **Before each reading**: the run is chosen on the Validation sessions alone; `verify-held-out`
  passes; the commit and the weights' SHA-256 are written into the readings below *before* `evaluate`
  runs.
- **Met** → phase 1 opens with that model.
- **Missed** → the figures beside the bar (phase-M1.md §7) say where: Board or Darts, which wires,
  which hard cases. The next run changes something the Validation sessions can show helped. A third
  miss stops the phase and goes to the owner with those figures and the options: more training
  Capture sessions, D2 reopened, synthetic renders, or the bar's evidence weighed again. The bar is
  not moved to meet a model.

---

## Tests

`PLAN.md` rule 3's second clause. M2 has no device behaviour; its safety values are the ones that
keep the Held-out set unseen and the bar honest:

- **`TrainingDataTest`** checks that the dataset refuses a DeepDarts `test` record, an owner record of
  a frozen held-out Capture session (by name and by hash, as `HeldOutTest` does for `build`), and a
  Validation session in training. It fails towards a model that has seen what it is judged on.
- **`DecodeTest`** renders heatmaps from known points and checks that decoding returns them within
  0.05 pixels, finds every Entry point in a channel holding three, and returns nothing for a channel
  below the threshold. It fails towards points the model never found.
- **`PredictTest`** checks that the predictions file built from the labels themselves reads 100%
  found and 0 mm through `evaluate`, and that the file names the run that made it. It fails towards
  a predictions writer that loses or invents points between the model and the bar.
- **`AugmentTest`** checks that a rotated and warped sample's labels land on the same Board positions
  as before, and that no flip is ever applied. It fails towards labels that no longer mark what the
  pixels show.

## Documents this phase amends

| Document | Change | At |
| --- | --- | --- |
| ADR-0008 | dated amendment: the model (D1), the runtime and its readings (D4, §5), where the weights start (D2) | E |
| `CONTEXT.md` | **Validation sessions**: the training Capture sessions set aside to choose between models, never the Held-out set | B |
| `ml/README.md` | `train`, `predict`, the runs folder; PyTorch and torchvision, and every library the ROCm wheel bundles, in the licence table | A, B |
| `CLAUDE.md` | the `train` and `predict` commands | B |
| `PLAN.md`, `DOD.md` | M2 ticked; phase 1's `minSdk` item gets E's latency and size | H |

Not amended: the privacy policy, the listing and `play-app-content.md`. No app code changes in this
phase; phase 1, which ships the model, owes the DeepDarts credit on the licences screen.

## Known gaps, deliberately

- **DeepDarts is face-on.** Nearly all of it is from a fixed mount. It teaches the Board and the Darts;
  only the owner's 450 or so training Photos teach the Angles players stand at. If F misses at steep
  Angles, more training Capture sessions are the fix, at about 2 owner hours each.
- **The projected labels.** Training on DeepDarts' 76 projected points teaches whatever error four
  clicks carry. C's reading measures it; the owner's labels, clicked or checked at every crossing,
  correct it in F.
- **From scratch is slower to learn.** D2 trades accuracy, possibly, for a licence that is clean. C
  shows the cost.
- **One Board.** As in M1: the Held-out set measures new Capture sessions, not new homes.
- **The emulator is not a phone.** E's latency chooses a runtime; it is not the app's speed. Phase 1
  reads that.

## Readings

`PLAN.md` rule 3. M2 changes no app, so its readings are taken off the training runs and the tools,
with the command that took them. Each training reading names its run folder.

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | **The gate.** Epoch time on the GPU (ROCm) and on the CPU; the first 200 losses compared | `darts-ml train --probe` under each build | *(A)* |
| R2 | The Board on DeepDarts: found share, and median / 95th percentile error at the treble and double wires, on val and on test | `darts-ml evaluate`-style figures on DeepDarts, from the chosen C run | *(C)* |
| R3 | The Darts on DeepDarts: share of D1 test and of D2 test Photos scored right, the paper's way (total), beside 94.7% and 84.0%; and Dart by Dart | the chosen D run | *(D)* |
| R4 | Export, per runtime tried: model size, runtime size per ABI, parity in mm over 1,070 val Photos, emulator latency of both passes, operations that failed | `darts-ml export` and its report | *(E)* |
| R5 | The owner's Photos: B1 and B2 on the Validation sessions for the chosen F run | the chosen F run | *(F)* |
| R6 | **The bar**, each reading: date, commit, weights SHA-256, then every row of `evaluate` | `darts-ml evaluate --predictions <file>` | *(G)* |
