# The tip is a Play Billing consumable that unlocks nothing

## Context

An app built from this template is free: no ads, no paid tier, nothing locked. Some users want to
pay anyway, and the developer would like to let them. The question is the route.

Play's Payments policy §3.2 allows a peer-to-peer tip outside Play Billing when the whole amount
reaches the creator and nothing unlocks. Enforcement has not agreed with the text: StreetComplete was
rejected in February 2022 for in-app Patreon, Liberapay and GitHub Sponsors links, and for a link to
its own home page because that page carried donation information. A Buy Me a Coffee link in the app
this template was extracted from was flagged the same way. The first two apps built from the
template each held the tip back for that reason, then shipped it through Play Billing once they were
live (2026-10-11), with the same products, the same two surfaces and the same code. This ADR is that
outcome, written down so the next app starts there.

## Decision

**The tip ships in the template, as four consumable one-time products sold through Google Play
Billing, and it unlocks nothing.**

- **Products:** `tip_small`, `tip_medium`, `tip_large`, `tip_xlarge`, at 5, 10, 20 and 50 PLN in
  Poland and Play's own conversions elsewhere, each with multi-quantity on — the nearest Play comes
  to an amount the user picks. `TIP_PRODUCT_IDS` in `tip/TipJar.kt` must match the Console exactly; a
  product missing there is simply not offered.
- **Every purchase is consumed, on every foreground.** Consuming is what lets the same tip be given
  twice, and it is also the acknowledgement Play requires within three days, after which it refunds.
  `MainApplication` settles owned purchases whenever the app comes to the foreground, so a payment
  that clears while the app is closed, or one caught by a process death, is consumed the next time
  the user opens it. There is no entitlement, so nothing about a purchase is ever stored.
- **`TipJar` lives in `AppContainer`, not a `ViewModel`**, because a purchase can finish after the
  screen that opened Play's sheet is gone.
- **Two surfaces.** A section on *Help and feedback*, present only where Play returns products — no
  Play, the debug `applicationId` or products not yet created all leave it absent rather than broken.
  And one card on the home screen, **once per install**, to someone who has had the app 30 days and
  recorded ten items (`tip/TipAsk.kt`); either button answers it for good on that install. The
  answer is a preference, and `AppBackupAgent` backs up only the database and the thumbnails
  (ADR-0005), so a user who moves phones is asked once more, a month after the move.
- **Prices come from Play only.** The UI shows `formattedPrice`; a literal "5 zł" would be wrong
  everywhere outside Poland.
- **The wording is "tip the developer"**, never "donate" or "support the project": it is a payment to
  a person, and it buys nothing.
- **`INTERNET` stays out.** The billing library depends on Google's `datatransport`, which merges
  `INTERNET` for its own logging. The manifest removes it with `tools:node="remove"`, and
  `scripts/aab-permissions.py` keeps it forbidden. Billing never needed it: a purchase is IPC to the
  Play Store app, which does the networking in its own process.

## Alternatives

- **A personal payment link (§3.2).** Free of Google's cut and of any dependency, and the policy
  text permits it. Lost on enforcement: rejection reaches links the reviewer reads as external
  payment, including pages the *listing* links to, and the cost lands on a closed test or a release.
- **No tip at all.** Costs nothing and risks nothing, and leaves generous users with no way to pay.
  Each app can still choose it — `optional-modules.md` lists what to delete.
- **A tier, a badge or a thank-you unlock.** Rejected on principle: every feature ships to everyone.
  It would also turn the tip into a product with an entitlement to restore across devices, which is
  the machinery this decision avoids.
- **Subscriptions.** A recurring charge for nothing is not a tip.

## Consequences

- **Google takes its cut** — 15% on the reduced tier, which the developer account enrols in once.
- **The listing shows *Contains in-app purchases*** once the products exist, on an app whose pitch is
  that nothing is for sale. The tip's own wording is the answer: it unlocks nothing.
- **The content rating moves in Brazil.** IARC's *does the app allow users to purchase digital goods?*
  is now Yes, and ClassInd rates any such app **14+**, tip or not. Every other authority stayed at
  its lowest band for both apps that re-rated (`play-app-content.md`).
- **Products cannot be created before the code ships.** Play Console refuses a one-time product until
  a bundle carrying `com.android.vending.BILLING` is on a track, so the first build with the tip goes
  to internal testing with no products, and shows no tip, by design.
- **One more dependency and one more permission**: the billing library, `lifecycle-process`, and
  `BILLING` in the artifact. The licences screen links Google's terms for the Play services artifacts
  billing brings in; their text is not ours to ship.

## Amendment — 2026-11-12: the tip's answer reaches the next phone

Auto Backup now carries every preference (ADR-0005's 2026-11-12 amendment), `tip_asked` among them,
so a user who answered the ask is not asked again after moving phones. The month still restarts on
the new phone, since `firstInstallTime` is not backed up, but the ask does not come back.

## Amendment — 2026-11-12: the ask counts Visits scored, on the Visit screen

The app has no Items, so the home-screen card lives on the Visit screen, the home tab, and its
measure of use is Visits scored rather than items recorded: the preference `visits_scored`, against
`TIP_ASK_AFTER_VISITS`, still 10. The 30 days are unchanged. Nothing writes the count until phase 1
can score a Visit, so until then the ask never comes due.

## Amendment — 2026-11-22: `INTERNET` returns for the Mounted camera, and the logging still has no way out

ADR-0009 brings `INTERNET` back, for the local link between a Player's phone and its Mounted camera
only ([`phase-G.md`](../phase-G.md), checkpoint C). The Decision's *`INTERNET` stays out* no longer
holds, and what it protected moves:

- **The billing library's `datatransport` would have a route off the phone.** Its only backend,
  `com.google.android.datatransport:transport-backend-cct`, is excluded from the billing dependency in
  Gradle, and `app/proguard-rules.pro` gains `-dontwarn com.google.android.datatransport.cct.**`,
  since billing's logger names `CCTDestination` directly and R8 would otherwise fail the release
  build on the missing class. At run time that logger's constructor then fails, it catches the error
  and skips every log after it (*Skipping logging since initialization failed.*), so nothing reaches
  `datatransport` (ADR-0009, decision 12). The manifest declares `INTERNET` itself and its
  `tools:node="remove"` goes.
- **`scripts/aab-permissions.py` checks the artifact carries no `datatransport` backend**, in place of
  the forbidden `INTERNET`: a dependency bump that brings a backend back fails the upload.
- **The tip is read working on the first internal-track build with the exclusion** (`phase-G.md` R7).
  If billing fails without the backend, the exclusion is reverted and the Data safety form declares
  what the library collects, in the same commit.

Takes effect with the build that first declares `INTERNET`; until then the Decision above stands as
written.
