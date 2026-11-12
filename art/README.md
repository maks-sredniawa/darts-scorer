# Identity assets

Source art for the launcher icon and the Play listing. **Everything in `app/src/main/res` that draws
the mark is generated from here** — edit `mark.py` and regenerate, never hand-edit the path data in
the `VectorDrawable`s.

| Asset | Source | State |
| --- | --- | --- |
| `mark.py`'s PARTS | sectors and circles drawn in code; no concept image | the Fan mark |
| `drawable/ic_launcher_{background,foreground,monochrome}.xml`, `mipmap-*`, `play-icon-512.png` | `mark.py` → `make-launcher-icon.py` | generated |
| `play-feature-graphic.png`, `play-feature-graphic-<tag>.png` (1024×500, one per translated listing; `COPY`) | `mark.py` + `theme/Color.kt` (+ `feature-background.png` if present) → `make-feature-graphic.py` | generated, but still the template's until Phase N regenerates it |
| `play-screenshots/<n>_<scene>-<tag>.png` | `scripts/screenshots.py --build release --numbered` → `pad-screenshot.py` | — |

## The mark

`mark.py` is the single definition, as **cubic subpaths in `PARTS`**, each a filled shape or a hole
punched through what is under it. Both generators import it, so the launcher icon and the feature
graphic cannot drift into being different marks.

What ships is **the Fan mark**: eight of the board's segments, each split by the treble wire, round a
bull with a real hole. Every part is a sector or a circle, so it is written in code rather than
traced. Ground `2A2A28` is the dark scheme's `surfaceContainerHigh` and the ink `EFC05D` its
`primary`, the board's black and a brass barrel. Chosen by the owner on 2026-11-12 from three
options, on a Fable design pass.

- **Recolouring is two values in `mark.py` and a re-run**: `GROUND` (the icon's field) and
  `MARK_INK` (the mark on it). `make-launcher-icon.py` writes every drawable from them, the
  background included — it used to be hand-written, and a second copy of a colour in a file nobody
  regenerates is the drift the first app built from this template found the first time its palette
  moved.
- Take the colours from the app's generated scheme (`scripts/gen_scheme.py`) rather than picking
  them for the icon, so the identity and the app agree. **Judge the ground at 44dp on a real home
  screen, light and dark**: a dark tone of a warm hue is brown, and a gradient's middle is the same
  brown at launcher size. A flat ground with no gradient is what survives; here it is a near-neutral
  charcoal, so the warmth is all in the brass ink.
- The feature graphic **reads its colours out of `theme/Color.kt`**, so a regenerated palette
  reaches the listing by re-running the script. Pasted inks stay the old hue on a ground that moved.
- **The hole must be a real hole in the path**, not a shape painted in the background colour. A
  themed launcher (API 33+) tints the whole monochrome layer one flat colour, and a painted hole
  simply vanishes.

## Where the art has to come from

**Use art you have the right to ship.** This is not a formality — it is the thing most likely to
block a first Play upload, and it is discovered late.

- An icon traced from an **emoji font** carries that font's licence. Noto Emoji is Apache-2.0 or
  OFL depending on the release, and both impose obligations on the *outlines* — which is what
  tracing copies.
- A **stock icon** is somebody's asset with somebody's terms, whatever the site's marketing says.
- **Art you drew, or art generated from your own prompt, is clean.** Keep a note of which, in this
  file, so the provenance survives you forgetting it.

Rendering *text* with a font is a different question from redistributing its *outlines*: the OFL
explicitly permits documents produced with a font. `make-feature-graphic.py` renders the wordmark
with Noto Sans on that basis and ships no glyph outlines.

## Replacing the mark

```bash
# 1. Draw or generate a concept image, and put it beside this file.
python3 art/trace-mark.py concept.png   # prints cubic path data
#    Set CROP and the concept's two tones at the top of trace-mark.py first — they describe the
#    *image being traced*, not the app. Paste the outer path and the hole into art/mark.py's PARTS
#    as Subpath(...) and Subpath(..., hole=True), with your colours.

# 2. Regenerate everything that derives from it.
python3 art/make-launcher-icon.py       # icons, mipmaps, the 512² Play asset
python3 art/make-feature-graphic.py     # the 1024×500 listing graphics
```

`make-launcher-icon.py` prints a **safe-radius check** and will tell you when the art is clipped by
a circular launcher mask. It is a real constraint rather than a formality: a launcher may mask the
icon to a 66dp circle, so anything outside a 33dp radius from the centre is cut off. Shrink
`ART_SIZE` until it says `inside`.

One size worth knowing, already handled: the **flat mipmaps** are cropped to the 72dp a launcher
actually shows of the 108dp adaptive canvas, so they match what the adaptive icon looks like rather
than appearing to shrink.

## The feature graphic and Play's crop

Play shows the 1024×500 graphic in a **16:9 box with `object-fit: cover`** on the search-results
card, so 68px of each side never reaches a viewer. It is correct in every local preview and in the
Console's uploader, and wrong only on the surface most people see. `make-feature-graphic.py` lays out
against the cropped frame, prints the spans it measured, and **exits 1** when the copy is clipped or
runs into the mark — shorten the tagline rather than moving the margin.

A photographic ground is `art/feature-background.png` (cover-fitted, never stretched). Record where
it came from in the provenance table below, like the concept image.

## Provenance

| File | Where it came from | Licence / terms |
| --- | --- | --- |
| `mark.py` | drawn in code from sectors and circles, for this app | the repo's LICENSE |
| `feature-background.png` | *(if used)* | |
