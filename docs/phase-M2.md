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

**`PLAN.md`'s paragraph holds, with three additions said here first.** It says the Board comes first
and the Darts second; that is checkpoints C and D. It says the Board is found "from a handheld
photo", but C first finds it on DeepDarts' fixed-mount crops, because those are here today; the
handheld reading arrives with the owner's Photos in F. It does not say that most of M2 can run before
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
| **D5** | **The Validation sessions** (§3) | **s09 (phone 1, day) and s14 (phone 2, evening)**: one per phone, from the training rows, chosen now. While all 12 training rows are taken, each is the second row of its phone and light, so holding it out leaves every light trained: phone 1's day keeps s01 and s16, phone 2's evening keeps s05. M1's shortfall rule can drop either; §3 says what happens then. Models are compared on these and on DeepDarts' own val split, never on the Held-out set. They cost a sixth of the owner's training Photos, about 90 |
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
| **D** | **The Darts, on DeepDarts**: Entry points added; DeepDarts' face-on (`d1_`) and angled (`d2_`) test folders scored beside the paper's 94.7% and 84.0% | code + compute | `docs:` (readings) | C |
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

Every outcome lands in exactly one of these. A device *works* when it runs the probe, its build of
PyTorch is allowed by ADR-0008's licence rule, and, for the GPU, it passes the parity check below.

1. **ROCm works and its epoch takes ≤ 15 minutes** → train on the GPU. A 30-epoch run is an evening.
2. **Otherwise, the faster device that works takes ≤ 60 minutes an epoch** → train on it, with
   fewer, longer runs for C and D. The verdict says that D2's from-scratch choice is the one most
   hurt.
3. **Otherwise** (no device works, or the faster one that does takes more than 60 minutes an epoch) → D3 comes back
   to you: a rented GPU for DeepDarts-only runs (A–E), and F on this machine regardless, since the
   owner's Photos stay here.

**The parity check.** The two probe runs start from the same initial weights, built on the CPU under
one seed and then moved to the device; see the same batches in the same order, from a seeded loader
with no augmentation in the probe; and share the input size, batch size and optimiser. The GPU passes
when its mean loss over steps 151–200 is within 5% of the CPU's, and both curves fall: each run's
mean over steps 151–200 is below half its mean over steps 1–10. A GPU run that fails this counts as
not working, whatever its speed.

### The verdict, taken 2026-11-17: 1, train on the GPU

- **The GPU works.** PyTorch 2.14.1 with ROCm 7.14 runs on the Radeon 8050S (gfx1151) with nothing
  installed system-wide: the wheel carries ROCm, and the kernel driver was already there. **9.7
  minutes an epoch** at 512 pixels, batch 16 (22.0 Photos a second).
- **The CPU works too, at 20.9 minutes an epoch** (10.2 Photos a second), so verdict 2 was the
  fallback: the GPU buys a factor of two, not the phase.
- **Parity holds.** Mean loss over steps 151–200: 0.180 on the GPU, 0.183 on the CPU, 1.7% apart.
  Both fall from about 2.40 over steps 1–10. The first five losses agree to three decimals.
- **What neither verdict anticipated: the licence.** The ROCm runtime bundles SuiteSparse's
  `libcholmod` built with its Supernodal and Modify modules, which are GPL-2.0-or-later, not LGPL.
  Training loads it with the rest of the runtime and never calls it, and it never ships. ADR-0008's
  rule as worded ruled that wheel out; the owner amended the rule the same day to allow exactly this
  case (ADR-0008, 2026-11-17), so the GPU *works* in the sense above. Without that amendment the
  verdict would have been 2, on the CPU.
- MIOpen ships no tuned kernel database for gfx1151 and warns so; it picks kernels at run time. The
  9.7 minutes is with that, so tuning can only make it shorter.

## 2. The model

