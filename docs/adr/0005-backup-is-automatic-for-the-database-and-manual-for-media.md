# Backup is automatic for the database and manual for the media

## Context

All data lives on the device, so losing the phone means losing everything unless the user acts. There
is no server and there will not be one, so backup has to cost nothing to run.

Android Auto Backup covers this for free — but with two properties that shape the whole design:

- **A per-app quota of about 25 MB**, and **Android rejects the entire over-quota dataset.** It does
  not back up partially. So a pile of photos does not cost "just the photos": it silently takes the
  database down with it, and the user believes they have a backup when they have none.
- **It runs unattended**, on the OS's schedule, with no UI and nobody present. Nothing can be
  surfaced at backup time.

And one that is easy to miss: **Room runs in WAL mode**, so the most recent committed writes may live
only in the `-wal` sidecar. Copying the `.db` alone hands over a file missing the very data the user
asked to keep — and copying the sidecar alongside it is the other half of the same trap, because a
`-wal` captured mid-write restores *corrupt*.

## Decision

**Two levels.**

**Automatic**, through a custom `BackupAgent`: the database, checkpointed, plus the small media. It
is an agent rather than `backup_rules.xml` because **static include/exclude XML cannot checkpoint the
WAL**, and there is no way to express "flush first" in it. Registered with `fullBackupOnly="true"` —
declaring an agent without it puts the app on the key/value path, where the no-op `onBackup` is what
runs and the app silently backs up nothing.

**Manual**, in the app: a single zip the user keeps wherever they like, at a chosen scope. Records
only (small enough to mail yourself) or everything (which can be hundreds of megabytes).

**The archive carries a manifest**, read first on restore. Without one, the only way to find out an
archive is from a newer version of the app is to open its database and have Room throw — by which
point the live file has already been replaced.

**A restore extracts into a staging directory and swaps in only once the extraction has completed.**
Extracting straight over the live files — which is where they are going anyway — turns every
interrupted restore into total data loss.

## Alternatives

**Include photos in Auto Backup.** Trades a reliable small backup for an unreliable large one, and
the failure is silent.

**`backup_rules.xml` and no agent.** Cannot checkpoint. Produces backups that appear to work.

**Restore in place.** See above. A user restoring a backup is already having a bad day.

**A cloud sync of our own.** A server, a bill, a privacy policy with something in it, and an account
system — for a feature the platform already provides.

## Consequences

- "The small media" is bounded, not assumed small: thumbnails go newest first under a budget taken
  from the quota the transport reports, less a margin, with each file charged its tar overhead
  (`data/backup/AutoBackup.kt`). Enough of them can never push the set over the quota and take the
  database with it. A device-to-device transfer has no quota and carries every thumbnail and photo.
  "Newest" is the file's mtime, so the export carries it and a restore puts it back.
- Each attempt leaves a marker, and `onQuotaExceeded` overwrites it, so the Backup screen can say
  when Android last backed up, how many thumbnails were left out, or that the latest set was refused
  and which earlier one is the last that went through. Android reports no other transport failure,
  so the marker records an attempt that was not refused, not a confirmed upload. A device-to-device
  transfer writes none.
- The export is written to a `.part` and renamed on success, so an interrupted export leaves no file
  that looks shareable and is not. A restore writes each live file the same way, so a kill mid-swap
  leaves the old file or the new one whole, never half of one. The next restore sweeps the stray
  `.part` files, and neither the export nor Auto Backup counts them as media.
- Exports and restores share one process-wide lock, and Back is held while a restore runs: leaving
  the screen would not stop it, only hide it.
- A restore copies the new database to `app.db.part`, then **deletes the `-wal` and `-shm`
  sidecars**, then renames it over `app.db`; Auto Backup's `onRestoreFinished` does the same. Leaving
  a log belonging to a different database is a corrupt open on next launch.
- The restorer guards against **zip slip** — an entry named `../../databases/other.db`. The archive
  arrives from the user's storage, not from the app, so it is never trusted even though the app wrote
  the format.
- Media is merged rather than replaced on restore: filenames are UUIDs, so a collision means the same
  file, and keeping files the archive does not mention costs disk where deleting them costs photos.

## Amendment — 2026-11-12: platform Auto Backup, include-only, preferences only

Darts Scorer's first version keeps no records ([`phase-0.md`](../phase-0.md) §§ 2–3), and the one thing
it keeps besides its settings is the photos of the board, which the app exists to keep on the phone.
Both halves of the decision above lose their reason: there is no database whose write-ahead log needs
a checkpoint, and the media that needed a quota budget is the media that must not leave. So the custom
agent, the in-app export and restore, the Backup screen and sharing are gone, with
`scripts/upgrade-diff.py`, which read the export.

Platform Auto Backup takes over: `allowBackup="true"` and two rule files that say the same thing.
`res/xml/data_extraction_rules.xml` (`android:dataExtractionRules`) is read on Android 12 and later,
for `<cloud-backup>` and `<device-transfer>` alike, and `res/xml/backup_rules.xml`
(`android:fullBackupContent`) on Android 8 to 11. Both are **include-only** and name two things:
`datastore/`, the preferences, and AppCompat's locale record,
`androidx.appcompat.app.AppCompatDelegate.application_locales_record_file`, so the chosen language
follows the user below Android 13. Both are in the `file` domain; the record's name was read off a
device, not guessed (`phase-0.md`, R2). Include-only fails closed: a directory added later stays on
the phone until someone names it. `BackupRulesTest` holds each of the three sets to exactly those
two includes.

- Every preference key reaches the next phone, the tip's answer included (ADR-0007's 2026-11-12
  amendment). A key that is live state rather than a setting is judged at the read
  ([`optional-modules.md`](../optional-modules.md)).
- A device transfer carries no more than the cloud backup: a user's photos stay on the old phone.
- The over-quota failure above cannot happen: the set is a few kilobytes.

The custom agent's reasoning returns with a database. A feature that adds a table starts from the
decision above and the code at `e6409d8` (`AppBackupAgent.kt`, `data/backup/`, `ui/backup/`,
`ui/common/Share.kt`, `scripts/upgrade-diff.py`), because static XML still cannot checkpoint a WAL.
