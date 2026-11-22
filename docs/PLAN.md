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

- [x] **Phase 0** — Skeleton: the placeholder Items and reminders gone, Room and the custom backup
  gone because the first version stores no visit history, the system camera and Photo Picker kept
  for the board photo, Darts Scorer's palette and mark
- [ ] **Phase M1** — The data, off the phone (ADR-0008): the `ml/` folder (code only), the DeepDarts
  dataset, the owner's own handheld photos taken and labelled, a held-out set put aside, and the bar
  that phase 1's model must meet written down. **It runs alongside phases 0 and P**
- [ ] **Phase M2** — The model, off the phone (ADR-0008): a detector trained with permissively licensed code,
  the board first and the darts second, its accuracy measured on the held-out handheld photos.
  **Phase 1 is built alongside it, and closes only on a model that met the bar** (amended
  2026-11-20; it used to wait for M2)
- [x] **Phase P** — The pipeline: repository setup, upload key, Play entry, secrets, a green internal upload.
  0.2.0 reached internal testing on 2026-11-22 (testers: `only-me-Tester`)
- [ ] **Phase 1** — The mechanism on the phone: one photo in, the darts drawn on the board with their
  score, offline, plus tapping the board to correct a dart, and the system camera with its path for a
  phone that has no camera app (no `CAMERA` permission is asked for).
  Each dart's marker carries a white and black keyline: no brand colour reaches 3:1 on all four board
  colours (black, cream, red, green). Readings: real Visits on a real Board, in ordinary room light
- [ ] **Phase G** — A Mounted camera, an addition the player turns on: by default the photos are
  still taken with the phone. A spare Android phone running this app in its camera role, mounted
  beside the Board, takes the Photo when the player taps after a Visit and sends it over the local
  Wi-Fi to the Player's phone, which scores it, offline, as it scores a handheld Photo
  ([`phase-G.md`](phase-G.md), ADR-0009). One camera, so no merge of Angles: **it comes before
  phase 2**, and a second camera waits for phase 2's merge. `INTERNET` returns for that local link
  only, with the amendments phase S listed for it (ADR-0007, `scripts/aab-permissions.py`, the
  privacy policy live before any build carries it, the Data safety answers); the Mounted camera holds
  `CAMERA`, which also makes the handheld *Take a Photo* ask for it unless the owner chooses a second
  app (`phase-G.md` Q1). Its gate reads the Board half of M1's bar on Photos from the mount position;
  the Darts half closes it. It ships in 1.0.0. **Before the door**. (Amended 2026-11-22: the owner
  chose the spare phone over a network camera or a GoPro, one camera first and before phase 2; no
  Bluetooth. Phase S, if built after, adds only the sharing's own part)
- [ ] **Phase 2** — As few photos as it needs: merging several angles in board millimetres, and
  asking for another angle only when a dart is missing, unsure, or on a wire (ADR-0008)
- [ ] **Phase T** — The Scoreboard on a Second screen, an addition the player turns on: with a
  Second screen (a TV or monitor connected by HDMI cable or Miracast), the app shows a large
  Scoreboard there through Android's `Presentation` API, while the phone keeps the controls. The
  Scoreboard shows the last Visit's Score and its Darts on a drawn Board, never the Photo, so no
  Photo is sent to a wireless Second screen. It is read from across the room: large high-contrast
  text, no state told by colour alone, nothing told by sound alone, and the same Score stays
  readable on the phone, since TalkBack does not read the Second screen. The phase says what the
  player sees with no Second screen and when one drops mid-Visit, because not every phone can drive
  one: many have no USB-C video out, and stock Android, Pixels included, has no Miracast. It runs
  offline and asks for nothing; plain screen mirroring keeps working without it. Google Cast is not
  used: a custom Cast receiver is a web page hosted online and registered with Google, which an
  offline app cannot be. It adds CONTEXT.md terms for the Scoreboard and the Second screen, with
  *TV*, *monitor*, *cast* and *display* in the Not column. It ships in 1.0.0, and since it asks for
  nothing it may land on either side of the door. Its reading is taken on a real Second screen, over
  both a cable and Miracast
- [ ] **Phase S** — Sharing a photo, by choice: a player can send a photo with its corrected score
  to help train the model. Off by default and asked per photo; it ships in 1.0.0. Scoring is the
  same whether or not a player shares, and the new privacy policy is live before any build carries
  the feature, internal testing included. Its ADR comes first and settles that `INTERNET` returns
  for the whole app, including what the billing library's usage logging could then send for every
  player, opted in or not, plus a place to receive photos, consent and deletion. It amends ADR-0007,
  ADR-0008 (its "photos never leave the phone" context and its training-data list),
  `scripts/aab-permissions.py`'s `INTERNET` rule, the privacy policy and `docs/play-app-content.md`'s
  Data safety answers, and adds CONTEXT.md terms for a shared photo and the consent. If phase G is
  built first, its ADR has already brought `INTERNET` back with those amendments, and phase S adds
  only the sharing's own part. **Before the door**, so testers and Play's Data safety answers see it
  from the first build
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
API for it, so no code of yours can tell a granted state from a denied one — only a reading of the
vendor's own screen over `adb`, run by you (`8ae670b:scripts/device-gate.py`, removed with the
reminders in phase 0). The clause survives it: the phase still owns the hand-off and still owns
saying what a denial costs, without claiming to know the answer. What changes is only who can check.

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
directories, because a backed-up photo is a photo that left the phone: in both
`dataExtractionRules` (Android 12 and later, cloud backup and device transfer) and
`fullBackupContent` (Android 8 to 11), or the photos live in `noBackupFilesDir` instead.

## Phase M1 — The data

The riskiest part, and the one that decides whether there is an app at all, starts with photos rather
than code. The owner takes handheld photos of a real board from the angles a player actually stands
at and labels their calibration points and Entry points; the DeepDarts dataset is added beside them,
and a share of the owner's photos is held out and never trained on. The `ml/` folder holds the code
that prepares them; the photos, labels and weights stay out of git (ADR-0008). Before M1 closes, the
bar phase 1's model must meet is written in `phase-M1.md`, so it is set before training starts, not
fitted to the first result. Labelling costs the owner's hours, training costs compute and
iterations, so per rule 2 they are two phases.

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
| Sending a photo to train the model (off by default) | when the player first chooses to send one, then for each photo | phase S |
| Camera, for the Mounted camera's own captures (`CAMERA`) | the first tap on *Use this phone as the mounted camera* | phase G |
| Camera, for the handheld *Take a Photo*, once `CAMERA` is declared (unless `phase-G.md` Q1 chooses a second app) | the first tap on *Take a Photo* | phase G |
| Local network (`ACCESS_LOCAL_NETWORK`), only once the target SDK reaches 37 | pairing, on both phones | the target-SDK bump (ADR-0009) |

## Not in this plan

- The app sending a player's photo off the phone without the player choosing to, photo by photo.
  Phase S's opt-in is the only way a photo leaves the phone. The model is trained off the phone
  (ADR-0008).
- A live camera view that scores while the darts are being thrown. The app scores still photos of
  darts already on the board.
- Fixed or mounted cameras other than phase G's.
- Soft-tip (electronic) boards, until an ADR covers their geometry.
