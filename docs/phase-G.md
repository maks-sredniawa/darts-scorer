# Phase G — A spare phone mounted beside the Board takes the Photo when the player taps, and the Visit is scored on the player's own phone

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
rests on [ADR-0009](adr/0009-a-mounted-camera-is-a-spare-phone-paired-over-the-local-network.md),
written for it, and amends ADR-0008 (its *no fixed camera* context and its rejected fixed-camera
alternative) and ADR-0007 (`INTERNET` returns), both by dated amendments in the same pull request as
ADR-0009. It relies on ADR-0002 (every Photo through `MediaFiles`), ADR-0003 (nothing posted, nothing
scheduled) and ADR-0005 (Auto Backup is include-only). [`CONTEXT.md`](../CONTEXT.md) gains **Mounted
camera**, **Player's phone** and **Pairing**, and **Capture session** is widened to a Mounted camera's
position, all in that same pull request.

**What closing this phase means.** Today a player walks to the Board after every Visit and takes the
Photo by hand. After this phase a player who has a spare Android phone mounts it beside the Board,
pairs it once by pointing it at a QR on their own phone, or by pasting that QR's text into it, and
from then on taps *Take with the mounted
camera* after a Visit: the spare phone takes the Photo, sends it over the home Wi-Fi to the player's
phone, and the Visit is scored there exactly as a handheld Photo is. The Photo travels between the
player's two phones over a pinned, encrypted link and nowhere else. A player who never pairs a camera
sees one change: the first *Take a Photo* asks for the camera permission (D5). The difference a device can be asked about: **on two emulators on one
virtual Wi-Fi, a paired Mounted camera answers a capture with a Photo that the Player's phone scores,
a third unpaired emulator can neither connect nor capture, and on two real phones at a real Board the
Board half of M1's bar is read on the Mounted camera's own Photos (R1).**

**`PLAN.md`'s paragraph for this phase was wrong in five places, said here first, and amended in the
same pull request as this file:**

- It left the camera open between a network camera, a spare phone and a GoPro, to be chosen on a test
  of each. The owner chose the spare phone on 2026-11-22, without that test (ADR-0009, decision 1).
- It said one to three cameras, through phase 2's merge. Phase G is **one camera, before phase 2**;
  two cameras wait for phase 2's merge, and three are not planned.
- It named Bluetooth among the permissions, and its *Asks* table carried a Bluetooth row. Nothing in
  this phase uses Bluetooth or location: NSD on the Wi-Fi needs neither (ADR-0009, decision 2).
- It asked how several cameras are reached at once. With one camera, it is not this phase's question;
  each camera is its own connection, and the camera list is a list from the start.
- It did not foresee that declaring `CAMERA` for the camera role changes the handheld path on every
  phone (ADR-0009, *Context*). The owner chose to ask for it at the first handheld *Take a Photo*
  (D5).

---

## Decisions for the owner

### Decided 2026-11-22, by the owner

| # | Decision | Decided |
| --- | --- | --- |
| **D1** | **The camera** | **A spare Android phone running this app in a camera role**, mounted beside the Board and facing its face. One camera first; maybe two later |
| **D2** | **The permissions** | **`INTERNET` returns for the local link only**, phone to phone on the same Wi-Fi, never to a server. **The Mounted camera holds `CAMERA`** and captures through CameraX; the handheld path keeps the system camera. The privacy policy, Data safety and `aab-permissions.py` change before any build carries either |
| **D3** | **Where Photos go** | **Never off the owner's own phones**: from the Mounted camera to the Player's phone over the local network, and nowhere else |
| **D4** | **The order** | **One-camera phase G before phase 2.** It needs no merge of Angles. Two cameras wait for phase 2 |
| **D5** | **The handheld path, now that `CAMERA` is declared** (`TakePicture` throws unless it is granted, on every phone) | **Ask for `CAMERA` at the first handheld *Take a Photo***, with one line saying why; a denial leaves the Photo Picker. Not a second app for the camera role, and not in-app capture on the handheld path |
| **D6** | **When the paperwork merges** | **E merges first, right after checkpoint 0 and before B**, so the privacy policy runs one release ahead of the app rather than one behind. Release PRs are then merged on green CI as usual; none has to be held |
| **D7** | **Data safety once a Photo crosses the Wi-Fi** | **Still *No data collected***, on Play's end-to-end-encryption exemption: the Photo is readable only by the two phones that hold the keys, and the developer never receives one |
| **D8** | **Mount positions for gate A** | **All three are possible, and gate A reads all three**: (a) the wall to one side at Board height, 0.5–1 m out from the Board's face; (b) above the Board, looking down at it; (c) a stand by the oche (see D11) |
| **D9** | **The spare phone** | **A Redmi Note 8 Pro on Android 11 (API 30)**, already on the owner's Wi-Fi with the debug app installed |

### Decided 2026-11-23, by the owner

