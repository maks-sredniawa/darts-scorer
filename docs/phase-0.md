# Phase 0 — Darts Scorer is no longer the template: no items, no reminders, no database, and no photo reaches a backup

Sequence lives in [`PLAN.md`](PLAN.md); the live worklist lives in [`DOD.md`](DOD.md). This phase
amends four ADRs and reopens none: ADR-0001 (no database in the first version), ADR-0002 (no
database to hold the relative paths, and the photo directories never backed up), ADR-0003 (nothing is
scheduled) and ADR-0005 (platform Auto Backup replaces the custom agent). The strip itself follows
[`optional-modules.md`](optional-modules.md) module by module and is not restated here.
[`CONTEXT.md`](../CONTEXT.md) is owed nothing: the one new surface, the **Visit** screen, uses a term
already defined there.

**What closing this phase means.** Today the app is the template under a new name and mark: a list
of placeholder Items in a Room database, a daily reminder sweep, a custom backup agent that copies
the database and every photo directory off the phone, and export and restore screens. After this
phase it is a shell around one empty screen, the Visit screen, plus Settings and Help and feedback,
with the tip kept. It has no database, schedules nothing, declares no notification, boot or alarm
permission, and backs up only its preferences. The difference a device can be asked about: **a
file planted in `files/photos/` is gone after a backup-and-restore round trip, while a changed
setting comes back**, on both backup paths (Android 12 and later, and Android 8 to 11).

**`PLAN.md`'s paragraph is off in two places, said here first.**

- "The system camera and Photo Picker kept" holds for the plumbing only: `media/MediaFiles.kt`, the
  `FileProvider` and `file_paths.xml`, Coil and `exifinterface`. `file_paths.xml` keeps `camera/`
  alone: its `exports/` entry leaves at B with the backup zip and `preserved/` at C with Room, each
  with its paragraph in the file's comment. The two launchers that fire the
  camera and the picker live in the items editor, and leave with it. Phase 1 writes its own on the
  Visit screen, because the first tap on *Take a photo* is phase 1's ask (*Asks* in `PLAN.md`). The
  editor at `e376428:app/src/main/java/app/dartsscorer/ui/items/ItemEditorScreen.kt` is the
  reference to copy from.
- "Darts Scorer's palette and mark" already shipped in the bootstrap PR, and `DOD.md` ticks both.
  Nothing of it is left for this phase.

---

## 0. What this phase inherits

- **Nothing has shipped.** No Play entry exists, so every deletion here is free. This is the reason
  for doing it now (`optional-modules.md`, *Why before*). Once the first internal upload exists, it
  costs nothing yet either, because the internal track holds only the owner. From the door
  (phase 3) on, every table and permission removed is a migration or a Data safety change.
- **The tip stays.** ADR-0008 assumes it ("the app is on Play with a tip purchase") and `CONTEXT.md`
  defines it. Its one ask, though, lives on the Items screen and counts Items as its measure of use
  (`tip/TipAsk.kt`, `TIP_ASK_AFTER_ITEMS`). Both go with the Items, so the ask needs a new home and a
  new measure (§3).
- **The photo directories are already split by kind** (`photos/`, `thumbnails/`, `documents/` under
  `filesDir`). The capture `TakePicture` writes into lives in `cacheDir`, which no backup ever takes.
  The custom agent takes all three media directories today.
- **The asymmetry that shapes the phase: a cloud backup can be read off an emulator end to end, a
  device-to-device transfer only halfway.** `bmgr` drives the cloud-backup path and its restore. With
  D2D test mode it can also run Android 12's transfer backup on a Google Play image, which shows the
  files a transfer would carry, but nothing on an emulator restores one. The transfer half is
  therefore held by a test that each rule set is exactly the expected one (*Tests*), with a reading
  (R4) to try beside it.

## What is in, and what is deliberately not

