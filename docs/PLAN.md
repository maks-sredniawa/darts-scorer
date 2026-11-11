# Roadmap

Sequence and status only. The reasoning behind a decision lives in [`docs/adr/`](adr/); the words
live in [`CONTEXT.md`](../CONTEXT.md); commands, layout and house rules live in
[`CLAUDE.md`](../CLAUDE.md).

**This file is the record, not the worklist.** What is still open — the boxes to tick, with the
device state and the commands to read it — lives in [`DOD.md`](DOD.md), which stays short enough to
open every session. Read the phase you are in here; read `DOD.md` to know what to do next.

**A phase being planned or built gets its own file** — `phase-N.md` beside this one — so working on
it costs the phase rather than the whole history. This file stays deliberately thin: one paragraph
per phase, no task lists. The detail is written when the phase opens, not now. The app this template
was extracted from and the first app built from it settled on exactly this split independently.
[`phase-template.md`](phase-template.md) is the shape a phase file settled into; copy it on the day.

## Status

- [ ] **Phase 0** — Skeleton: the placeholder Items and reminders gone, Room and the custom backup
  gone because the first version stores no visit history, the system camera and Photo Picker kept
  for the board photo, Darts Scorer's palette and mark
- [ ] **Phase M1** — The data, off the phone (ADR-0008): the `ml/` folder (code only), the DeepDarts
  dataset, the owner's own handheld photos taken and labelled, a held-out set put aside, and the bar
  for opening phase 1 written down. **It runs alongside phases 0 and P**
- [ ] **Phase M2** — The model, off the phone (ADR-0008): a detector trained with Apache or MIT code,
  the board first and the darts second, its accuracy measured on the held-out handheld photos.
  **Phase 1 waits for it**
- [ ] **Phase P** — The pipeline: repository setup, upload key, Play entry, secrets, a green internal upload
- [ ] **Phase 1** — The mechanism on the phone: one photo in, the darts drawn on the board with their
  score, offline, plus tapping the board to correct a dart, and the camera ask with its denial path.
  Readings: real Visits on a real Board, in ordinary room light
- [ ] **Phase 2** — As few photos as it needs: merging several angles in board millimetres, and
  asking for another angle only when a dart is missing, unsure, or on a wire (ADR-0008)
- [ ] **Phase 3** — *(safe to hand to a stranger)* ← **the door: closed testing opens here**. The
  first-run path, the DeepDarts attribution on the licences screen
- [ ] **Phase N** — Ship shape: listing, screenshots, the App content answers

---

## Rules that cut across every phase

### 1. Decide where the door is, early

**The door** is the first build a stranger installs — closed testing, for a new personal Play
account. Everything that reaches a tester's phone is harder to change afterwards: a stored key, a
permission, a `minSdk`, the `applicationId`. So name the phase the door sits after, and write down what
it freezes. The closed-test window is calendar time and other people's replies, so later phases can
run while it waits.

**Do not plan a decision on the testers' answers.** The first app built from this template left two
phases' open questions — defaults, whether a behaviour was too clever — to be asked of its closed-test
testers. The survey that did go out asked none of them, and both closed *unanswered, on the values
that shipped*. What carried
the decisions was the device readings. Decide on a reading, ship a default, and let the mail hand-off
(`ui/support/`, live from the door) tell you if it is wrong.

### 2. When the two halves of a phase cost wildly different amounts, they are two phases

The first app built from this template split every one of its middle phases along cost or along
kind, because in each case a bundle of a cheap item with an expensive one — or a feature with the
safety work it depends on — hid which half was blocking. However neatly one sentence describes both, two costs are two phases.

### 3. A phase proves itself on the phone, not in a test

Every phase ends with readings taken off a real device and written into its `phase-N.md`, with the
command that produced them. A green test run says the code does what the test asked; the phone says
what the ROM allowed. Vendor ROMs are where those two part company.

**But the rule has a second clause, and leaving it out is how a roadmap arrives at no tests at all.**
Most of the risk in an app this size is device behaviour, and none of that is reachable by a unit
test — but the pure functions that *compute or bound a safety value* are the exception, and each of
them fails in exactly the direction the app exists to prevent. So: device behaviour is proven by
measurement; a safety value is proven by test, and **the phase that introduces one introduces its
test**. For the first app built from this template that came to five tests across the whole roadmap
— a window that crosses midnight, two deadlines resolved against a clock, a ramp whose bottom end
turns the backlight off over a live touchscreen, the width of a window that swallows touches, and a
restored intent that had to be refused. Not a testing culture. Five tests standing in front of the
properties `CLAUDE.md` calls load-bearing.

