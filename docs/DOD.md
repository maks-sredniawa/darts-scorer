# Definition of done — what is still open

The **live checklist**. Keep it short: when an item closes, tick it, write the *result* into whatever
long-form record you keep, and delete the detail from here. A session should be able to pick up the
work by reading this file alone.

## The standing schema gate — parked until the first table

**Parked** (ADR-0001's 2026-11-12 amendment): the app has no database, so there is no
`APP_SCHEMA_VERSION` to change, and `scripts/schema-gate.py` passes with nothing to gate. It comes
back the day a feature adds a table, with the five points below as they stand.

**An update must migrate an existing install without losing anything** (ADR-0001). This item does not
close. Whenever `APP_SCHEMA_VERSION` changes, all five hold before the release goes out:

1. `MIGRATION_x_y` written **and registered in** `APP_MIGRATIONS` for every step. A migration Room
   never runs is not a migration, and nothing about the build complains.
2. The exported `app/schemas/*/N.json` committed — every later migration is transcribed from it,
   never from the entity classes.
3. `SchemaGateTest` extended, so the **launch gate** is proven to let the upgrade through. Every
   migration test opens the database directly and walks past that gate; this assertion is the only
   thing standing in front of it.
4. A migration test proving the **rows survive** — read values back, do not merely assert nothing
   threw. `runMigrationsAndValidate` compares *shapes* and is blind to a table emptied by a cascading
   `DROP`.
5. **An actual upgrade watched on a phone**: install the previous build, put real data in it, install
   the new one over the top, confirm the app opens and the data is there.
   `./gradlew assembleDebug -PreleaseShapedDebug` is how to do this without touching a Play install —
   it is minified *and* `BuildConfig.DEBUG == false`, so migrations are registered rather than the
   destructive fallback. ⚠️ **Both halves are load-bearing**: a plain debug build takes the fallback
   and proves the opposite of what you wanted.

`scripts/schema-gate.py` enforces 1–3 mechanically in CI. Items 4 and 5 are yours.

## Phase M1 — the data

[`phase-M1.md`](phase-M1.md). Runs alongside phase P. Phase 1 is built alongside M2 and closes
only on a model that met this phase's bar.

- [x] **Answer the six decisions** at the top of `phase-M1.md`, the bar (D1) first: it is set before
      any training, never after a result. All six taken as recommended on 2026-11-13.
- [ ] **The pilot is the gate.** Capture session s01 taken and labelled in rounds a, b and c; R1's
      verdict written in before any other Capture session is taken.
- [ ] **Capture and label the other 17 Capture sessions**, each through `darts-ml check`; the six
      held-out ones frozen by `ml/splits/held-out.toml`, with at least 60 Visits B2 counts.
- [x] **DeepDarts in, or out** (D5): in, from DataPort with a free account; R2 and R3 in
      `phase-M1.md`.

## Phase M2 — the model

[`phase-M2.md`](phase-M2.md). A to E run on DeepDarts alone, alongside M1; F and G wait for M1's freeze.

- [x] **Answer the six decisions** at the top of `phase-M2.md`. All six taken as recommended on 2026-11-17.
- [x] **The gate (A):** verdict 1 on 2026-11-17, train on the GPU; R1 in `phase-M2.md`.
- [x] **The training code (B):** `darts-ml train` and `predict`, the decoder and both passes, the
      fences and their tests; the Entry channel stays at stride 4 (`phase-M2.md` §2).
- [x] **The Board (C):** found on every val and test Photo, wire medians 0.27 to 0.40 mm; 512 px
      and from-scratch weights stay (D's gap work later moved the model to 640 px, R3). R2 in
      `phase-M2.md`.
- [x] **The Darts (D):** read on test the paper's way, 75.8% face-on and 39.3% angled against the
      paper's 94.7% and 84.0%, with at most three Entry points kept per Photo. R3 in `phase-M2.md`.
- [x] **Close D's gap before E:** the Entry output at stride 2, a penalty on false tips around
      real ones, and 640 px, read the same way: 81.8% face-on and 48.0% angled on test against D's
      75.8% and 39.3%, close pairs as two 18 of 74 (R3, 2026-11-19).
      E converts `2026-11-19-darts-640-s2-ring-ext`, 30 more epochs from that run: val exactly right
      69.2% against 66.5% (`phase-M2.md` §4); on test it reads level with it (R3).
- [x] **Export (E):** LiteRT 1.4.2, bundled, through its Interpreter API; 0 of 1,070 val Visits
      scored differently from PyTorch. Chosen over ONNX Runtime and LiteRT 2.3.2 for adding no Play
      part and nothing to the manifest. ADR-0008 amended on 2026-11-19, MPL-2.0 allowed unmodified
      and credited. R4 in `phase-M2.md`.

## Phase 1 — one Photo scored on the phone

[`phase-1.md`](phase-1.md). Built alongside M2; closes only on a model that met M1's bar (E).

- [x] **Answer the six decisions** at the top of `phase-1.md`. All six taken as recommended on
      2026-11-20.
- [x] **The gate (A):** the Kotlin pipeline gives the Board and Darts that Python's `locate()` gives,
      as `darts-ml phone-parity` writes them out, on DeepDarts' val Photos written through
      `MediaFiles` (`phase-1.md` §1, R1). 2026-11-20: 200 of 200 on API 36 and API 26, worst
      crossing 0.005 mm; the Credits ADR-0008 asks for came with it. Its second question, the
      `photos` kind's q85 re-encode, moved val's exactly right from 69.2% to 68.7% (R5): D2 holds.
- [x] **A Visit scored from one Photo (B)**, with the Visit count: merged in PR #39, 2026-11-20
      (`phase-1.md` §4, *What moved while building B*).
- [x] **Correcting a Dart (C)** with the keypad sheet (D3) and *Enter the Score yourself* (D6):
      merged in PR #41, 2026-11-20. The keypad from a marker or chip, change, confirm, remove with *Undo*,
      add by *Add a Dart* or a tap on the Photo, a Visit entered by hand (counted once), focus into
      and out of the sheet, and the Photo beside the Score in landscape (`phase-1.md` *What moved
      while building C*). Read on `pixel-api36` and `urgent-api26`.
- [ ] **Readings (D):** thread count (R2), `minSdk` (§5, R4), real Visits on a real Board (R3).
      R4 taken 2026-11-20: about 0.36 s a Photo on a 2 GB, 2-core API 26 image at 4 threads and at
      2, so `minSdk` stays 26. R2 taken 2026-11-22 on the owner's phone: about 1.25 s a Photo at 1,
      2, 4 and 6 threads alike, so the app ships at 2, the count R4 was read at. R3 waits on real
      Visits on the owner's Board.
- [ ] **The model that met the bar (E)**, after M2's G; R3 read again.

## Phase G — the Mounted camera

[`phase-G.md`](phase-G.md), ADR-0009. Before phase 2 and before the door.

- [x] **The owner's questions answered** 2026-11-22, recorded as `phase-G.md` D5 to D9: the handheld
      `CAMERA` ask, the paperwork first, Data safety unchanged, all three mount positions, the Redmi
      Note 8 Pro on Android 11 as the spare. On 2026-11-23, D10: pairing by the QR or by its text,
      pasted, both accepted with TalkBack on in B and C; D11: B to D first, and the gate read on the
      finished app from the owner's 3 m stand.
- [x] **The paperwork (E)** merged and the policy live, before B merges: PR #77, and the policy read
      live at `https://maksforge.com/darts-scorer/privacy-policy` on 2026-11-23 (*Last updated: 23
      November 2026*).
- [ ] **B, C, D** in that order, each with its acceptance checks read.
- [ ] **The gate (A):** the Board half of M1's bar on the Mounted camera's own Photos from the
      stand's positions, read on the finished app after D (R1, D11). Needs no Darts thrown.
- [ ] **R8**, the Darts half of the bar from the mount, once the owner can throw again: the phase
      closes on it.

## Before the first upload

- [x] **Delete what the app does not need.** Phase 0: reminders, the custom backup and sharing, the
      Items and Room are gone; platform Auto Backup carries the preferences only. The tip and the
      photo plumbing stay. [`phase-0.md`](phase-0.md).
- [x] **Decide `minSdk` deliberately, before the door.** Stays 26 (2026-11-20): LiteRT's floor is 21,
      and R4 read both passes at about 0.36 s a Photo on a 2 GB, 2-core API 26 image
      ([`phase-1.md`](phase-1.md) §5); CI's floor leg stays at 26. Phase 1 decided it, on the model runtime's
      own floor and an inference time on a low-end emulator image ([`phase-0.md`](phase-0.md)).
      The direction is asymmetric: raising it later strands existing installs on the last build that fitted them, lowering it later is free. If the
      only phone in the loop sits at the top of the range, every `SDK_INT` branch below it ships
      unvalidated — the first app built from this template raised 26 to 33 for exactly that reason. Move CI's floor legs with it,
      and write the reason beside `minSdk` in `app/build.gradle.kts`, where the next person to touch it reads it.
- [x] **Ship the runtime the way ADR-0008's 2026-11-19 amendment says.** Phase 1: LiteRT, Eigen
      and the other libraries compiled into LiteRT's native library on the Credits screen beside
      DeepDarts (`SupportConfig.BUNDLED_CREDITS`), and a thread count set on the phone's reading
      rather than LiteRT's default of one, which read about three times slower (`phase-M2.md` R4):
      2 threads, from R2 on 2026-11-22 ([`phase-1.md`](phase-1.md) §2).
- [x] **Replace the placeholder mark.** The Fan, drawn in code in `art/mark.py` (no concept image),
      provenance in `art/README.md`; launcher, monochrome, notification and Play icons regenerated.
      Chosen 2026-11-12 from three Fable options.
- [x] **Regenerate the feature graphic.** 2026-11-22, English and Polish, taglines
      "Photograph the board, check every dart" and their Polish; the wordmark down to 80 px, as
      Archery Scorer's, so the name clears the mark inside Play's crop.
- [x] **Replace the placeholder domain.** Phase 0 (C) deleted the Items; the Visit screen is the
      home tab, empty until phase 1.
- [x] **Rewrite `scripts/edge-to-edge.py`'s SCENES** against your screens. Phase 0 (C): the shell,
      Visit, Settings, Help and feedback and the licences; `HOME_TAB` is *Visit*. Phase 1 adds its
      screens. R6 in [`phase-0.md`](phase-0.md).
- [x] **Make the artifact allowlists yours.** All four `aab-*.py` scripts passed on a local
      `bundleRelease` of `47b2abf`, 2026-11-22: three permissions (two from Play Billing, one from
      AndroidX), none of the six forbidden, no features, no orientation locks, Polish complete.
- [x] **Choose the palette.** Brass `8A6500`, khaki grey `6E6552`, steel blue `3F6E8C`, near-grey
      `E4E2DE` in `scripts/gen_scheme.py`; every contrast check passes.
- [x] **Make the support address work both ways.** `darts-scorer.support@maksforge.com`: Gmail's
      *Send mail as* lists it through Brevo, verified, read 2026-11-22; the listing's contact field
      and IARC use the same address. No test mail: a configured send-as is taken as working, and the
      domain is the owner's own (owner, 2026-11-22).
- [x] **Write the listing.** `docs/store-listing.md`, English and Polish, category *Sports*,
      2026-11-22, and in the Console in both languages. The AI asset declaration is the owner's:
      *Label assets as created or edited using AI* ([`play-app-content.md`](play-app-content.md)).
- [x] **Capture the screenshots.** An interim set, 2026-11-22, on the emulator from the release
      build, light theme, English and Polish: the Visit tab, Settings, and Help and feedback, padded to
      9:16 in `art/play-screenshots/`. No scored Visit yet: the shipped run misread the owner's board
      photos, so that shot waits for a better model, and `edge-to-edge.py` needs its scene first.
- [x] **Put the app on maksforge.com.** Its icon goes at `assets/icons/<repo>.webp` in
      maks-sredniawa/maks-sredniawa.github.io, which the app's own site loads, and the app goes on that home
      page. Replace `description` in `docs/_config.yml` too: it is the tagline under the app's name.
- [x] **Write the privacy policy.** Live at `maksforge.com/darts-scorer/privacy-policy` since
      2026-11-12; read against the App content answers on 2026-11-22, and its opening line corrected the
      same day to the app as it is: one photo of the board per Visit.
- [x] **Answer the Console's App content pages and write [`play-app-content.md`](play-app-content.md).**
      All ten declarations answered 2026-11-22, each dated in that file; rating PEGI 3, ClassInd 14+.
      Under managed publishing they wait in *Publishing overview*, unsent, for the first review.
- [x] **`LICENSE` and `README.md`**, 2026-11-22: the source-available notice and a *Contributing* that
      refuses pull requests, which agree; the README now says one photo per visit, the internal track,
      and the model's DeepDarts CC BY 4.0 credit.
- [x] **The upload keystore**, created and backed up 2026-11-22, and its four `UPLOAD_*` secrets
      set the same day: *The upload key* in `RELEASING.md`. It replaced a 2026-11-12 key that was not on
      this laptop and never signed an upload.
- [x] **Set up the GitHub repository.** Ruleset and rebase-only merges in place; the release-please
      PAT was set 2026-11-12 and **expires 2026-12-12**: replace it before then, or release PRs stop
      appearing.
- [x] **Create the service account and set `PLAY_SERVICE_ACCOUNT_JSON`**, 2026-11-22:
      `darts-scorer-play-ci` in its own Cloud project `darts-scorer-play`, invited with no account
      permissions, the two app permissions on this app only, and no expiry date.
- [x] **Plan the closed test.** Not a concern (owner, 2026-11-22). The testers are in
      [`RELEASING.md`](RELEASING.md). **The first closed release of a never-published app is made in
      the Console**; `publish-play-closed.yml` takes over after its approval.
- [x] **Decide the `applicationId` deliberately.** `com.maksforge.dartsscorer`, fixed by the Play
      entry created 2026-11-22 (default listing language en-US, free).

## The tip — products live, the purchase proven once on Binky

ADR-0007. The code is in; these are the parts only Play and a phone can prove. The steps are
*Selling the tip* in [`RELEASING.md`](RELEASING.md).

- [x] **Keep it or delete it, before the first upload.** Kept (owner, 2026-11-22).
- [x] **A build with billing on internal testing**, then the four products created and active.
      0.2.0 on internal 2026-11-22; `tip_small`, `tip_medium`, `tip_large`, `tip_xlarge` active
      2026-11-22, purchase option `tip`, multi-quantity on, Poland at exactly 5.00 / 10.00 / 20.00 /
      50.00 PLN ([`RELEASING.md`](RELEASING.md), *Selling the tip*).
- [x] **One purchase from a licence tester** on the internal install, ending in the thank-you line,
      and the *same* tip bought again. Not owed by Darts Scorer: `TipJar` and `TipBilling` are the
      shared code, and the purchase was proven once for every app on Binky (2026-11-13).
- [x] **The debug build shows no tip section and no card.** The section is read on `pixel-api36`,
      2026-11-22, with the debug build from `main`: Help and feedback has no tip section. That AVD has
      no Google account, so `BillingClient` reported billing unavailable and `offers` stayed empty,
      the same empty state `.debug` gets from Play. The card is ticked on the code, not that reading:
      `tipAskDue` hides it on a fresh install whatever Play returns, and `VisitViewModel` also requires
      `offers.isNotEmpty()`, so an empty `offers` never shows it.
- [x] **Content rating submitted** with *digital purchases* Yes, 2026-11-22: ClassInd 14+, the rest 3+
      or Everyone ([`play-app-content.md`](play-app-content.md)).

## Before the next upload

Re-declarations a change owes Play, written down the day the change merges and ticked when the
Console matches. A new permission, foreground service or data type is a Console change that waits in
*Publishing overview* for *Send for review* with the upload that needs it. Empty most of the time.

## After the closed test

- [ ] **The production-access application is in, with its answers recorded verbatim** in
      [`play-app-content.md`](play-app-content.md). Until it is granted the production track does not
      exist. The app this template was extracted from waited one day; that is one datapoint, not a
      promise. **If it comes back rejected, read the reason before changing any artifact.** Changing
      the build first leaves you arguing the reason against a different build.
- [ ] **Add the production countries in the Console** — *Test and release → Production → Countries /
      regions*. A new app's production track targets none, the API cannot add them, and a dry run
      does not catch it ([`RELEASING.md`](RELEASING.md)).
- [ ] **Decide the first production number.** release-please never jumps to `1.0.0` by itself (with
      the major at 0 even `feat!:` bumps the minor), so it takes a `Release-As: 1.0.0` footer
      ([`RELEASING.md`](RELEASING.md)), or a deliberate decision to stay on 0.x. In order: production
      access granted, *then* that version's release notes in every locale on an ordinary branch (never
      on release-please's own, which it force-pushes), *then* the AAB and the listing go up together.
- [ ] **Turn on the weekly CI run once the app is live on Play.** Add
      `schedule: [{cron: '47 1 * * 0'}]` under `on:` in `.github/workflows/ci.yml`; until then
      edge-to-edge runs only from the Run workflow button. GitHub's `schedule` is best-effort and
      can drop a run: a week with no run is not a green week.

## Standing checks that never close

- [ ] **Every release: run the artifact checks on the built AAB**, not on the source.
      `aab-permissions.py` is the one that finds what a *dependency* merged into your manifest —
      a permission you never declared, or a `uses-feature` that quietly filters the app off devices.
- [ ] **Every release: read the release notes gate's output** rather than trusting it passed.
- [ ] **Every Play declaration: confirm Data safety still holds** against
      [`play-app-content.md`](play-app-content.md), and write the date of the re-read here.
- [ ] **Every dependency bump: re-run `licensee`.** The build fails on an unallowed licence, which is
      the point — but the fix is two things, the allowlist *and* the bundled text.
- [ ] **Test the release-shaped build on a device.** A missing R8 keep rule does not crash; it makes
      a feature silently stop working.