**In:** the reminders module, the custom backup and its screens, the Items and the Room database
with its schema gate all deleted, in that order. Platform Auto Backup with include-only rules in
both rule files. A Visit screen as the home tab, holding the tip's one ask with Visits scored as its
measure. Every script, allowlist, policy and ADR the strip reaches, in the commit that strips the
code they describe.

**Not in, and each with a reason rather than a phase:**

- **The camera and picker launchers, and anything on the Visit screen beyond the tip card.** Firing
  the camera is the ask phase 1 owns, with its failure path (no camera app, a cancelled capture). A
  button added here would move that ask forward to "get it out of the way", which rule 4 forbids.
- **Visit history.** The first version stores none (`PLAN.md`). A table shipped unused becomes a
  destructive migration the day it is removed. A table added later starts at version 1 with its own
  ADR, and ADR-0001's schema gate comes back with it.
- **The `minSdk` decision.** `DOD.md` asks for it before the first upload, but the reason it gives is
  stranding installs, and until the door the only install is the owner's. The facts that decide it
  arrive in phase 1: the model runtime's own floor, and an inference time on a low-end emulator
  image. Phase 1 decides it, before the door. `DOD.md`'s item is reworded to say so.
- **A debug seeder.** With no records there is nothing to seed. The seed rows, `SampleData.kt`,
  `SeedReceiver` and its manifest entry go with the Items. If phase 1 wants a seeder (a sample board
  photo, for instance), it brings one, pointed at its own data.
- **The feature graphic.** Phase N (`DOD.md`).

**The tempting one is keeping Room "because history is coming".** It looks free: the code works, the
schema gate is green, and history is the obvious next feature. It is not free. Every Data safety
answer, backup rule and migration test would then defend a table that holds nothing, and its first
real schema would be a migration from a placeholder rather than a version 1 designed for Visits.
Deleting it costs one commit now and one `git show` the day it returns.

**The second tempting one is `noBackupFilesDir` for the photos.** It also keeps photos out of every
backup, without any XML. But `CLAUDE.md`'s house rule resolves every media path against
`filesDir`, and `MediaFiles.kt` writes there. Moving the photos splits that rule in two to save one
rule file the include-only form needs anyway. Include-only rules fail closed: a media kind added
later is excluded until someone includes it on purpose.

---

## Checkpoints

| | Checkpoint | Merges | Depends on |
| --- | --- | --- | --- |
| **A** | **Reminders out**: `work/`, the Settings section and its ask, four permissions | `refactor:` | — |
| **B** | **Backup out, Auto Backup in**: the custom agent, export and restore, sharing; include-only rules | `refactor:` | A |
| **C** | **Items and Room out, the Visit screen in**: the placeholder domain, the database and schema gate, the tip ask moved, `edge-to-edge.py` walking the shell | `refactor:` | B |
| **D** | **The surroundings**: `screenshots.py`, the four `aab-*.py` scripts against a local `bundleRelease`, `DOD.md` and `PLAN.md` | `docs:` / `chore:` | C |

One PR per checkpoint, each through the local review loop. Each leaves the app building, its tests
green and every shipped language complete.

**Why A before B.** Reminders are a pure deletion (`optional-modules.md`), and once they are out,
`device-gate.py`, the manifest's receivers and the WorkManager initializer comment are gone before B
edits the same manifest.

**Why B before C.** The custom backup exports and restores the database (`data/backup/`,
`WalCheckpoint.kt`), so Room cannot go while it stands. B removes the last reader other than the
Items.

**Why C carries the Visit screen.** Deleting the Items empties the home tab, and an app with no home
tab does not open. The screen arrives in the same commit as the deletion, so the app never stops
working.

**Why C carries `edge-to-edge.py`.** C deletes the screens the script walks (`HOME_TAB = "Items"`,
`SEED_WALK`), so left until D it fails on every emulator and the nightly stays red between the two
checkpoints. Rewriting it in the commit that deletes them keeps the nightly green and lets R6 pass
at C.