**One network, two kinds of point** (ADR-0008). A convolutional backbone (torchvision's MobileNetV3
or EfficientNet family: settled in B on A's speed reading) feeds a small upsampling head that outputs,
at a quarter of the input resolution:

- **81 heatmaps**: one per Calibration point, by name, and one shared by all Entry points, since a
  Photo holds any number of Darts and they have no order;
- **4 offset channels**: the sub-pixel distance from each heatmap cell to the true point, so a point is
  not rounded to a 4-pixel grid; two for Calibration points and two for Entry points, so a Dart
  landing in a crossing's cell does not overwrite the crossing's offset.

**Grouped Darts are the hard case for one Entry channel.** At 512 pixels on an 800-pixel crop a
heatmap cell is about 3.5 mm of Board. Two Entry points in one cell decode as one Dart, and two a
cell or two apart blur into one peak if the target Gaussian is wide; M1 captures grouped Visits on
purpose, so this is not rare. The Entry channel's target Gaussian is therefore half as wide as the
Calibration channels' (σ of 1 cell, not 2), and B reads on DeepDarts' val split the share of Dart
pairs closer than 10 mm that decode as two Darts. Below 95%, the Entry channel moves to a stride-2
output before C trains anything on it.

**Read at B, 2026-11-17: the Entry channel stays at stride 4.** Decoded from the training targets
themselves, at 512 pixels through the second pass's framing, the pairs closer than 10 mm come back as
two Darts in **27 of 27** on DeepDarts' val split and **348 of 353 (98.6%)** on its train split
(`darts-ml deepdarts grouped`). Val holds too few close pairs to judge alone, so train, which nothing
is chosen on here, is read beside it. This is the encoding's own limit, what a model reproducing its
targets exactly would decode; a trained model blurs peaks further, so every epoch of `darts-ml train`
reads the same share on its own output, and C reads it again.

**After D, 2026-11-18: the Entry channel moves to stride 2, and false tips near a real one cost
more.** D (`2026-11-18-darts-512`) got 91% of Darts right but found only 5 of 27 val pairs under
10 mm as two, while its own targets decode 27 of 27: the limit is the model, not the encoding. Its
overlays put phantom Entry peaks on barrels and flights a few millimetres from real tips. Two
changes answer that, both switchable for an ablation (`ml/README.md`): the Entry heatmap and its
offsets come from a small stride-2 head, so a pair 6 mm apart is about four cells apart instead of
two, with the Calibration channels left at stride 4 as C trained them; and the Entry heatmap's
penalty for a false peak is five times higher in a ring 4 to 20 mm of Board around each labelled
Entry point, never on a neighbour's tip. The encoding limit at 640 pixels is unchanged by the
stride: 27 of 27 val pairs and 348 of 353 train pairs at stride 2 and at stride 4 alike; the
targets only part at stride 4 for pairs closer than about 3 mm.

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

**What B settled from A's speed reading, 2026-11-17.** The backbone is MobileNetV3-Large, as gate A
measured it. The speed-ups were each read with the probe and its parity check (512 px, 200 steps,
`runs/probes/`):

| Change | Photos/s | Epoch | Loss 151–200 against the CPU's 0.777 |
| --- | --- | --- | --- |
| none (float32) | 22.5 | 9.5 min | +0.8% |
| bfloat16 autocast (untuned; tuned, see below) | 23.6 | 9.0 min | +1.3% |
| channels-last | 22.5 | 9.5 min | +0.8% |
| both | 23.4 | 9.1 min | +1.3% |
| both, batch 32 | 22.9 | 9.3 min | — |
| **MIOpen's tuned kernels** (user database filled once under `MIOPEN_FIND_ENFORCE=SEARCH`) | **25.3** | **8.5 min** | −0.5% |

Every row passes parity and both curves fall. The GPU shares the laptop's memory, and MobileNet's
depthwise layers wait on memory rather than arithmetic, which is why halving the number width or
doubling the batch buys little. Only the tuned kernels are kept, as the
default: `train`, `predict` and `deepdarts score` point MIOpen at `$DARTS_DATA/miopen/`. Batch 32
runs at batch 16's speed, so 16 stays. The model is two passes at 512 pixels until C's first run
says otherwise.

**C keeps 512 pixels (read 2026-11-18, R2).** Its wire medians, 0.27 to 0.40 mm on val and test,
are a third to a half of an input pixel (about 0.875 mm at 512 pixels on an 800-pixel crop), and
inside B1's 0.5 mm. A larger input buys nothing C can measure; E reads the phone's side of the
trade.

**MIOpen cannot search for kernels once the laptop has slept (read 2026-11-18).** This paragraph
first said that bfloat16 does not run from a fresh start. The cause is wider and is not bfloat16:
after a suspend every kernel search fails, in float32 as well, and before one every search works.
MIOpen chooses a kernel for a shape it has not run before by timing each candidate. After a resume
the GPU's firmware restarts the clock it stamps each kernel launch with, while the kernel driver's
GPU clock, which the ROCm runtime uses to turn those stamps into times, keeps counting from boot.
The runtime then reads every launch as time zero, so MIOpen sees every candidate take no time
("Invalid elapsed time detected in EvaluateInvokers"), rejects them all and stops with
`miopenStatusUnknownError`. Read on the GPU after the 2026-11-18 07:25 resume: 600 of 600 timed
intervals came back zero or negative, the runtime's own log showed the raw stamps advancing and
every translated time as 0, and the two clocks stood 12.8 hours apart, the time from the boot to
that resume. Every search that worked was run on 2026-11-17 before the 22:12 suspend. Every one that
failed came after the resume: bfloat16 at batch 16, float32 at a batch of 6, and float32 at batch 16
itself against an empty database. With the driver's clock shifted by that offset as the runtime
reads it (a preload shim, for this reading only and not in the repository), searches for all three
succeeded in the same session. A shape already in the database needs no timing and runs in any
session, which is why training and the padded inference batches were never stopped. So a search (a
new input size, batch size or precision) is run after a restart, before the laptop sleeps, and
`darts-ml` says so when one fails. `MIOPEN_FIND_MODE=FAST`, which picks kernels without timing
them, runs in any session but slowly: bfloat16 under it read 14.3 Photos/s, with a loss that passes
parity (0.786 over steps 151–200, 1.2% above the CPU's 0.777;
`runs/probes/gpu-512-16-200steps-bf16-20261118-073643.json`).

**bfloat16, once tuned, reads 9% faster than float32, and `--bf16` stays a flag, off (read
2026-11-18).** Read in one session, alternating, at 512 px, batch 16 and 200 steps, each from a
trial copy of the database; `$DARTS_DATA/miopen/` was not written:

| Probe | Photos/s | Epoch | Loss 151–200 against the CPU's 0.777 |
| --- | --- | --- | --- |
| float32 on the tuned kernels (three readings) | 24.4 | 8.8 min | −0.5% |
| bfloat16 from 2026-11-17's untuned search (two readings) | 19.3–20.0 | 10.7–11.1 min | +1.3% |
| **bfloat16 tuned** (`MIOPEN_FIND_ENFORCE=SEARCH`, about 3.5 min once; two readings from the database it filled) | **26.6–26.7** | **8.0 min** | +0.8% |

The files are `runs/probes/gpu-512-16-200steps[-bf16]-20261118-2136…` to `-2207…`. Four of them ran
under the shim and are not in the table: the tuning run itself (`-215322`, 26.6 Photos/s) and one
repeat of each row (`-220031`, `-220250`, `-220752`).

MIOpen offers no Winograd kernel for bfloat16. By its own timings the convolutions of one batch
take 424 ms in float32 on the tuned kernels, 491 ms in bfloat16 untuned and 395 ms in bfloat16
tuned. The tuned gain is in the weight-gradient pass (198 ms against float32's 304); the
backward-data pass stays slower (139 against 61). The untuned bfloat16 and the float32 figures are
both lower than 2026-11-17's from the same database entries (23.6 and 25.3). The shimmed clock does
not bring them back (20.0 and 24.4), so the timer is not why, and neither has been read again on a
boot that has not slept. bfloat16's kernels also print 15 to 21 debugging lines per step to standard
output from inside the ROCm library, which nothing turns off.

`--bf16` stays off. No run has been trained in bfloat16, so what it costs in millimetres at the
wires is unread; 200 steps of loss parity say only that it learns. What it buys is 0.75 min an
epoch, about 22 min of a 30-epoch run. Turning it on for a run needs its tuned kernels in
`$DARTS_DATA/miopen/` first (one probe after a restart, `ml/README.md`) and a run in it read against
the same run in float32.

**From scratch** (D2). Weights start random; nothing pretrained is downloaded. C's reading clears
B1's median at both wires on val and test, so D2 does not come back to the owner.

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

**If hours run short in M1.** Its shortfall rule (phase-M1.md §3) runs first, unchanged, and can
drop a Validation session: from the bottom up it drops s18, s16 and s14, skips s13 and s11 as phone
1's only flash and phone 2's only harsh row, then drops s09. A dropped Validation session is not
replaced. If no Validation session survives for a phone, F compares runs by leaving one Capture
session out at a time over that phone's training sessions instead, and that stands in wherever this
document says "the Validation sessions". It costs compute, not owner hours.

**DeepDarts' projected points are trained on, at a lower weight.** The four clicked points carry full
weight. The 76 projected through them are right only as far as four clicks are, and wrong by the
same warp on every point of a Photo when one click is off. Training on all 80 teaches the model the
inner wires DeepDarts never clicked; weighting them at half lets the clicked points win where they
disagree. C reads whether that holds: its error at the treble wires, where only projected labels
exist, against its error at the double wires.

**Read at C, 2026-11-18: the projected labels cost the treble wires nothing visible.** The treble
wires, labelled only by projection, read lower than the double wires, the wire the four clicked
points sit on: median 0.274 against 0.303 mm on val, 0.324 against 0.396 mm on test (R2). The half
weight stays. What this cannot show is the projection's own error: val and test are labelled the
same way, so a model that reproduced four-click projection exactly would read zero against them. The
owner's labels, checked at every crossing, measure that in F.

The best epoch was 12 of 30. After it the training loss fell from 0.126 to 0.098 while val's treble
median wandered between 0.28 and 0.35 mm without improving on 0.274, so 30 epochs is not short for the
Board. C trains no Entry points, so its grouped share (0 of 27 val pairs, 0 of 74 test) is D's to
read.

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

`darts-ml predict --run <run>` writes the predictions file `evaluate` reads. It is
the only way a model's output reaches the Held-out set, and it records in the file which run made it.

**Read at D, 2026-11-18: which Entry peaks are kept.** Every local maximum over 0.25 was a Dart, and
most extra ones sat on a real Dart's barrel or flight a few millimetres from its tip, flagged unsure
(seen drawn over 20 val Photos). So a Photo is now scored from at most three Entry points, the most
confident, each over 0.34. `darts-ml deepdarts tune` chose that on val alone, over thresholds 0.25 to
0.55, caps of three or none, and a merge of peaks closer than 0 to 12 mm, then a finer pass at 0.28
to 0.40 in steps of 0.02 with the cap at three and merges of 0, 6, 8 and 10 mm, both inside its grid
now: exactly right rose from
39.1% to 58.8%. Merging peaks within 8 mm added 1.2 points more, but it drops a real second Dart
landing that close, which is the grouped case M1 captures on purpose, so the merge stays at 0 and
remains a setting. The cost is real Darts with low confidence: Darts right fell from 90.5% to 82.1%.
That, and close pairs found as two in 5 of 27, are training's to fix, not decoding's.

**Read after the stride-2 run, 2026-11-19: the threshold falls to 0.24.** The stride-2 head is less
confident per peak, and tune's best sat on the floor of its grid at 0.25, so the grid now starts at
0.12 and holds every threshold from 0.22 to 0.30 in steps of 0.01, the finer pass read here. With the
cap at three and no merge, exactly right is flat at 61.4% from 0.24 to 0.26 and falls
on both sides (60.2% at 0.22, 61.1% at 0.29); 0.24 is kept because, at the same exactly right, it
gets the most Darts right (84.8% against 83.9% at 0.25) and close pairs as two (4 of 27 against 3).
The same rule at D's 0.34 reads 58.2%.

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
sessions, sampled so the owner's Photos make up about half of each batch despite being about a thirtieth of
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
| ADR-0008 | dated amendment: a plain-GPL library bundled in a training tool's wheel, loaded and never called, never shipped, is allowed and listed (taken 2026-11-17, from A's licence finding) | A |
| ADR-0008 | dated amendment: the model (D1), the runtime and its readings (D4, §5), where the weights start (D2) | E |
| `CONTEXT.md` | **Validation sessions**: the training Capture sessions set aside to choose between models, never the Held-out set | B |
| `ml/README.md` | `train`, `predict`, the runs folder; PyTorch and torchvision, and every library the ROCm wheel bundles, in the licence table, with the libraries the ROCm runtime bundles under the LGPL, a runtime exception or, by ADR-0008's 2026-11-17 amendment, the GPL | A, B |
| `CLAUDE.md` | the `train` and `predict` commands | B |
| `PLAN.md`, `DOD.md` | M2 ticked; phase 1's `minSdk` item gets E's latency and size | H |

Not amended: the privacy policy, the listing and `play-app-content.md`. No app code changes in this
phase; phase 1, which ships the model, owes the DeepDarts credit on the licences screen.

## Known gaps, deliberately

- **DeepDarts is face-on.** Nearly all of it is from a fixed mount. It teaches the Board and the Darts;
  only the owner's 450 or so training Photos teach the Angles players stand at. If F misses at steep
  Angles, more training Capture sessions are the fix, at about 2 owner hours each.
- **The projected labels.** Training on DeepDarts' 76 projected points teaches whatever error four
  clicks carry. C cannot measure it, since val and test are projected the same way (R2 shows only
  that the treble wires read no worse than the double); the owner's labels, clicked or checked at
  every crossing, measure it and correct it in F.
- **The whole-Photo pass learns mostly from the owner's Photos.** DeepDarts' Photos are already
  crops, so the first pass, which finds the Board in a whole Photo, has only the owner's 450 or so
  training Photos showing a real room around a Board. DeepDarts crops shrunk onto a padded canvas
  help a little, but their background is not a room.
- **From scratch is slower to learn.** D2 trades accuracy, possibly, for a licence that is clean. C
  showed from-scratch clears B1's median at both wires (R2); no pretrained run was compared, so what
  it costs against one is unmeasured.
- **One Board.** As in M1: the Held-out set measures new Capture sessions, not new homes.
- **The emulator is not a phone.** E's latency chooses a runtime; it is not the app's speed. Phase 1
  reads that.

## Readings

`PLAN.md` rule 3. M2 changes no app, so its readings are taken off the training runs and the tools,
with the command that took them. Each training reading names its run folder.

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | **The gate.** Epoch time on the GPU (ROCm) and on the CPU; the first 200 losses compared | `darts-ml train --probe --device gpu`, then `--device cpu` | **Verdict 1, 2026-11-17.** GPU (Radeon 8050S, ROCm 7.14): 9.7 min an epoch, 22.0 Photos/s. CPU: 20.9 min, 10.2 Photos/s. Loss over steps 151–200: 0.180 against 0.183, 1.7% apart; both from about 2.40 over steps 1–10. 512 px, batch 16, seed 0, `runs/probes/` |
| R2 | The Board on DeepDarts: found share, and median / 95th percentile error at the treble and double wires, on val and on test | `darts-ml evaluate`-style figures on DeepDarts, from the chosen C run | **2026-11-18**, run `2026-11-18-board-512`: `--board-only`, 512 px, batch 16, float32, augmented, 30 epochs in 4.7 h, `best.pt` from epoch 12. **Val:** Board found 1070/1070; treble wires median 0.274 mm, 95th 0.623; double wires median 0.303, 95th 0.711. **Test:** 2150/2150; treble 0.324 / 0.815; double 0.396 / 0.892. `darts-ml deepdarts score --run 2026-11-18-board-512 --split val`, then `--split test` |
| R3 | The Darts on DeepDarts: share of the face-on (`d1_`) and of the angled (`d2_`) test Photos scored right, the paper's way (total), beside 94.7% and 84.0%; and Dart by Dart | the chosen D run | **2026-11-18**, run `2026-11-18-darts-512`: `--init` from C, 512 px, 30 epochs, `best.pt` from epoch 22; at most three Entry points over 0.34 (§4). **Test, Visit total right the paper's way:** face-on 1517/2000 (**75.8%**, paper 94.7%), angled 59/150 (**39.3%**, paper 84.0%). Exactly right: 68.1% and 38.0%; Darts right 3722/4383 (84.9%); close pairs as two 16/74. Board found 2150/2150, wire medians 0.332 / 0.397 mm. Before the three-point rule the same weights read 62.4% and 22.7% the paper's way. `darts-ml deepdarts score --run 2026-11-18-darts-512 --split test`. **2026-11-19, after D**, run `2026-11-18-darts-512-s2-ring`: `--init` from D, 512 px, Entry head at stride 2, ring weight 4 over 4–20 mm, 30 epochs, `best.pt` from epoch 26; at most three Entry points over 0.24 (§4). **Test, the paper's way:** face-on 1621/2000 (**81.0%**), angled 66/150 (**44.0%**). Exactly right: 73.9% and 43.3%; Darts right 3876/4383 (88.4%); close pairs as two 15/74. Board found 2150/2150, wire medians 0.327 / 0.406 mm. `darts-ml deepdarts score --run 2026-11-18-darts-512-s2-ring --split test` |
| R4 | Export, per runtime tried: model size, runtime size per ABI, parity in mm over 1,070 val Photos, emulator latency of both passes, operations that failed | `darts-ml export` and its report | *(E)* |
| R5 | The owner's Photos: B1 and B2 on the Validation sessions for the chosen F run | the chosen F run | *(F)* |
| R6 | **The bar**, each reading: date, commit, weights SHA-256, then every row of `evaluate` | `darts-ml evaluate --predictions <file>` | *(G)* |
