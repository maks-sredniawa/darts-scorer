# Play Console — App content answers

The answers this app gave in the Console's **App content** pages, what each one rests on, and **the
fact that would change it**. The Console shows what was answered but never why, and Play asks again:
when the app changes, when the questionnaire changes, and once a year. A re-declaration made from
memory a year from now is how a true answer turns false.

Two rules keep this file honest:

- **The privacy policy and the Data safety form describe the same facts to two audiences**, and Play
  cross-checks them. [`privacy-policy.md`](privacy-policy.md) and this file move in the same commit.
  A change to one without the other is the drift this file exists to stop.
- **A claim about permissions is read off the built artifact, never off the manifest.** A dependency
  can merge a permission the source never declared, and that is invisible from `AndroidManifest.xml`.
  `scripts/aab-permissions.py` is the reader, it runs before every upload, and its `EXPECTED` and
  `FORBIDDEN` tables are this section's twin — edit them together.

## What the artifact carries

Read at **versionCode 206, versionName 0.2.0** by `publish-play.yml`'s verify step on 2026-11-22
([run](https://github.com/maks-sredniawa/darts-scorer/actions/runs/45054439048)):

> 3 permissions, all accounted for; none of the 6 forbidden ones present; 0 <uses-feature> declared; 0 of the 4 activities lock their orientation, every one of them expected

| Permission | Whose | What it is for | Console consequence |
| --- | --- | --- | --- |
| `ACCESS_NETWORK_STATE` | Play Billing's `datatransport` | read before its (blocked) log upload; it opens nothing | none, but a reviewer may ask why an app with no network reads it — this row is the answer |
| `com.android.vending.BILLING` | Play Billing Library | the tip (ADR-0007): IPC to the Play app's billing service | none: not on Play's declaration list. The listing shows *Contains in-app purchases* once products exist |
| `…DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | AndroidX | its own non-exported receivers, signature-level | none: not user-visible |

The billing library's `datatransport` dependency merges `INTERNET`; the manifest removes it with
`tools:node="remove"`, and the gate is what proves it stayed out. It merges `ACCESS_NETWORK_STATE`
too, and is that row's only owner, so the row goes with the tip.

**Forbidden, and asserted absent**: `INTERNET`, `AD_ID`, `QUERY_ALL_PACKAGES`,
`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, `CAMERA`, `USE_EXACT_ALARM`. The first two are what the Data
safety and advertising-ID answers rest on.

---

## Ads

**No.** Answered 2026-11-22.

Would change: any ad SDK, ever. `AD_ID` absent from the artifact is the check that would catch one
arriving through a dependency.

## App access

**All functionality is available without special access.** Answered 2026-11-22. The Console now calls
this page *Sign-in details*, and asks *Is any part of your app restricted?*: **No**. Its Yes option
names payments such as one-time products; the tip unlocks nothing, so it restricts nothing.

There is no account and no sign-in. Would change: a feature behind a login.

## Content rating

**The IARC questionnaire.** Answered 2026-11-22, category *All other app types*, rating contact
`darts-scorer.support@maksforge.com` — the listing's address, so there is one address to keep alive, not two. Every
question answered No gives Everyone (ESRB) and PEGI 3.

The category is *All other app types* unless the app's purpose is something the questionnaire names.
Not *Social or communication* for an app that only touches calls or messages: that category means
people talking to each other through the app.

**The tip turns one answer to Yes**: *does the app allow users to purchase digital goods?*
(ADR-0007). Its follow-up, *can these purchases include random items* (loot boxes), is
**No**. The first two apps built from this template, both category *All other app types*, came out
at PEGI 3, ESRB Everyone, USK 0 and 3+ elsewhere, with an *In-app purchases* notice — and **Brazil's
ClassInd at 14+**, which it gives any app selling digital goods. Expect the same, and decide before
submitting that a tip is worth it; deleting the tip is the only answer that keeps Brazil at L.

**Result, 2026-11-22:** PEGI 3, ESRB Everyone, USK all ages, IARC 3+, Google Play 3+ and ClassInd 14+,
each with *In-app purchases* as the interactive element and no content descriptors. Every question was
No except *purchase digital goods* (Yes) and its loot-box follow-up (No).

In the Console the questionnaire shows one section at a time, and *Next* stays disabled until
*Save* has been pressed. With managed publishing off, saving the summary sends it for review at once.

**The Mounted camera keeps every answer No** (ADR-0009, decision 13). *Do users interact or exchange
content?* is about people reaching each other through the app; the Mounted camera's link joins one
player's own two phones, the Player's phone and the spare phone it paired, and carries only that
player's Photo between them. No user reaches another user, and nothing a user makes is shown to anyone
else. Nothing is re-answered for it.

Would change: user-generated content, communication between users, or a link out to anything that
has either. A Mounted camera that could be paired with someone else's phone, or a Photo shown to
another player, would be the first. A support `mailto:` hand-off is not user-to-user communication — it opens the user's own
mail app, addressed to the developer — and a rate row opens Play's own listing, whose reviews are
Play's surface rather than the app's.

## Target audience and content

**18 and over.** Answered 2026-11-22. *Restrict users that Google has determined to be minors* left
unticked. Re-read after the rating was submitted: no band blocked, nothing flagged.

The Mounted camera does not change it: no content and no contact between users (*Content rating*
above). Would change: lowering it. Any age band under 18 brings in the Families policy and its design and
SDK requirements.

⚠ Re-read this page once the content rating is submitted. On Darek, built from this template
(2026-10-31), it showed the under-13 bands blocked by *"your app's ESRB rating is set to Teen or
higher"* before any rating existed.

## Government, financial and health features

**No to all three.** Answered 2026-11-22: not developed by or on behalf of a government, *My app
doesn't provide any financial features*, *My app does not have any health features*.

Health is the one to guard, for an app anywhere near wellbeing. **Keep health claims out of the
listing, the site and the tags** — Play's enforcement has treated a linked page as part of the
listing. Would change: copy or a tag that sells the app as good for you.

## Data safety

**No data collected. No data shared.** Answered 2026-11-22 against versionCode 206: *Does your app
collect or share any of the required user data types?* **No**, which skips every later step. No
badge claimed.

**The Mounted camera keeps that answer** (ADR-0009, decision 13; the owner's choice, `phase-G.md` D7),
so nothing is re-submitted in the Console when its build ships. The reasoning below is written for the
app as it will be once phase G's checkpoints B to D ship, one release ahead of them (`phase-G.md` D6).
Until the build that declares `INTERNET`, point 1's older and stronger fact still holds as well: the
artifact carries no `INTERNET` at all (the table above).

Play's definitions, from its Data safety help page (support.google.com, answer 10787469) — re-read
them at each re-declaration rather than trusting this quote:

> "'Collect' means transmitting data from your app off a user's device."
>
> "User data accessed by your app that is only processed locally on the user's device and not sent
> off device does **not** need to be disclosed."
>
> "**End-to-end encryption:** User data that is sent off device, but that is unreadable by you or
> anyone other than the sender and recipient as a result of end-to-end encryption does **not** need
> to be disclosed." Under it: "The encrypted data must not be readable by any intermediary entity,
> including the developer, and only sender and recipient may have necessary keys." (Read 2026-11-23.)

The answer rests on one fact per route data could take:

1. **The app transmits one thing: a Photo, only between the player's own paired phones, end to end
   encrypted.** A Mounted camera sends the Photo it took to its Player's phone over the local
   network, and nowhere else (ADR-0009, decisions 3 and 4). It is "sent off device", so the answer
   rests on the exemption quoted above, not on the definition: the link is TLS, mutually
   authenticated and pinned to the two phones' Keystore keys, which cannot be exported, so only the
   sender and the recipient hold the keys and the developer, the router and anyone else on the
   network can read nothing. The app connects only to a private or link-local address that NSD
   resolved, makes no DNS lookup and holds no URL (the local-peer check, `isLocalPeer`, with its
   test). **The encryption is load-bearing for this answer, not a nicety**: a Photo sent in the clear,
   or to anything but the paired phone, makes Photos *collected*. What stands where the forbidden
   `INTERNET` stood is therefore code: the local-peer check, the pinned TLS, and point 6's
   exclusion, each with its test or gate.
2. **Photos are processed only on the player's own phones.** Picked or taken, re-encoded by
   `media/MediaFiles.kt` with their metadata — GPS included — stripped, and stored in the app's
   private storage, which no backup takes them out of (point 3). A Mounted camera encodes its Photo
   the same way into memory, sends it and drops it, writing nothing to its own storage (ADR-0009,
   decision 6). The app has no share or export of its own.
3. **Auto Backup is still "no data collected".** The platform moves the user's backup to the user's
   own Google Drive; the developer never sees it. That is Android transmitting the user's backup, not
   the app transmitting to the developer. It carries the preferences and the chosen language, and
   **never a photo**: both rule files are include-only and name nothing else, for the cloud backup
   and the device transfer alike, and `BackupRulesTest` fails on any other include. ⚠ Every key the
   backup carries lands on the user's *next* phone too — see ADR-0005's 2026-11-12 amendment. The
   Mounted camera's pairing store (its pins, the camera list and the role) lives in
   `noBackupFilesDir`, which Android excludes from both whatever the rules say, and `PairingStoreTest`
   holds it there (ADR-0009, decision 4).
4. **A support mail is still "no data collected", and the reason is the definition rather than an
   exemption.** A `mailto:` hands a draft to **another app**; the user reads it, can edit every line,
   and sends it from their own mail client, or does not. ⚠ **Do not write "Play exempts support
   flows" in a re-declaration.** The help page has no such exemption; the claim is true because of
   what "collect" means, and that is the reason to give.
5. **A tip is still "no data collected", by the same help page's FAQ on payment services.** It names
   Google Play's billing system as a service whose payment data you don't need to declare when the
   app never accesses that information and the service collects it directly from the user under its
   own terms. The tip meets both: Play's own sheet takes the payment details, under Google's terms,
   and the app never sees them. The FAQ also asks about other financial data and about what the app
   receives back: that is a purchase token and a product id, which the app hands straight back to Play
   to consume, never stores and never sends anywhere else, so by the definition above it is not
   collected. The developer's order report comes from Google, not from the app.
6. **The billing library's usage logging still cannot leave**, now that `INTERNET` is declared
   (ADR-0009, decision 12; ADR-0007's 2026-11-22 amendment). Its only `datatransport` backend,
   `transport-backend-cct`, is excluded from the build, so billing's logger fails to initialise and
   skips every log (*Skipping logging since initialization failed.*) instead of handing it on, and
   `aab-permissions.py` fails the upload if a `backend:` meta-data entry ever reappears. Before the
   build that declares `INTERNET`, the missing permission does the same job. If the tip stops working
   without the backend (`phase-G.md` R7), the exclusion is reverted and this point becomes a
   declaration of what the library collects, in the same commit.

Would change any of it:

- **A connection to anything but a paired phone**: a server, a URL, a DNS lookup, or a peer outside
  the local network, from our code or a dependency. Before the Mounted camera's build, `INTERNET` on
  the artifact at all is this; after it, the local-peer check and the pinned TLS are what stop one.
- **A Photo sent without the pinned, end-to-end encryption**, or readable by anything between the
  two phones: point 1 then rests on nothing.
- **A `datatransport` backend in the artifact** (point 6), or the exclusion reverted.
- **Anything the app sends by itself**, such as crash reporting or analytics. There is none today.
- **The app keeping a purchase**, such as a tip history or a supporter badge: that is *Purchase
  history* the app collects, and the form has no way to declare it as Google Play's.
- **Location of any kind**, including through a photo's metadata surviving into storage or a backup.
- **A backup rule that names a photo directory**, or a share or export of a photo: point 2 stops
  being the whole story.

## Advertising ID

**No.** The artifact carries no `com.google.android.gms.permission.AD_ID`, and `aab-permissions.py`
forbids it. Answered 2026-11-22.

## Foreground service permissions

**None declared**: the artifact carries no `FOREGROUND_SERVICE`, and nothing here starts one. If the
app gains a foreground service, this section records the type, the `PROPERTY_SPECIAL_USE_FGS_SUBTYPE`
text if it is `specialUse`, and the three answers the declaration asks for: what the user sees, why
it cannot wait, and why no named type fits.

The Mounted camera deliberately needs none: it works only while its screen is open, kept on by a
window flag, so there is no `camera` foreground service, notification or video to declare (ADR-0009,
decision 10). Neither `CAMERA` nor `INTERNET` is on Play's list of permissions that need a
declaration form (decision 13).

The declaration also wants **a video** of the service doing its job. Record its link here, and keep
it viewable by anyone with the link for as long as the declaration is on file. `adb screenrecord`
captures no audio, so say so in the declaration if the service's job is a sound.

## Store settings (not App content, recorded here because it is asked for the same reason)

- **Category:** *Sports*, set 2026-11-22 — a tool for one sport's scoring, not a general utility, so
  not *Tools*.
- **Tags:** none.
- **Contact email:** `darts-scorer.support@maksforge.com`, set 2026-11-22 with the website
  `https://maksforge.com/darts-scorer/`. The Console's contact dialog offers only *Save and publish*,
  so these went live at once rather than with a review. Public on the listing and the same address
  `ui/support/SupportConfig.kt` compiles in. The Console field changes without a release; the app's copy needs
  one.
- **AI asset declaration:** *Label assets as created or edited using AI*, answered by the owner
  2026-11-22 on the store listing's *Review* step. The mark, and with it the icon and the feature
  graphic, was chosen from designs an AI model drew and is rendered by code an AI wrote; the
  screenshots are captures of the app. Would change: listing art made by hand.
- **Privacy policy:** `https://maksforge.com/darts-scorer/privacy-policy`, set 2026-11-22, served from `docs/` by
  maksforge.com. It updates within about 15 minutes of a merge to `main`, with no release, which is why it has to be right before the
  app it describes ships rather than after. Read against these answers 2026-11-22 and re-dated that day,
  when its opening line dropped "one or more photos" for the single photo the app reads today.
  Re-dated 2026-11-23 for phase G's checkpoint E (`phase-G.md` §1), one release ahead of the Mounted
  camera: it drops *no permission to use the internet*, says the camera and the local network arrive
  with the Mounted camera, and describes the Mounted camera as coming. The words *coming* and *today's
  version* go in the release that ships it, with the store listing's.

## Production access — the application, and the answers it was given

**Submitted _<date>_.** Asked once, from the Console's Dashboard, after the closed test's 14 days.
Record the answers **verbatim**, not summarised: the Console asks the same set again for the next app
on this account, and an answer re-read a year later has to be the one that was given.

**Draft the answers here before pasting them**, under a *Drafted <date>, not submitted* line that
becomes the submission date once they are in. Every claim must trace to a dated record in
[`DOD.md`](DOD.md) or a phase file: a test you remember but never wrote down is cut, not paraphrased.
Leave `_<…>_` gaps only for the testers' own words, which only the owner has.

**About your closed test**

- *How did you recruit users for your closed test?* — _<answer>_
- *How easy was it to recruit testers?* — _<answer>_
- *Describe the engagement you received from testers* — _<answer>_
- *Provide a summary of the feedback that you received* — _<answer>_

**About your app**

- *Who is the intended audience?* — _<answer>_
- *Describe how your app provides value to users* — _<answer>_
- *How many installs do you expect in your first year?* — _<answer>_ (the apps built from this
  template answered 0–1,000)

**Your production readiness**

- *What changes did you make based on what you learned during your closed test?* — _<answer>_
- *How did you decide that your app is ready for production?* — _<answer>_

**Three things the apps built from this template kept deliberate, so a later answer does not undo
them:**

1. **The audience answer agrees with *Target audience* above.** A reviewer reads the two side by side.
   A mismatch is a question rather than a rejection, but it can cost days.
2. **Engagement is answered from what the app can know.** With no analytics and no server there is no
   telemetry, so the true answer is what is visible without it: *"The app has no analytics and no
   server, so I cannot see how often testers used it. What I can see is the testers who
   stayed opted in through the 14 days, and the messages some of them sent."* A guessed figure would
   contradict *Data safety* in this same file.
3. **The changes answer says where the changes came from.** If the testers reported nothing, say so and
   name what came from your own use instead. Presenting your own work as tester-driven is an easy
   dishonest sentence, and the application does not need one.

## A payment-link tip (Payments policy — not a question Play asks, but one a reviewer answers)

**Default: no payment link on any surface the release controls**, whatever the app sells through Play
Billing. Not in the app, and not on the pages the listing links to. Read this before adding one,
because the policy text and its enforcement disagree.

- **The text allows it.** Payments policy §3.2 treats a tip as a peer-to-peer payment, outside Play
  Billing, when **100% reaches the creator** and **nothing unlocks** — no badge, no theme, no
  thanks-screen. §4's anti-steering rule excepts §3. So: one personal payment link, worded as a *tip to
  a person*, never a *donation to a project*.
- **Enforcement has rejected apps anyway.** StreetComplete (February 2022) was rejected for in-app
  Patreon, Liberapay and GitHub Sponsors links — and **for a link to its own home page, because that
  page carried donation information**. A Buy Me a Coffee link in the app this template was extracted
  from was flagged the same way. None of those is the §3.2 shape (tiers unlock things, a platform takes
  a cut, a project is not a person), but the distinction has to survive a reviewer skimming for
  "external payment link", and a pre-launch rejection costs the closed-test window.
- **The reach is one level out.** The first app built from this template moved its tip from the app to
  the repository and the app's site, then noticed that the listing's *Website* field and the last line
  of its full description point at exactly those pages. So "nothing the app links to" includes what
  the **listing** links to.
- **When to revisit:** once the app is live, with a track record to appeal from. The cheapest shape
  then is a tip on the repository alone, with the listing's Website field and full description kept
  off it. A Play Billing consumable is the unambiguous alternative, at the cost of a billing
  dependency, Google's cut, and an *in-app purchases* badge on the listing.

⚠ The listing's *Website*, `maksforge.com/darts-scorer/`, and the privacy policy are drawn by
`maks-sredniawa/pages-theme`, whose layout carries a *Like what I make?* block with Buy me a coffee and
PayPal links on every page. Accepted: the live siblings, Gloam and Binky, passed review with the same
theme. If a reviewer cites it, the fix goes in the theme, as a per-site opt-out, not in this app.

Region carve-outs (US external links since October 2025, the EEA's external-offers program) do not
help: both are fee programs with reporting obligations, which is not a serious route for occasional
tips. A sentence promising a *future* tip, with nothing to click, is a statement about pricing and is
fine anywhere.

## The tip (ADR-0007)

**A Play Billing consumable, not a link** — the section above is why. The template ships it; an app
that does not want it deletes it before the first upload (`optional-modules.md`), and the section
above still holds after it is gone.

What a reviewer can still ask about, and the answer:

- **The *Contains in-app purchases* label** on a free app: the tip unlocks nothing, and the Support
  section says so in the user's language.
- **The content rating**: re-answered above, with Brazil at 14+.
- **Data safety**: points 5 and 6 above.
- **Financial features**: unchanged. A tip is an in-app purchase, not a financial feature.

---

## When Play asks again

1. Run `python3 scripts/aab-permissions.py` against the newest bundle, and compare its table with the
   one above. A new row is a new question.
2. Read `docs/privacy-policy.md` against the answers here. If one has moved, both move, in one commit.
3. Copy any value this file does not hold while the Console is open — a category, a date, a
   declaration's exact wording — so the next re-declaration can compare against it.
4. Re-date the sections you re-answered.