| # | Decision | Decided |
| --- | --- | --- |
| **D10** | **A way to pair without seeing the QR** (WCAG 2.2, 1.1.1) | **The QR stays, with a content description, and its payload can also be copied or shared as text** from the Player's phone and pasted into a field on the Mounted camera: the same fingerprint and one-time token, the same TLS pinning and HMAC binding. Both routes are accepted with TalkBack on, in B and C (ADR-0009, decision 4). Chosen over recording pairing as visual-only |
| **D11** | **When the gate is read, and from where** | **B, C and D are built first, and A is read on the finished app**, from the Mounted camera's own Photos, as the owner's real test. The owner's spare phone sits on a 3 m stand with a 360° holder, so a position can be anywhere around the Board, not only the three of D8. Chosen over reading A first with the phone's own camera app |

### Recommended in ADR-0009, decided as written when its pull request merges

Discovery by NSD; a TLS socket on the Mounted camera that the Player's phone pulls from; pairing by a
QR on the Player's phone (or its text, D10) with mutual TLS pinned to both phones; a button as the trigger; a 2048 px
JPEG never stored on the camera; the phone's own lens correction and nothing else; the link's
behaviour when it drops; a Settings row for the role; the screen kept on by a window flag with no
service; `ACCESS_LOCAL_NETWORK` left undeclared until target SDK 37; the billing backend excluded.
Each has its options and reasons in ADR-0009.

---

## 0. What this phase inherits

- **Phase 1's whole scoring path** (`phase-1.md`): a Photo through `MediaFiles` as the `photos` kind,
  the two passes on LiteRT, the Darts drawn and corrected, the Photo deleted when the next Visit's
  arrives. A Mounted camera's Photo enters that path where a handheld one does; nothing after the
  arrival changes.
- **No network and no camera permission.** The manifest removes `INTERNET`, `aab-permissions.py`
  forbids it and `CAMERA`, and the privacy policy, Data safety, the store listing and phase 1's ask
  table all rest on that. Every one of them changes here.
- **The model was trained and measured on handheld Photos and DeepDarts.** A Mounted camera sees the
  Board from one fixed, often steep Angle. `dart-pose-v6`, fixed webcams at steep side angles, was
  tried as training data and dropped on 2026-11-22 (ADR-0008); it says nothing about how the shipped
  model reads such Photos. That is the gate.
- **The owner cannot throw darts at the moment** (2026-11-20). The gate and most readings need
  none: the Board half of the bar reads an empty Board, and the link's readings need no Board at all.
  Readings with Darts in the Board wait, as phase 1's R3 does.
- **The asymmetry that shapes the phase:** everything about the link, pairing and the flow can be read
  on emulators, which since emulator 36.5 share one virtual Wi-Fi and see each other's NSD; whether
  the Photo is good enough, how the lens bends and what the battery does can only be read on a real
  spare phone at a real Board.

## What is in, and what is deliberately not

**In:** the camera role on a spare phone (CameraX, a screen that stays on, aiming, QR scanning); NSD
discovery; the pinned TLS link and its pairing; *Take with the mounted camera* on the Visit screen,
its states and its failure paths; the handheld path's `CAMERA` ask (D5); the billing backend
excluded; the permission tables, privacy policy, Data safety reasoning, store listing and `CLAUDE.md`
brought in line; the gate's Board readings from the mount.

**Not in, each with a reason:**

- **A second Mounted camera.** Two Photos of one Visit need phase 2's merge in Board millimetres;
  until it exists, a second Photo has nowhere to go. The stored list and the protocol already allow
  it.
- **Detecting a Visit, a Dart or the pulling of Darts from the camera's frames.** That is a live
  camera view, which `PLAN.md` keeps out, and it would make the camera stream rather than take one
  still.
- **A network camera, a GoPro, Bluetooth, Wi-Fi Direct, Nearby Connections.** ADR-0009's alternatives,
  each with its reason.
- **Straightening the lens on the Player's phone.** Waits for a reading that asks for it (ADR-0009,
  decision 7).
- **The Mounted camera running with its screen off.** It would need a foreground service of type
  `camera`, its permission, a notification and a Play declaration with a video, against ADR-0003. A
  phone on a charger with a dimmed screen costs none of that.
- **Training on the Mounted camera's Photos.** If gate A's verdict asks for it, that is phase M2's
  work on new Capture sessions, not this phase's code.

**The tempting one: reuse the Board's homography between Visits.** The camera does not move, so the
Board found in the first Photo could be kept, and a Dart covering Calibration points would no longer
matter. It is left out because a mount that is knocked, a phone that slips in its holder or a door
that shakes the wall moves the Board in the Photo by millimetres, and a cached homography would then
score every later Visit wrong without anything on screen saying so. A per-Photo fit checks itself on
every Visit. If readings show the per-Photo fit failing on covered Calibration points from the mount,
a cached fit with a drift check against the new Photo is a decision of its own, with its own reading.

---

## Checkpoints