**No checkpoint cuts a release.** None of A to D is user-visible in a way worth a version: there
are no users. `refactor:`, `docs:` and `chore:` bump nothing, and the open release PR #3 (0.2.0)
stays as it is. Whether that PR is merged before Phase P is the owner's question, asked separately.

**No gate.** Nothing in this phase can veto it: every piece is a deletion the template has already
done once, written down in `optional-modules.md`. The one property that could fail silently is the
backup exclusion, and that is a reading at B (R3, R4, R5), not a gate.

---

## 1. A — Reminders out

`optional-modules.md`, *Reminders and WorkManager*, all of it, with these decisions made:

- **Nothing else runs in the background.** `Autostart.kt`, `BatteryExemption.kt` and the
  `com.miui.securitycenter` `<queries>` entry go too, and so does `device-gate.py`'s autostart half.
  The whole of `device-gate.py` goes if nothing is left in it.
- **Nothing else posts.** `NotificationPermission.kt`, `POST_NOTIFICATIONS`, `ic_notification.xml`
  and `res/raw/keep.xml` go.
- **The tip stays**, so `ACCESS_NETWORK_STATE` stays in `aab-permissions.py`'s EXPECTED with billing
  named as its only owner, and `play-app-content.md`'s row says the same.
- `ManifestWiringTest.kt` loses its boot, update and boot-permission cases here, and its share case
  in B, which empties it. The whole file goes in B.
- *Restore defaults* stops naming reminders: `settings_restore_hint` and
  `settings_restore_confirm_body`, in every shipped language.

**What the user sees:** Settings loses its *Reminders* section. Nothing else changes.

## 2. B — Backup out, Auto Backup in

`optional-modules.md`, *Backup export/restore*, all of it. Sharing goes too: nothing in phases 0 to 3
shares a file. That covers `Share.kt`, `ShareBook.kt`, the `ShareChosenReceiver`, the two `SEND`
`<queries>` entries and `revokeUnpickedShare()`. `ManifestWiringTest.kt` goes with its last case.
`BACKUP_FOLDER_URI` leaves `AppPreferences`. `file_paths.xml` loses `exports/` and the comment's
paragraph about it.

### The rules

`android:allowBackup="true"` stays. `backupAgent` and `fullBackupOnly` go, and two files arrive:

| File | Read by | Attribute |
| --- | --- | --- |
| `res/xml/data_extraction_rules.xml` | Android 12 and later: `<cloud-backup>` and `<device-transfer>` | `android:dataExtractionRules` |
| `res/xml/backup_rules.xml` | Android 8 to 11 | `android:fullBackupContent` |

Both are **include-only**, and both include the same two things:

- `domain="file" path="datastore/"`: the preferences.
- AppCompat's locale record, so the chosen language follows the user below Android 13. The
  file's exact name under `filesDir` is read off a device at B, not guessed. If it lives outside
  `filesDir`, its domain is whatever the reading shows.

Everything else is left out by not being named: `photos/`, `thumbnails/`, `documents/`, and any
directory a later phase adds. `<device-transfer>` carries the same includes as `<cloud-backup>`. A
transfer is the user's own new phone, but a photo is a photo, and one rule is easier to keep true
than two.

### Every key, asked what it means on the next phone

Exclusions are per file, and the preferences store is one file, so every key travels
(`optional-modules.md`). After A, B and C the store holds:

| Key | On the next phone |
| --- | --- |
| `theme_mode`, `material_you` | a setting, welcome |
| `onboarding_done` | true is right: the user has used the app. Phase 3 owns the first run and revisits this |
| `tip_asked` | welcome: the ask is once per person, not once per phone |
| `visits_scored` (C) | welcome: it measures use, and the use was real |

None of them is live state. If a later key is, it is judged at the read, per `optional-modules.md`.

**What the user sees:** Settings loses its *Backup* row. Android's own backup now carries their
settings to a new phone, and never their photos.

## 3. C — Items and Room out, the Visit screen in

