# A Mounted camera is a spare phone running this app, paired by QR and reached over the local network

Written 2026-11-22, before any code of phase G ([`phase-G.md`](../phase-G.md)). The owner decided
the camera, the permissions and the order on 2026-11-22, and the same day the handheld `CAMERA` ask,
when the paperwork merges and the Data safety answer (`phase-G.md` D1 to D9); those are recorded as
decided. Every other point below was recommended here and is decided as written when the pull request
that carries this ADR merges.

## Context

Phase G (`PLAN.md`) adds a camera fixed beside the Board, so a player stops walking to the Board
with the phone after every Visit. It is an addition the player turns on: the handheld path stays the
default.

Three constraints shape it:

- **The photos never leave the owner's own phones** (`CLAUDE.md`). There is no server, and there
  will be none for this.
- **The app has no network today.** `INTERNET` is removed from the merged manifest, and
  `scripts/aab-permissions.py` forbids it, because the privacy policy and the Data safety answers
  rest on its absence (ADR-0007, `docs/play-app-content.md`). Any link between two devices needs it
  back.
- **The app has no `CAMERA` permission.** The handheld path uses the system camera through
  `TakePicture`, which needs none (phase 1, `PLAN.md` *Asks*). A camera that takes a Photo on
  command, with nobody touching it, cannot go through another app's shutter button.

`PLAN.md` left the camera open between a network camera (RTSP or ONVIF), a spare phone and a GoPro
through Open GoPro. **The owner chose the spare phone on 2026-11-22**: an old Android phone running
this same app in a camera role, mounted beside the Board and facing its face. It costs nothing the
owner does not already have, it runs the app's own code on both ends, and it needs no third-party
protocol. One camera first; perhaps two later. One camera needs no merge of several Angles, so
**phase G comes before phase 2**, and two cameras wait for phase 2's merge.

The owner approved what that needs:

- `INTERNET` returns, **for the local link only**: phone to phone on the same Wi-Fi, never to a
  server;
- the spare phone holds `CAMERA` and takes its Photo through CameraX. That reverses `CLAUDE.md`'s
  *Photo Picker + `TakePicture` intent, not CameraX* for the camera role only;
- the privacy policy, the Data safety answers and `aab-permissions.py` change accordingly, before
  any build carries the permissions.

Two platform facts that this ADR has to answer, found while writing it:

- **Declaring `CAMERA` changes the handheld path.** `MediaStore.ACTION_IMAGE_CAPTURE`, which
  `TakePicture` launches, documents: *"if you app targets M and above and declares as using the
  CAMERA permission which is not granted, then attempting to use this action will result in a
  SecurityException."* One manifest serves both roles, so once the camera role exists, the handheld
  *Take a Photo* needs `CAMERA` granted on every phone. The owner decided that the handheld path
  stays as it is; on Android it cannot stay exactly as it is in the same app. Decision 11 takes the
  smallest change, which the owner chose on 2026-11-22.