| | Checkpoint | Merges | Depends on |
| --- | --- | --- | --- |
| **0** | **The ADR and this plan**: ADR-0009, the amendments to ADR-0007 and ADR-0008, `CONTEXT.md`'s terms, `PLAN.md`'s paragraph | `docs:` | — |
| **E** | **The paperwork**: the privacy policy, `play-app-content.md`'s Data safety reasoning, the store listing in every language, written for the app as it will be once B to D ship | `docs:` | 0 |
| **A** | **The gate**: is the Board found from the stand's positions (D8, D11), within the Board half of M1's bar? Read on the finished app, after D | a `docs:` with the verdict; a `feat:` or `fix:` for the app when a verdict changes it: verdict 1's recommended position in the copy, translated, or verdict 3's row behind the debug seam; a `chore(ml):` that builds each position's session from `phone-captures/`, one Photo per Visit in the order of each marked Visit's `keptAt` (§2), with `evaluate`'s option to read a session outside the Held-out set if it needs one | D |
| **B** | **The camera role**: Settings' *Mounted camera* row, the camera screen, CameraX capture into memory, the screen kept on and dimmed, QR scanning and the paste field (D10); the handheld path's `CAMERA` ask (D5) | `feat:` | E |
| **C** | **The link and pairing**: Keystore keys, NSD, the TLS socket and its frames, the QR with its content description and its text to copy or share (D10), the pairing proof, unpairing, the store outside the backup; `INTERNET` declared, the billing backend excluded | `feat:` | B |
| **D** | **The capture-and-score flow**: *Take with the mounted camera* on the Visit screen, the camera's state, the timeouts and failure paths, the Photo into phase 1's path | `feat:` | C |

**The order is 0, E, B, C, D, then A on the finished app (D11).** B to D stay in the order the owner
listed them: the link needs a camera to serve, and the flow needs the link. Around them:

- **E comes right after 0** (D6). The privacy policy, the Data safety reasoning and the listing must
  be live before any build carrying `INTERNET` or `CAMERA` reaches a track, internal included, and
  this repo merges release PRs as soon as CI is green. Merged first, they run one release ahead of
  the app, which errs on the safe side; merged last, they would run a release behind, which breaks
  Play's policy. What describes the artifact rather than the app moves with the code instead:
  `aab-permissions.py`'s tables and `play-app-content.md`'s artifact table travel with the commit
  that adds each permission, because the upload gate fails otherwise, and `CLAUDE.md`'s stack rows
  and the manifest's comment travel with B and C.