`optional-modules.md`, *Room database and the schema gate* and *The placeholder domain*, all of it.
`DOD.md`'s standing schema gate is marked **parked**, its five points kept verbatim.
`file_paths.xml` loses `preserved/` and the comment's paragraph about it, leaving `camera/` as its
only path.

### `edge-to-edge.py`

SCENES, `TAB_BAR`, `HOME_TAB` (`"Visit"`) and `SEED_WALK` (gone) are rewritten against the shell in
this checkpoint, so the nightly walks screens that exist. `DOD.md`'s *Rewrite
`scripts/edge-to-edge.py`'s SCENES* is ticked here.

### The Visit screen

- Route `Visit` (a `data object`), the first `TopLevelDestination`, in `ui/visit/`. The tab label
  string is `tab_visit`, "Visit". Settings stays the second tab.
- **Phase 0 content: the tip card when it is due, and nothing else.** There is no copy to translate
  twice and no placeholder text that phase 1 has to remember to delete. A blank home tab on an
  internal build is honest: the screen exists so the shell has a home. Phase 1 fills it.

### The tip ask, moved

- `TipAskCard.kt` and the `items_tip_ask_*` strings move to `ui/visit/`. The strings become
  `visit_tip_ask_*`, in every shipped language, with their translations moved rather than redone.
- **The measure of use becomes Visits scored.** `TIP_ASK_AFTER_ITEMS` becomes
  `TIP_ASK_AFTER_VISITS`, still 10, and `tipAskDue` takes `visits`. Visits scored is an `Int`
  DataStore key, `visits_scored`, in `Keys.KEPT`, with an `incrementVisitsScored()` on
  `AppPreferences`. Phase 1 is its first writer: until a Visit can be scored the count stays 0, and
  the ask never comes due. That is correct, since no one should be asked to tip an app that cannot
  score yet.
- `VisitViewModel` takes over what `ItemsViewModel` held for the ask: `preferences`, `tipJar`,
  `installedAt`, `answerTipAsk`, and the `refresh()` when the ask is due.

**What the user sees:** the app opens on an empty *Visit* tab. Items, their detail and editor
screens, and the schema-mismatch screen are gone.

## 4. D — The surroundings

- `screenshots.py` rewritten against the shell, as far as it can before there is anything to
  screenshot.
- `aab-permissions.py` EXPECTED, as A to C left it, proven against a local `bundleRelease` together
  with the other three `aab-*.py` scripts.
- `DOD.md`'s *Make the artifact allowlists yours* stays open: R7 proves the AAB matches the lists,
  not that FORBIDDEN and EXPECTED_ORIENTATION are right for this app, and it is ticked once both are
  reviewed too.
- `DOD.md`: tick *Delete what the app does not need* and *Replace the placeholder domain*. Reword the
  `minSdk` item to "before the door". `PLAN.md`: tick Phase 0.

---

## Tests

Phase 0 introduces one safety value, and it is the property the app exists for: **a photo never
leaves the phone.**

- **`BackupRulesTest`** (JVM, new, at B) parses both rule files from `res/xml/`. It asserts that
  each is include-only (no `<exclude>`, so nothing is "everything but"). It asserts that
  `<cloud-backup>`, `<device-transfer>` and `backup_rules.xml` each equal the exact expected include
  set: `file:datastore/` plus the AppCompat locale record R2 reads. As a second line of defence it
  asserts that no include names `photos/`, `thumbnails/`, `documents/`, or the domain root. It fails
  towards the leak: any include added to any of the three, such as `domain="database"` or a new
  media kind, turns it red. It is what holds the device-transfer restore no emulator drives.
- **`TipAskTest`** (changed, at C): the same boundaries, with Visits in place of Items.
- **`AppPreferencesTest`** (changed): the reminder lines leave at A and the backup-folder lines at
  B. At C, `visits_scored` starts at 0, increments, and survives *Restore defaults* because it is in
  `KEPT`.
- **Deleted with their code:** `SchemaGateTest`, `ReminderChannelsTest`, `ShareBookTest`, the four
  `data/backup/` tests, `ItemDaoTest`, `MigrationTest`, `ShareChosenCallbackTest`,
  `ManifestWiringTest`.