- **Local network access becomes a runtime permission at target SDK 37.** Android 17 enforces
  *local network protection* for apps targeting API 37: `ACCESS_LOCAL_NETWORK`, a runtime permission
  in the *Nearby devices* group, covering outgoing and incoming TCP, UDP and `NsdManager`. At target
  SDK 36, which this app has, `INTERNET` grants it implicitly, and Google's guidance is not to declare
  or request it until targeting 37
  ([developer.android.com](https://developer.android.com/privacy-and-security/local-network-permission),
  read 2026-11-22).

## Decision

### 1. The camera is a spare Android phone running this app (owner, 2026-11-22)

A **Mounted camera** is a phone running Darts Scorer in its camera role, fixed beside the Board and
facing it. The phone the player holds, which scores, is the **Player's phone**. Both words go into
`CONTEXT.md`. One Mounted camera per Player's phone in phase G; the stored list of paired cameras is
a list from the start (one key, JSON, as `CLAUDE.md`'s house rule asks), so a second one needs no
migration.

### 2. Finding each other: NSD (mDNS/DNS-SD) on the LAN

The Mounted camera registers a service of type `_dartsscorer._tcp` with `NsdManager`, on a port the
system picks. Its service name is random and its TXT record carries only a protocol version and the
first 16 hex digits of its certificate's SHA-256 fingerprint, so a Player's phone with two cameras
can tell them apart and nothing on the LAN learns the phone's name or owner. The Player's phone
discovers and resolves with `NsdManager`.

- Both phones are on the same Wi-Fi. With no Wi-Fi at the Board, the Player's phone's own hotspot is
  that network: the Mounted camera joins it like any Wi-Fi, and no code changes.
- `NsdManager` does the multicast in the system's own process, so no `CHANGE_WIFI_MULTICAST_STATE`
  and no multicast lock.
- NSD needs no `NEARBY_WIFI_DEVICES` and no location permission at any API level. Those belong to
  Wi-Fi Direct, Wi-Fi Aware and the local-only hotspot, none of which is used.

### 3. The transport: the Mounted camera listens, the Player's phone connects and pulls

One TLS connection (decision 4) from the Player's phone to the Mounted camera, held while the
Player's phone has the Visit screen open, carrying small length-prefixed frames with no library on
either end:

| Frame | From | Carries |
| --- | --- | --- |
| `HELLO` | both, first | the protocol version, the role, the app's `versionName` |
| `PING` / `PONG` | Player's phone, every 5 s | nothing; three missed replies mark the link down |
| `CAPTURE` | Player's phone | a request id |
| `PHOTO` | Mounted camera | that request id, the JPEG (decision 6), its size, when it was taken |
| `ERROR` | Mounted camera | that request id and a code: camera not ready, permission withdrawn, busy |

- A frame is a 4-byte length, a 1-byte type and its body. A declared length over 16 MiB is refused
  before anything is allocated, and the connection closed.
- A protocol version the other phone does not speak ends the connection with a message on both
  screens: *Update Darts Scorer on both phones*. The two phones are updated by Play separately and
  can run different versions for days.
- The Mounted camera is the one that listens because it is the peer that stays put, on one screen,
  all evening; the Player's phone is the one that leaves the app and comes back, so it is the one
  that reconnects.
- **Only local peers.** The Player's phone connects only to an address NSD resolved, and only if it
  is a private, link-local or unique-local address (RFC 1918, 169.254/16, fe80::/10, fc00::/7). The
  Mounted camera accepts a connection only from such an address. The app makes no DNS lookup and
  holds no URL. That check is a pure function with its own test (`phase-G.md`, *Tests*), and it is
  what stands where the forbidden `INTERNET` stood: the permission now exists, so the guard on where
  the app talks is the code's.

### 4. Pairing and trust: a QR on the Player's phone, mutual TLS pinned to both phones

A stranger's phone on the same Wi-Fi must neither trigger a capture nor read a Photo, and nothing on
the LAN may read a Photo in transit.

- **Each phone holds an EC P-256 key in the Android Keystore**, made once, with the self-signed
  certificate the Keystore issues for it. A Keystore key cannot be exported and is never in a
  backup.
- **The Player's phone shows a QR** on its *Add a mounted camera* screen: a protocol version, its own
  certificate's SHA-256 fingerprint and a fresh 128-bit pairing token. The token exists in memory
  only, while that screen is open, and is used once.
- **The Mounted camera scans it** with the camera it already has (decision 9), pins the Player's
  phone's fingerprint and starts advertising.
- **The Player's phone connects in pairing mode**: it presents its own certificate, accepts the
  camera's certificate for this one connection, sends a random nonce, and gets back
  `HMAC-SHA256(token, "pair" ‖ nonce ‖ camera fingerprint ‖ player fingerprint)`, the camera
  fingerprint being the one this TLS session actually presented. It pins that fingerprint only if
  the MAC checks out, then forgets the token.
- **From then on both ends are pinned**: TLS with client authentication required, each side
  accepting only the one certificate it pinned. A stranger's phone fails the handshake; a phone that
  pretends to be the camera during pairing cannot compute the MAC without the token, which only
  someone who saw the Player's phone's screen has; a relay between the two fails because the MAC
  binds the fingerprint the Player's phone saw.
- TLS 1.3 where the platform has it (Android 10 and later) and TLS 1.2 with ECDHE and AES-GCM below,
  through the platform's own `SSLSocket`. No crypto library is added.
- **Unpairing** is a row on either phone; it deletes that pin, and the other phone fails its next
  handshake and says *Pair again*.
- **The pins, the camera list and the role live in a store outside Auto Backup**: a DataStore file
  the backup rules do not name, so `BackupRulesTest`'s include-only check keeps it out. A restored
  phone starts unpaired, which is right, since its Keystore key did not travel with it.

### 5. What triggers a capture: a button on the Player's phone

After a Visit, the Visit screen offers *Take with the mounted camera* beside *Take a Photo* and the
Picker, whenever a Mounted camera is paired. One tap sends `CAPTURE`; the Photo comes back and
enters the same path as a handheld Photo. Nothing on the Mounted camera needs touching. Detecting a
thrown Dart, a Visit's end or the darts being pulled is out of scope.

### 6. The Photo: a JPEG, 2048 px on the long edge, never stored on the Mounted camera

- CameraX's `ImageCapture` takes it into memory. The Mounted camera encodes it with `MediaFiles`'
  encoding for the `photos` kind, to bytes rather than to a file: 2048 px on the long edge, rotation
  baked in, every metadata field stripped, GPS included. Quality 90 rather than the stored kind's 85,
  because the Player's phone re-encodes it.
- **Nothing is written to the Mounted camera's storage.** The bytes are sent and dropped, and a
  failed send is dropped too: the Darts are still in the Board, so the player taps again.
- The Player's phone writes it through `MediaFiles` as the `photos` kind, exactly like a handheld
  Photo, so phase 1's rules for keeping and deleting a Photo (`phase-1.md` D2) apply unchanged.
- Full resolution is not sent: about 4 MB at 12 MP against about 0.5 MB, for a model that reads a
  640 px crop of the Board, and the Player's phone downsamples to 2048 px anyway.

### 7. The lens: the phone's main camera, straightened by the phone if it offers to, nothing else

The homography assumes straight lines (ADR-0008). A phone's main (1×) camera is close to
rectilinear, and most phones already correct what is left in their still pipeline.

- The Mounted camera uses CameraX's default back camera and refuses an ultra-wide one.
- Where Camera2 reports `DISTORTION_CORRECTION_MODE` (Android 9 and later), the capture asks for
  `HIGH_QUALITY` through `Camera2Interop`.
- Nothing is straightened on the Player's phone. Whether that is enough is a reading, not an
  assumption: the Board's fit error on the Mounted camera's Photos against the bar's Board half
  (`phase-G.md`, checkpoint A).

### 8. When the link drops

- **The Player's phone shows the camera's state** on the Visit screen: *Connected*, *Looking for the
  camera* or *Camera not found*. It looks again when the Visit screen opens and at each tap; nothing
  runs in the background.
- **A capture waits at most 10 s.** On a timeout, a lost connection or an `ERROR`, the Visit screen
  says why, offers *Try again*, and keeps *Take a Photo* and the Picker beside it, so a Visit is never
  lost to the link (the same rule as phase 1's D6).
- **The Mounted camera keeps listening.** It shows *Waiting for your phone* or *Connected*, and a
  dropped Player's phone simply reconnects. A Photo half sent is dropped on both ends.
- A network that keeps its devices apart (client isolation on guest or public Wi-Fi) looks like
  *Camera not found*; that message names the hotspot as the way round.

### 9. Choosing the role: a Settings row, then a screen of its own

- Settings gains **Mounted camera**, opening a screen with two choices: *Add a mounted camera*
  (this is the Player's phone: shows the QR, lists the paired camera, unpairs it) and *Use this phone
  as the mounted camera*.
- The second asks for `CAMERA`, opens a full-screen camera screen with a preview for aiming, and
  scans the QR there. The role is stored (by enum name, in the store of decision 4), so a phone left
  in the camera role opens straight into that screen until *Stop being a camera* is pressed.
- Nothing changes for a player who never opens the row, apart from decision 11.

### 10. Battery and the screen while mounted

- The camera screen keeps the screen on with `FLAG_KEEP_SCREEN_ON` while it is in front, and nothing
  else: no `WAKE_LOCK`, no foreground service, no notification (ADR-0003's *nothing posted* holds).
  Leaving the screen or locking the phone stops the camera role until it is opened again.
- After 30 s without a touch the screen dims to the window's lowest brightness and hides the preview,
  leaving a small dark status line that moves now and then, so an OLED panel does not burn in. A
  touch brings the preview back.
- CameraX stays bound while the screen is open, so a capture does not wait for the camera to open
  and its exposure to settle. The copy recommends a charger; the drain without one is a reading
  (`phase-G.md`), and the verdict is written before it is taken.

### 11. Permissions, by API level

| Permission | Kind | Phones | Asked |
| --- | --- | --- | --- |
| `INTERNET` | normal, granted at install, API 26–36 | both | never |
| `ACCESS_NETWORK_STATE` | normal; already merged by billing | both | never; now also read to tell Wi-Fi from none |
| `CAMERA` | runtime, API 26–36 | the Mounted camera; and, see below, the handheld path | at *Use this phone as the mounted camera*; and at the first *Take a Photo* |
| `ACCESS_LOCAL_NETWORK` | runtime, *Nearby devices* group, only when targeting API 37 | both | **not declared at target SDK 36**, as Google's guidance says; the target-SDK bump that reaches 37 owes its ask, on both phones, at pairing |
| `NEARBY_WIFI_DEVICES`, `ACCESS_FINE_LOCATION`, `BLUETOOTH_*` | runtime | — | never: forbidden in `aab-permissions.py` |
| `CHANGE_WIFI_MULTICAST_STATE`, `WAKE_LOCK`, `FOREGROUND_SERVICE*` | normal | — | never: not declared |

- **`<uses-feature>` for the camera is declared, at `required="false"`**, for both
  `android.hardware.camera` and `android.hardware.camera.autofocus`. `CAMERA` implies both as
  required, and Play would then hide the app from every phone without a camera, for a role few use.
  `aab-permissions.py`'s `EXPECTED_FEATURES` lists both at `False`.
- **The handheld path asks for `CAMERA` once declared** (Context): at the first *Take a Photo*, with
  a line saying why; a denial leaves the Picker, with phase 1's
  *No camera app* banner reworded for it. **The owner decided this on 2026-11-22** (`phase-G.md` D5),
  over a second app for the camera role (Alternatives).

### 12. `INTERNET` returns, and the billing library's logging stays unable to leave

With `INTERNET` declared, Google's `datatransport`, which the Play Billing Library brings, would have
a route off the phone for the first time (ADR-0007). The decision is that it still does not:

- **`com.google.android.datatransport:transport-backend-cct` is excluded** from the billing
  dependency in Gradle. It is the only backend `datatransport` has, registered through a
  `backend:` meta-data entry in the merged manifest; without it, `datatransport` has nowhere to send
  and drops what it logs.
- `aab-permissions.py` gains a check that no `backend:` meta-data entry is in the artifact, so a
  dependency bump that brings a backend back fails the upload, as a merged `INTERNET` did before.
- **The tip is read working afterwards**, prices and the purchase sheet, on the first internal-track
  build that carries the exclusion. If billing fails without the backend, the exclusion is reverted
  and the Data safety form declares what the library collects instead (`phase-G.md`, the readings'
  verdicts).

ADR-0007 gains a dated amendment saying so.

### 13. The Play declarations it triggers

- **Data safety stays *No data collected***, on Play's own end-to-end-encryption exemption: *"User
  data that is sent off device, but that is unreadable by you or anyone other than the sender and
  recipient"* (support.google.com, answer 10787469, read 2026-11-22). A Photo leaves the Mounted
  camera only over decision 4's TLS, whose keys exist only on the two phones, and goes to nobody
  else. This makes the encryption load-bearing for the answer, not a nicety. The owner chose this
  answer on 2026-11-22 (`phase-G.md` D7) over declaring *Photos: collected, for app functionality,
  not shared*.
- **The privacy policy** loses *the app has no permission to use the internet* and gains what is
  true: the app uses the local network for one thing, the Mounted camera, between the player's own
  phones; it never connects to a server; the camera permission is for the Mounted camera and the
  system camera.
- **The store listing's** *does not request the internet permission* goes, in every language, and its
  *PERMISSIONS* block names the camera and the local network.
- **No permission declaration form**: neither `CAMERA` nor `INTERNET` is on Play's restricted list,
  and no foreground service is declared.
- **Content rating and target audience are unchanged**: the link is between one player's own phones,
  so no users interact and no content is shared between them. `play-app-content.md` records that
  reasoning.

## Alternatives

**The camera** (decided by the owner; recorded for the reasons):

- **A network camera over RTSP or ONVIF.** A still image over a standard protocol, but each brand
  bends ONVIF its own way, most ship with cloud apps and default passwords, and RTSP sends frames in
  clear on the LAN. It also means buying hardware before a reading.
- **A GoPro through Open GoPro.** A documented API, but it pairs over Bluetooth Low Energy and then
  serves over the camera's own Wi-Fi access point, which takes the Player's phone off its normal
  Wi-Fi, and needs Bluetooth permissions on every API level. Expensive for a mount.

**Finding each other:**

- **Wi-Fi Direct.** Works with no router, but needs `NEARBY_WIFI_DEVICES` on Android 13 and later
  and fine location, with location switched on, on Android 8 to 12; it shows a connection invitation
  that one side has to accept, and vendor implementations differ. The hotspot gives the no-router
  case without any of that.
- **Nearby Connections.** Handles discovery and transport over Bluetooth and Wi-Fi, but it is part of
  Google Play services: closed code carrying the Photos, Bluetooth and Wi-Fi permissions on every API
  level, location on older ones, and no app at all on a phone without Play services, which an old
  spare phone may be.
- **Bluetooth alone** (`PLAN.md` named it): RFCOMM moves a 0.5 MB Photo in seconds and BLE in tens of
  seconds, and both need the *Nearby devices* or location permissions. Kept only as a later option
  for a phone with no Wi-Fi.
- **An address typed or in the QR, no discovery.** Simplest, but a DHCP lease that changes breaks the
  pairing with no way to tell the player why. NSD costs one system service and finds the camera
  wherever it landed. A debug-only address field remains for emulator readings.

**The transport:**

- **An HTTP server on the Mounted camera** (NanoHTTPD, BSD-3-Clause, or Ktor, Apache-2.0). Familiar,
  but with mutual TLS in front of it, HTTP adds headers and a library and nothing the five frames
  need.
- **The Player's phone listening and the Mounted camera connecting.** Works as well; it puts the
  reconnecting on the peer that never leaves its screen, and makes the camera, not the player's phone,
  the one that must find the other.

**Pairing and trust:**

- **A short code typed on one phone.** Six digits are 20 bits: an HMAC under them can be broken
  offline by anyone who recorded the exchange, so it needs a password-authenticated key exchange
  (SPAKE2, J-PAKE), which means a crypto library and protocol code to get right. The QR carries 128
  bits and needs neither.
- **The QR shown on the Mounted camera, scanned by the Player's phone.** The Player's phone has no
  camera of its own in the app (it uses the system camera), so it would photograph the QR through
  `TakePicture` and decode the still: a clumsier step, on the phone the player holds.
- **A shared secret and the app's own encryption** (AES-GCM keyed from the QR, no TLS). Possible
  with `javax.crypto` alone, and kept as the fallback if Keystore keys cannot serve TLS on some API
  level (`phase-G.md`, checkpoint C's verdicts). It loses to TLS because TLS's handshake, replay
  protection and record layer are not code this app has to own.
- **No pairing: trust the Wi-Fi.** Anyone on a shared or guest network could trigger the camera and
  read a Photo of the owner's home. Rejected.

**The trigger:** a button on the Mounted camera, a Bluetooth shutter remote, or detecting a Visit
from frames (which is a live camera view, against `PLAN.md`'s *Not in this plan*). The button on the
Player's phone is the one the player already holds.

**The lens:** straightening on the Player's phone from a calibration of each camera (a checkerboard,
or the Board's own rings). Real work, for a distortion the phone's own pipeline mostly removes; it
waits for a reading that asks for it.

**The role:**

- **A question at first run.** Every player would be asked about a feature few use.
- **A second launcher icon** (an `activity-alias`, enabled when the role is chosen). One more moving
  part for a role that a Settings row reaches in two taps.
- **A second app for the camera role** (its own `applicationId`, a second module in this repo).
  It is the only way to keep the handheld path's *no `CAMERA` permission* exactly as it is, because
  the main app would then gain `INTERNET` alone. It costs a second Play listing, its own closed test,
  release pipeline and store paperwork, and the owner decided on one app, and on 2026-11-22 on the
  handheld ask over this (`phase-G.md` D5).

**The billing library's logging:** declare it in Data safety and let it send (the honest fallback,
decision 12), or remove the tip (ADR-0007's own *no tip at all*). Excluding the backend keeps today's
promise at the cost of one Gradle line and one check.

## Consequences

- **The app has a network permission for the first time.** What keeps the photos on the owner's
  phones moves from a permission's absence, which the artifact proved, to code: the local-peer check,
  the pinned TLS, and the backend exclusion with its check. `aab-permissions.py` moves `INTERNET`
  and `CAMERA` from *forbidden* to *expected* and forbids the permissions this ADR rules out.
- **One more permission ask on the handheld path** (decision 11). Phase 1's ask table and its *No
  camera app* banner change.
- **Two phones on two app versions** have to talk: the protocol is versioned from its first frame,
  and an old camera tells the player to update rather than failing quietly.
- **Target SDK 37 costs a runtime ask on both phones.** The Mounted camera accepts incoming
  connections, which no system picker covers, so `ACCESS_LOCAL_NETWORK` is asked at pairing then.
  Play's deadline for target 37 is the trigger; nothing is declared before it.
- **New dependencies**: CameraX (`camera-core`, `camera-camera2`, `camera-lifecycle`, Apache-2.0) and
  ZXing's `core` (Apache-2.0) for making and reading the QR, both on the Credits screen through the
  dependency list. No Play services part, no crypto library, no server library.
- **Nothing is learnt from the Board between Visits.** The camera is fixed, so a homography fitted
  once could be reused; it is fitted per Photo, as ADR-0008 does, because a bumped mount would
  silently invalidate a cached one (`phase-G.md`, *The tempting one*).
- **Client-isolated Wi-Fi does not work** without the hotspot, and a phone without Wi-Fi cannot be a
  Mounted camera.
- The privacy policy, `play-app-content.md`'s Data safety reasoning and the store listing change one
  release ahead of the build that first carries the permissions (`phase-G.md` D6, checkpoint E);
  `aab-permissions.py`, `play-app-content.md`'s artifact table, `CLAUDE.md`'s stack table and the
  manifest's comment on `INTERNET` change with it.
  The comment in the synced `ui/support/SupportHandoff.kt` that says the app declares no `INTERNET`
  is android-starter's to change, through `sync-support.py`.