⚠ **Reconcile the list when the roadmap closes, and expect the count to be wrong.** That app planned
four and shipped five: the fifth arrived because a device reading found a fault no test had been
written for. That is the rule working, not an exception to it — the top of a ramp is not visible on a
device until it strands somebody.

### 4. Ask for nothing before the feature that needs it

An app of this shape ends up asking the user for three or four things, and most of them are hand-offs
to settings screens whose result cannot be read back reliably — `appops` has been caught lying about
`SYSTEM_ALERT_WINDOW` on a real phone. So the sequence is a rule rather than a phase:

**Every ask waits for the moment the feature needing it is switched on. The phase that introduces an
ask owns its hand-off, its re-read, and what the user sees when the answer is no.**

Write the table for your app — the ask, the moment it is made, the phase that owns it — and put it
here, so a later phase cannot quietly move an ask forward to "get it out of the way".

**The third clause is the one that gets left out, and it is the one that generates support mail.**
These denials nearly all fail *silently*: a denied notification permission leaves a foreground
service running with no way to stop it, a denied autostart leaves reboot restore never firing, a
denied battery exemption leaves a schedule never firing. In each case the app knows and the user does
not. A re-read tells the app; **nothing tells the person holding the phone** unless a screen does.
`ui/common/Surfaces.kt`'s `WarningBanner` is the idiom for a state the app can re-read; a permanent
row that makes no claim is the idiom for one it cannot.

**Autostart is the case where even the re-read is out of reach.** It is not an appop and there is no
API for it, so no code of yours can tell a granted state from a denied one — only
`scripts/device-gate.py`, over `adb`, run by you. The clause survives it: the phase still owns the
hand-off and still owns saying what a denial costs, without claiming to know the answer. What changes
is only who can check.

**The same logic applies to side effects, not only to permissions.** A feature that makes one of the
phone's own controls go inert is a system control that appears broken, caused by you. The phase that
introduces the behaviour owns saying so.

---

## Phase 0 — Skeleton

The template's placeholder domain goes: Items, and the reminders module (`work/`, exact alarms).
Darts Scorer schedules nothing. The photo path stays, because the board photo arrives through
`TakePicture` or the Photo Picker. Whether it is kept after scoring is phase 1's question, not this
one. The first version stores no visit history, so Room and the custom backup go here too, before
the first upload while deleting them is still free, with the amendments to ADR-0001 and ADR-0005
that `optional-modules.md` lists. Storing history is a later phase, with its own ADR, if it is
wanted. Whatever platform Auto Backup takes in the custom agent's place excludes the photo
directories, because a backed-up photo is a photo that left the phone.

## Phase M1 — The data

The riskiest part, and the one that decides whether there is an app at all, starts with photos rather
than code. The owner takes handheld photos of a real board from the angles a player actually stands
at and labels their calibration points and Entry points; the DeepDarts dataset is added beside them,
and a share of the owner's photos is held out and never trained on. The `ml/` folder holds the code
that prepares them; the photos, labels and weights stay out of git (ADR-0008). Before M1 closes, the
bar for opening phase 1 is written in `phase-M1.md`, so it is set before training starts, not fitted
to the first result. Labelling costs the owner's hours, training costs compute and iterations, so per
rule 2 they are two phases.

## Phase M2 — The model

Its first stop is the board alone: from a handheld photo, find the calibration points and fit the
homography. The reading is the error in millimetres at the double and treble wires. A detector that
cannot place the board cannot place a dart, so the darts come second, measured as the share of
Visits scored exactly right on the held-out handheld photos, against the bar M1 wrote down.

## Phase P — The pipeline

`DOD.md`'s *Before the first upload*: the GitHub repository and its ruleset, upload key, Play entry
under `com.maksforge.dartsscorer`, secrets, and a green internal upload of the skeleton.

## Asks

| Ask | When | Owner |
| --- | --- | --- |
| Camera (through the system camera, so no `CAMERA` permission) | the first tap on *Take a photo* | phase 1 |

## Not in this plan

- The app sending a player's photo off the phone, for any reason, including to train the model.
  The model is trained off the phone, on the owner's own photos and the DeepDarts dataset
  (ADR-0008).
- A live camera view that scores while the darts are being thrown. The app scores still photos of
  darts already on the board.
- Fixed or mounted cameras.
- Soft-tip (electronic) boards, until an ADR covers their geometry.