- **CI's instrumented job keeps a test:** `MediaFilesTest` stays, because `MediaFiles.kt` stays.

## Documents this phase amends

| Document | Change | At |
| --- | --- | --- |
| ADR-0003 | dated amendment: nothing is scheduled; the module and its reasoning return together | A |
| ADR-0005 | dated amendment: platform Auto Backup, include-only, preferences only; the custom agent's reasoning returns with a database | B |
| ADR-0001 | dated amendment: no database in the first version; the schema gate is parked and returns with the first table | C |
| ADR-0002 | dated amendment. B: the photo directories are outside every backup by the include-only rules. C: no database holds the paths yet | B, C |
| `docs/privacy-policy.md` + `docs/play-app-content.md`, together | A: notifications and reminders. B: backup export, sharing, and what Android's backup now carries (settings only, never photos). C: anything naming stored records | A, B, C |
| `CLAUDE.md` | Stack (Room and WorkManager rows), house rules (the schema rule parked, "media paths in the DB"), Layout (`AppBackupAgent.kt`, `data/backup/`, `work/`), the `connectedAndroidTest` comment | A, B, C |
| `docs/RELEASING.md` | its two mentions of backup or schema, reread and corrected | B, C |
| `docs/DOD.md`, `docs/PLAN.md` | as §3 and §4 | C, D |

## Known gaps, deliberately

- **A device-to-device restore is not read on a device.** R4 reads which files a transfer would
  carry, if the image has the transport, but no emulator restores one. `BackupRulesTest` proves the
  transfer rules are exactly the expected set, and the cloud round trip is read (R3). Closing it
  costs two physical phones and a transfer.
- **The tip ask cannot be seen in this phase.** The count is 0 until phase 1 writes it, so phase 1
  takes the reading of the card on the Visit screen.

## Readings

Taken on the emulators (`emulator-test`), on the cloud path at `pixel-api36` and the Android 8 to 11
path at `small-api30`. Backup readings need the local transport: `adb shell bmgr enable true` and
`adb shell bmgr transport com.android.localtransport/.LocalTransport`. Read the transport back with
`bmgr list transports` before believing any round trip.

| # | Reading | Command | Result |
| --- | --- | --- | --- |
| R1 | A's artifact declares no notification, boot or alarm permission | `./gradlew bundleRelease` then `python3 scripts/aab-permissions.py <aab>` | |
| R2 | AppCompat's locale record: its file name and domain, below Android 13 | set a language on `small-api30`, then `adb shell run-as <pkg> find . -newer <marker>` | |
| R3 | Android 12 and later: a planted `files/photos/x.jpg` does not survive a round trip, a changed theme does | plant with `run-as`, `bmgr backupnow <pkg>`, `pm clear <pkg>`, `bmgr restore <token> <pkg>`, then `run-as ls files/photos` and the theme on screen | |
| R4 | A reading to try. Android 12 and later, device transfer: a planted `files/photos/x.jpg` is not among the files a transfer carries. If the image lists no D2D transport, the result records that and `BackupRulesTest` stands in | on a Google Play image at API 36 (`pixel-api36` if it is one): `adb shell setprop log.tag.BackupXmlParserLogging VERBOSE`, `adb shell settings put secure backup_enable_d2d_test_mode 1`, `bmgr list transports`, `bmgr transport com.google.android.gms/.backup.migrate.service.D2dTransport`, plant with `run-as`, `bmgr backupnow <pkg>`, then the files taken as logcat lists them | |
| R5 | R3 on Android 8 to 11 (`fullBackupContent`) | as R3, on `small-api30` | |
| R6 | C's shell opens on the Visit tab on every emulator, edge to edge, with nothing clipped | `python3 scripts/edge-to-edge.py` | |
| R7 | D: the four `aab-*.py` scripts pass on a local `bundleRelease` | each script against the AAB | |