- **A comes last** (D11, the owner's choice on 2026-11-23). Read first, it could have stopped B
  before any code; read last, it is taken on the Photos the Mounted camera itself sends, which are
  the Photos the phase is about. The link does not depend on the model, so B to D stand either way;
  what A decides is whether the phase closes and what the copy recommends.

---

## 1. The paperwork (E)

Merged right after checkpoint 0 (D6), so each document describes the app as it will be once B to D
ship, one release before it does. The policy says what the app does when a Mounted camera is set up;
a player who sets none up meets none of it.

- **`docs/privacy-policy.md`**, re-dated: the *collects nothing* section keeps its title and loses *no
  permission to use the internet*; a section for the Mounted camera says the app uses the local
  network only to send a Photo from a phone you set up as a camera to your own phone, encrypted, and
  never to a server; the camera permission's two uses, the Mounted camera and the system camera; the
  billing library's logging still has no way out (ADR-0009, decision 12).
- **`docs/play-app-content.md`**, prose only: Data safety's point 1 rewritten from *the app cannot
  transmit anything* to *the app transmits only a Photo, only between the player's own paired phones,
  end to end encrypted*, with Play's exemption quoted (D7); a sixth point for the billing backend;
  *Would change* gaining *a connection to anything but a paired phone*; the content rating's reasoning
  for *users interact: No*; production access's engagement answer, which leans on *no internet
  permission*, reworded to *no analytics and no server*. The Data safety answer itself does not
  change, so nothing is re-submitted in the Console.
- **`docs/store-listing.md`**, every language: *does not request the internet permission* goes; the
  *PERMISSIONS* block names the camera and the local network. Translated per the translation brief,
  from English, in the same pull request.

**What moves with the code instead**, because it describes the artifact rather than the app:

- **`scripts/aab-permissions.py`**: `CAMERA` to `EXPECTED` and both camera features into
  `EXPECTED_FEATURES` at `False` in B; `INTERNET` and `CHANGE_WIFI_MULTICAST_STATE` to `EXPECTED`,
  the `backend:` meta-data check, and
  `FORBIDDEN` gaining `NEARBY_WIFI_DEVICES`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`,
  `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`, `BLUETOOTH_ADVERTISE`, `ACCESS_LOCAL_NETWORK` (until target
  SDK 37) and `FOREGROUND_SERVICE_CAMERA` in C. Its docstring and comments come in line with each.
- **`play-app-content.md`'s artifact table and forbidden list**, in the same commits.
- **`CLAUDE.md`**: the camera row (*`TakePicture` for the handheld path; CameraX for the Mounted
  camera, ADR-0009*) in B; the billing row (*`INTERNET` kept, its logging backend excluded*) and a row
  for the link in C.
- **`CLAUDE.md`'s and `README.md`'s *the photos never leave the phone***, and the public home page
  `docs/index.md`'s *The photos never leave your phone* (its line 8), rewritten in C to *the
  player's own phones*, with the Mounted camera named beside phase S (ADR-0008's amendment). The
  home page is live at `maksforge.com/darts-scorer/`, so its text stays as it is until C.
- **The manifest's comment** on `INTERNET`, rewritten for the local link, in C.
- **The policy's and the listing's *today* lines**, each in the checkpoint that makes it false: B
  rewrites `privacy-policy.md`'s *Today's version has no camera permission* and `store-listing.md`'s
  *Today, none to ask for* (EN and PL); C rewrites the policy's *no permission to use the network at
  all*.

**Acceptance (E):** the policy and the listing read against ADR-0009's decisions 11 to 13 and
`play-app-content.md`, in one pull request; `python3 scripts/translation-gate.py origin/main` passes;
the policy is live at `https://maksforge.com/darts-scorer/privacy-policy` before B merges.

## 2. The gate: is the Board found from where a camera can be mounted?

### The question, in the form that can be measured

On Photos the Redmi Note 8 Pro (D9) takes from each position the owner sets the stand at (D11), at
least three, each recorded as its height, its distance from the Board's face and its angle, of an
empty Board in the room's ordinary light, does the shipped model find the Board in at least 98% of
them, with the error at the treble wires and at the double wires each within a median of 0.5 mm and
a 95th percentile of 1.0 mm: the Board half of `phase-M1.md` D1?

### The apparatus

- The Mounted camera itself (D11): the finished app on the Redmi, on the owner's 3 m stand with its
  360° holder; at least 20 Photos per position, moving the mount a few centimetres between groups of
  five, so the figure is not one framing's luck.
- The Photos reach `ml/` as the debug build's marked Visits: each is taken with *Take with the
  mounted camera* on the debug Player's phone, which keeps it in `files/marked/` (`phase-1.md` §4).
  A Visit is kept only with a result, so D's debug half also keeps a Photo the link delivers on
  which no Board is found: those are the Photos the gate most needs. After each position,
  `uv run --directory ml darts-ml pull-marked --serial <serial> --delete-after` copies them into
  `$DARTS_DATA/phone-captures/<date>/`.
- `ingest` cannot read those Photos. A marked Photo is a byte copy of the `photos` file `MediaFiles`
  wrote, which carries no EXIF `DateTimeOriginal`, and `read_shot` refuses any file without one; and
  `ingest` expects three Angles per Visit, where the gate has one Photo of an empty Board. So A adds a
  `chore(ml):` that builds each position's session from `phone-captures/`: one Photo per Visit,
  ordered by the `keptAt` in each marked Visit's `.json`, with a sheet `label`, `prefill`, `review`
  and `check` can read.
- Each position is a **Capture session** in `CONTEXT.md`'s widened sense: one Mounted camera at one
  position, one kind of light, one day. Its height, distance and angle are written down at the
  stand and repeated in the verdict. Once that chore has built it, it goes through `label`,
  `prefill`, `review` and `check` like every session, Hand points and all, so the Calibration points
  are labelled rather than guessed.
- The Board figures are read with `predict` and `evaluate` for the shipped run, pointed at that
  session by a manifest of its own (`--manifest`). If `evaluate` cannot read a session outside the
  Held-out set, that option and its test go into the same `chore(ml):`.
- These sessions are not trained or chosen on until the verdict is written.

### The verdicts, decided now rather than argued about later

1. **At least one position meets the Board half of the bar** → the best of them is the one the copy
   recommends; the Darts half is read in R8 when the owner can throw again.
2. **The Board is found at one position in at least 98% of Photos but its error misses the bar** →
   the sessions become phase M2 data (a training session and a Validation one, per M2's rules), and
   the phase closes only on a model that meets the bar from the mount, as phase 1 closes only on
   M2's.
3. **No position finds the Board in 98% of Photos** → the Mounted camera row stays out of any
   production release: a `fix:` moves Settings' *Mounted camera* row behind the `app/src/debug/`
   seam, with a no-op in `src/release/`, which leaves *Take with the mounted camera* unreachable
   since it shows only with a camera paired. It merges before any production release, and none goes
   out before A's verdict is written, since a production release is only a manual dispatch of
   `publish-play-production.yml`. The finding goes to the owner with the Photos' overlays, and the
   choices are training data from the mount first, or pausing the phase.

### The verdict, taken *(date)*

*(Which one, the figures per position, and anything neither verdict anticipated.)*

## 3. The camera role (B)

**Shape.** Settings gains a **Mounted camera** row; it opens a screen with *Add a mounted camera* and
*Use this phone as the mounted camera* (ADR-0009, decision 9). The second asks for `CAMERA`; denied,
it explains and offers the system settings, since a camera role without a camera is nothing. Granted,
it opens the **camera screen**: full screen, preview on, a frame showing where the Board should sit,
*Scan the QR on your phone*, and below it a *Paste a pairing code* field with *Pair* (D10), for a
player who cannot scan. Both feed the payload parser of the *Tests* section; a code it refuses says
*That is not a pairing code* in an assertive live region. The role is stored by enum name in the pairing store (ADR-0009,
decision 4); a phone in the camera role opens straight into this screen.

**Capture.** CameraX `ImageCapture` bound with the preview, `takePicture` into memory, encoded with
`MediaFiles`' `photos` encoding at quality 90 into bytes (ADR-0009, decision 6). The default back
camera; an ultra-wide is refused. `DISTORTION_CORRECTION_MODE_HIGH_QUALITY` through `Camera2Interop`
where offered. In B the capture is triggered by a debug-only button in `app/src/debug/`, since the
link arrives in C.

**The screen.** `FLAG_KEEP_SCREEN_ON` while the screen is in front; after 30 s without a touch the
preview hides and the window's brightness drops to its lowest, leaving a status line that shifts
position every minute; a touch restores both (ADR-0009, decision 10). That status line (*Waiting for
your phone*, *Connected*) is a polite live region (`LiveRegionMode.Polite`), so TalkBack announces
each change without a touch, dimmed or not. No lock on orientation: the
Photo's rotation is baked in from the display's, so a phone mounted sideways sends an upright Photo.

**The handheld path (D5).** The first *Take a Photo* on any phone asks for `CAMERA` with a
line of rationale; granted, `TakePicture` runs as today; denied, phase 1's *No camera app* banner
becomes *Camera not allowed* with a way to the system settings, and the Picker stays. `PLAN.md`'s
*Asks* table carries this row from checkpoint 0, with phase 1's *no `CAMERA` permission* row marked
as replaced by it once B ships.

**Acceptance (B):**

- On `pixel-api36` and `urgent-api26`: the Settings row, the `CAMERA` ask and its denial, the camera
  screen with the emulator's virtual scene in the preview, the debug capture producing a JPEG of
  2048 px on its long edge with no EXIF beyond orientation, and nothing new under the app's
  `files/` or `cache/` after it (`adb shell run-as <id> find files cache`).
- The dimming after 30 s and its undoing on a touch, read with `adb shell dumpsys window` for the
  window's brightness.
- A fresh install's first *Take a Photo* asks for `CAMERA`; granted, the system camera
  opens; denied, the banner and the Picker.
- `aab-permissions.py` on a `bundleRelease`: `CAMERA` expected, both camera features at
  `required="false"`, nothing else new. A merged permission from CameraX fails it, and is decided then.
- On the Redmi Note 8 Pro (D9): the preview, a capture, and the default camera being the main lens,
  not its ultra-wide or macro.
- TalkBack on the camera screen announces *Waiting for your phone* and, in C, *Connected* as each
  appears, with focus left where it was.
- **Both pairing routes with TalkBack on** (D10), on the camera screen: the scan area and the
  *Paste a pairing code* field are each reachable by swiping and read by their labels; a scanned QR
  and a pasted code are each accepted (in B, the payload parsed and the pin stored, read in
  `adb logcat`), and a pasted wrong code is announced as *That is not a pairing code*.

## 4. The link and pairing (C)

**Shape.** ADR-0009, decisions 2 to 4: an EC P-256 Keystore key per phone; the Mounted camera
registers `_dartsscorer._tcp` and listens on TLS; the Player's phone shows the QR, the camera scans
it or the player pastes its text (D10), the Player's phone connects in pairing mode, checks the MAC
and pins; from then on, mutual TLS pinned both ways, the five frame types, `PING` every 5 s. When
`SDK_INT < 30` or `SdkExtensions.getExtensionVersion(TIRAMISU) < 7`, each side holds a
`MulticastLock` while NSD runs (ADR-0009, decision 2). Each Keystore key allows `DIGEST_NONE` as
well as `DIGEST_SHA256`, or no handshake completes, and the Player's phone connects through the
Wi-Fi `Network`, retrying on the next resolve (both from the verdicts below):
`NsdServiceInfo.network` on API 33 and later; below that, the `ConnectivityManager` network with
`TRANSPORT_WIFI` (`ACCESS_NETWORK_STATE`, ADR-0009, decision 11). `INTERNET` and
`CHANGE_WIFI_MULTICAST_STATE` are declared in the manifest and `INTERNET`'s `tools:node="remove"`
deleted; `transport-backend-cct` is excluded from billing in the same commit, with the R8
`-dontwarn` for `com.google.android.datatransport.cct.**` (ADR-0009, decision 12).

**The Player's phone's QR** carries a content description naming its purpose, and *Copy the code*
and *Share the code* beside it put the same payload, as one line of text, on the clipboard or in
Android's share sheet (D10). *Copy the code* marks the clip sensitive
(`ClipDescription.EXTRA_IS_SENSITIVE`, Android 13 and later), so the system's clipboard preview does
not show the token. Emulators pair through that text route too, so the debug build no
longer needs a QR text field of its own.

**For emulators,** `app/src/debug/` adds a field for an address and port instead of NSD, so a reading
can be taken where a multicast cannot reach, and a switch that skips the `MulticastLock`, for R2's
lock-off reading on the Redmi. Neither exists in the release build.

### Two questions this checkpoint answers first, with their verdicts written now

- **Can a Keystore key serve both ends of TLS on every API level from 26?** Read as a handshake between
  `urgent-api26` and `pixel-api36`, each as both roles in turn. **Verdict 1:** it handshakes both ways
  → as designed. **Verdict 2:** it fails on some level → that level's key is made in software, stored
  in the no-backup directory, with a certificate made by Bouncy Castle (MIT), and the same pinning; the
  Keystore stays wherever it works. **Verdict 3:** it fails everywhere → ADR-0009's fallback, a
  shared 256-bit secret from the QR and AES-GCM framing, gets an amendment to ADR-0009 before any of
  it is written.
- **Do two emulators find each other by NSD?** Read on `pixel-api36` and `urgent-api26` under emulator
  37.2.13. **Verdict 1:** both directions → readings use NSD. **Verdict 2:** only the newer images
  join the shared Wi-Fi → the floor's readings go through the debug address field and `adb forward`,
  and NSD is read on newer images and on the real phones.

### The verdicts, taken 2026-11-23

Both read with a throwaway app on emulator 37.2.13, headless, its code on the branch
[`spike/phase-g-link`](https://github.com/maks-sredniawa/darts-scorer/tree/spike/phase-g-link)
(`spike/`, one Activity driven by `adb shell am start` extras, logging under `LinkSpike`), which is
never merged. The excerpt below is the part C carries over.

**Keystore keys and mutual TLS: verdict 1, as designed, with one condition on the key.**

- `urgent-api26` and `pixel-api36`, each as both roles in turn, a Keystore EC P-256 key on each
  side, client authentication required, each side pinned to the other's SHA-256 fingerprint, the
  connection carried by `adb forward` because API 26 is not on the shared Wi-Fi (below): both
  directions handshake, `TLSv1.2 TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256`, and a line goes each way.
  Pinned to the wrong fingerprint, the camera side refuses the handshake
  (`SSLV3_ALERT_CERTIFICATE_UNKNOWN` on the other end).
- The same handshake inside one app, two Keystore keys, on API 26 (TLS 1.2), 30, 36 and 37 (TLS 1.3,
  `TLS_AES_128_GCM_SHA256`); and across emulators over the shared Wi-Fi between 33, 36 and 37 (TLS
  1.3), found by NSD.
- **The condition: the key must allow `KeyProperties.DIGEST_NONE` besides `DIGEST_SHA256`.** The
  platform's TLS hashes the handshake itself and asks the Keystore to sign the digest, so a key
  limited to `DIGEST_SHA256` fails every handshake, on API 26 and 36 alike, with
  `INCOMPATIBLE_DIGEST`: on 36 keystore2 (API 31 and later) logs `Digest 0 was specified, but not
  authorized by key`, on 26 the older keystore returns the same error, and the TLS layer sees only a
  closed connection. With `DIGEST_NONE` added, every reading above passes. The key is
  still sign-only and never leaves the Keystore; no software key, no Bouncy Castle.

```kotlin
KeyGenParameterSpec
    .Builder(alias, KeyProperties.PURPOSE_SIGN)
    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
    .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
    .build()
// TLS: an X509KeyManager returning that PrivateKeyEntry's key and its one self-signed certificate,
// an X509TrustManager that throws unless chain[0]'s SHA-256 is the pinned one, and
// SSLServerSocket.needClientAuth = true on the Mounted camera.
```

**NSD between emulators: verdict 2, only the newer images join the shared Wi-Fi.**

| Image | Wi-Fi address | Shared Wi-Fi | NSD both ways with `pixel-api36` | Lock taken by the rule |
| --- | --- | --- | --- | --- |
| `urgent-api26` | 192.168.232.2 | no, its own router | no, either way | yes |
| `small-api30` | 10.0.2.16, the same as `pixel-api36`'s | no | no, either way | yes (extension < 7) |
| `urgent-api33` | 10.0.2.18 | yes | yes, then TLS 1.3 | yes (extension < 7) |
| `pixel-api36` | 10.0.2.16 | yes | — | no |
| `pixel-api37` | 10.0.2.17 | yes | yes, then TLS 1.3 | no |

So, as the verdict says, the floor's readings go through the debug address field and `adb forward`,
and NSD is read on the newer images and on the real phones. What the table adds:

- **`urgent-api33` is the emulator for the `MulticastLock`.** It joins the shared Wi-Fi and is below
  T extensions 7, so the rule takes the lock there and its acquire and release can be read in `adb
  logcat`. The emulator cannot show that the lock is *needed*: with the lock off, `urgent-api33`
  still answered `pixel-api36`'s discovery. That half stays with the Redmi in R2, through the debug
  switch that skips the lock.
- **The first connect after a resolve can leave by the wrong interface.** On `urgent-api33` the
  emulator's `eth0` sits on 10.0.2.15/24 beside `wlan0`, and the first connect to the resolved
  10.0.2.16 went out of `eth0` and failed `EHOSTUNREACH`; the next resolve, a few seconds later,
  connected. C connects through the Wi-Fi `Network` (`Network.socketFactory`) rather than the
  default route, `NsdServiceInfo.network` on API 33 and later and the `TRANSPORT_WIFI` network from
  `ConnectivityManager` below, and retries on the next resolve; a real phone whose default network
  is mobile data has the same shape.

**Acceptance (C):**

- Two emulators pair through the text route, the code copied on the Player's phone and pasted on
  the camera (with `adb shell input text` where the two emulators share no clipboard); each shows
  the other as paired; a capture through a
  debug button returns a Photo; a packet capture of the camera emulator (`emulator -tcpdump`) shows
  TLS records and no plaintext JPEG marker (`FF D8 FF`).
- A third emulator running the app, unpaired, on the same virtual Wi-Fi: its connection to the camera
  fails the handshake, and a camera it advertises is not accepted by the Player's phone. Both visible
  in `adb logcat` under the link's tag.
- **Both pairing routes with TalkBack on** (D10), on both phones: TalkBack reads the QR's content
  description; *Copy the code* and *Share the code* are reachable and labelled, and the share sheet
  opens with the one-line payload; pairing completes by the QR (on the real phones, R2) and by the
  pasted text (on the emulators and on the real phones), each with TalkBack on throughout; on both
  phones the paired state (*Connected* on the camera, the camera listed as paired on the Player's
  phone) is announced politely without moving focus (WCAG 2.2, 4.1.3); and the pins on both routes
  are the same kind of pin, read in `adb logcat` under the link's tag.
- Unpairing on one side: the other's next handshake fails and it says *Pair again*.
- Restarting either app, and turning the camera emulator's Wi-Fi off and on: the link comes back
  without pairing again.
- A backup and restore (`adb shell bmgr backupnow` and `bmgr restore`) brings back the preferences
  and no pairing: the restored app is unpaired and says so.
- On `urgent-api33` as the Mounted camera, with `pixel-api36` as the Player's phone, and then the
  other way round: the camera is found by NSD with the `MulticastLock` held (its acquire and release
  in `adb logcat` under the link's tag). `urgent-api26` does not join the shared Wi-Fi (the NSD
  question's verdict 2), so `urgent-api33` is the emulator below T extensions 7 that does. That the
  lock is *needed* is read on the Redmi (Android 11) alone, in R2, with the debug switch that skips
  it.
- `aab-permissions.py`: `INTERNET` and `CHANGE_WIFI_MULTICAST_STATE` expected; no `backend:`
  meta-data entry; `NEARBY_WIFI_DEVICES`, location and Bluetooth absent.
- `./gradlew assembleDebug -PreleaseShapedDebug` and `bundleRelease` build with the exclusion (R8
  finds no missing class), and on that build the tip's first billing call logs `BillingLogger`'s
  *Skipping logging since initialization failed.* in `adb logcat`.
- The tip, on the first internal-track build carrying the exclusion: prices load and the purchase
  sheet opens (R7).

## 5. The capture-and-score flow (D)

**Shape.** With a camera paired, the Visit screen shows the camera's state and *Take with the mounted
camera* beside *Take a Photo* and the Picker. A tap sends `CAPTURE`; *Taking the Photo…* until it
arrives; then the Photo goes through `MediaFiles` and phase 1's two passes, unchanged. Timeouts and
failures as ADR-0009, decision 8. *Next Visit* with a Mounted camera paired does not open the system
camera: the player taps the button they want.

**The debug half keeps every Photo the link delivers**, for gate A (§2). Phase 1 keeps a marked Visit
only with a result; with a Photo that came over the link, the debug build keeps it in `files/marked/`
even when no Board is found, since those are the Photos the gate most needs. It goes through
`ui/visit/KeepMarked.kt`'s seam, so a release build still keeps nothing.

**Announced, not only shown** (WCAG 2.2, 4.1.3 Status Messages). The state chip (*Looking for the
camera*, *Connected*, *Camera not found*) and *Taking the Photo…* are polite live regions
(`LiveRegionMode.Polite`); the failure line is assertive (`LiveRegionMode.Assertive`). While a
capture is in flight the button stays enabled, with *Taking the Photo…* as its state description, and
ignores a second tap, so TalkBack's focus never sits on a control that has just been disabled.

| Moment | What the player sees |
| --- | --- |
| Visit screen opens, camera paired | the state chip: *Looking for the camera*, then *Connected* or *Camera not found* |
| *Take with the mounted camera* | *Taking the Photo…*; the button ignores taps, still focusable, until it returns or fails |
| Photo arrives | phase 1's *Reading the Photo…*, then the result |
| No reply in 10 s, link lost, or `ERROR` | the reason in one line, *Try again*, and *Take a Photo* and the Picker as always |
| *Camera not found* | *Is the camera on the same Wi-Fi, with its screen open? Guest networks can keep phones apart; your phone's hotspot works instead* |
| Protocol versions differ | *Update Darts Scorer on both phones* |

**Acceptance (D):**

- On two emulators: a paired capture scores a Visit; the Visit count the tip reads goes up once
  (`AppPreferences`' `visits_scored`); the previous Visit's Photo is deleted as with a handheld one.
- Stopping the camera emulator's app mid-capture: the failure line within 10 s, then *Take a Photo*
  works.
- Process death on the Player's phone during *Taking the Photo…* (`adb shell am kill` with the app in
  the background): no crash on return, and no half-written Photo left after the sweep.
- TalkBack, on both phones, announces each state as it appears without moving focus: *Looking for
  the camera*, *Connected*, *Camera not found* and *Taking the Photo…* politely, the failure line
  assertively, on the Player's phone; *Waiting for your phone* and *Connected* on the camera screen.
  Focus stays on *Take with the mounted camera* through a capture, and it reads *Taking the Photo…*.
- On the debug build, a paired capture of a scene with no Board leaves a marked Visit in
  `files/marked/` whose `.json` reads `"boardFound": false`; a release build leaves nothing there.
- On the two real phones: R2 to R6.

---

## Tests

`PLAN.md` rule 3: each pure function that bounds a safety value gets its test here.

- **The local-peer check** (`isLocalPeer`): private, link-local and unique-local addresses accepted;
  public IPv4 and IPv6, loopback from outside the device, the unspecified address and a
  carrier-grade NAT address refused. Fails toward a Photo sent off the LAN.
- **The pairing proof**: a MAC under the wrong token, over swapped fingerprints, over a fingerprint
  other than the session's, or over a replayed nonce, is refused. Fails toward a stranger's phone
  being trusted.
- **The frame reader's bound**: a declared length over 16 MiB is refused before allocating, a
  truncated frame ends the connection, an unknown frame type ends it. Fails toward a peer crashing the
  app or exhausting its memory.
- **The QR payload**, one parser for the scanned QR and the pasted text (D10): a wrong version, a
  malformed fingerprint or a short token is refused; the pasted text's surrounding whitespace and line
  breaks are trimmed, and a QR and its text give the same payload. Fails toward pairing with garbage.
- **`PairingStoreTest`**: the pairing store's file is under `noBackupFilesDir`, never under `filesDir`,
  whose `datastore/` both backup rule files include whole. Fails toward a restored phone coming back
  in the camera role with stale pins. `BackupRulesTest` stays unchanged.

## Documents this phase amends

- ADR-0007 and ADR-0008, `CONTEXT.md` and `PLAN.md`: in checkpoint 0, the pull request carrying this
  file.
- The privacy policy, `play-app-content.md`'s prose and `store-listing.md`: E, before B.
- `aab-permissions.py`, `play-app-content.md`'s artifact table, `CLAUDE.md` and the manifest's
  comment: B and C, with the permissions they describe.
- `PLAN.md`'s *Asks* table: already carries the handheld `CAMERA` ask (D5), and marks phase 1's
  row as replaced by it from B, both from checkpoint 0.
- `CLAUDE.md`'s, `README.md`'s and the public `docs/index.md`'s *the photos never leave the phone*:
  C, which first declares `INTERNET`.
- android-starter's `ui/support/SupportHandoff.kt`, whose comment says the app declares no `INTERNET`:
  a comment-only change there, synced in with `sync-support.py`, since synced files are never edited
  in the app.

## Known gaps, deliberately

- **Client-isolated Wi-Fi.** Guest and public networks that keep devices apart break discovery and
  the link. The copy names the hotspot; detecting isolation would mean probing the network, for a
  case the hotspot already answers.
- **A phone with no Wi-Fi, or no Play Store,** cannot be a Mounted camera: the app arrives through
  Play, and the link is Wi-Fi.
- **Target SDK 37.** `ACCESS_LOCAL_NETWORK` will need an ask on both phones; owed by the bump, not
  here (ADR-0009, *Consequences*).
- **The Darts half of the bar from the mount** waits for the owner to throw again (R8); until then the
  phase can build B to E but not close.
- **The lens beyond the phone's own correction.** Only if R1 asks for it.

## Readings

`PLAN.md` rule 3: filled in as the phase runs, from the device, with the command that read it.

Device state they depend on: the emulators run under emulator 37.2.13 (shared virtual Wi-Fi from
36.5), driven with the `emulator-test` skill, and never an AVD on a non-standard port, which is
another session's. The real phones are the owner's phone and the Redmi Note 8 Pro on Android 11
(D9), both on the home Wi-Fi, the Redmi with the debug app already installed. The Redmi runs MIUI, so
before installing a new build check that `adb shell getprop persist.sys.miui_optimization` reads
`false` (`CLAUDE.md`, *Environment notes*), and keep it awake with `adb shell svc power stayon usb`
only for readings that are not about the battery.

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | Gate A: the Board half of the bar per mount position | `uv run --directory ml darts-ml predict --run <shipped run> --manifest <position manifest>` then `evaluate --predictions <file> --manifest <position manifest>` | |
| R2 | Pairing on the real phones: QR scanned at arm's length in room light, in how many tries; and once by the shared text with TalkBack on both phones (D10). Then the Redmi as the camera with the debug switch skipping the `MulticastLock`, and again with it held: *Camera not found* with it off and found with it on, or, found both ways, the lock recorded as not needed on Android 11 | by hand, counted; the lock in `adb logcat` under the link's tag | |
| R3 | Tap to scored result, on the home Wi-Fi: median and worst of 20 | the debug timing line on the Player's phone | |
| R4 | The Photo: the Board's long axis in px, and a Dart's Entry point sharp at 100% | the stored Photo, `adb exec-out run-as <id> cat files/photos/<uuid>.jpg > r4.jpg`, opened at 100% | |
| R5 | Battery and heat on the spare, one hour unplugged, screen dimmed, camera bound, the `MulticastLock` held (Android 11). **Verdict now:** under 15% an hour → as designed; over → the camera is bound only while the Player's phone is connected, and opened per capture if still over | `adb shell dumpsys battery` at the start and the end | |
| R6 | The link through the Player's phone's own hotspot, no router | by hand, a capture scored | |
| R7 | The tip with `transport-backend-cct` excluded: prices and the purchase sheet, on the internal-track build | by hand on the owner's phone | |
| R8 | The Darts half of the bar from the mount position, when the owner can throw again | `darts-ml predict` and `evaluate` on Visits taken with the Mounted camera | |
