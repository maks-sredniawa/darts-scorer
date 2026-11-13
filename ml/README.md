# ml/ — the labelling loop

Code only. The owner's Photos, their labels, DeepDarts and any weights live in `DARTS_DATA`, outside
the repository, and never enter git ([ADR-0008](../docs/adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md)).
The plan, the data layout and the bar are in [`docs/phase-M1.md`](../docs/phase-M1.md); the words are
in [`CONTEXT.md`](../CONTEXT.md).

## Setup

```bash
sudo apt install libjpeg-turbo-progs        # jpegtran, for ingest
uv sync --locked --directory ml
uv run --directory ml darts-ml paths        # prints DARTS_DATA, refuses one inside the repo, checks jpegtran
```

`DARTS_DATA` defaults to `~/darts-scorer-data`. `paths.py` refuses any value that resolves inside the
repository or one of its worktrees, symlinks followed, and the same for every folder under it that the
loop reads or writes.

## The sheet

`$DARTS_DATA/capture-sessions/<capture-session>.toml`, typed up the same day from the notes taken at
the Board. One `[[visits]]` per Visit, in order, one string per Dart: its Score, then any marks.

```toml
phone = "phone 1"
light = "day"            # day, evening, flash or harsh
set = "training"         # training or held-out
date = 2026-11-14

[[visits]]
darts = ["T20", "T20 wire", "S1"]

[[visits]]
darts = ["S5", "T5 hidden", "out"]

[[mismatches]]           # only for a finding that cannot be fixed (phase-M1.md §5)
photo = "s01-v02-p3"
reason = "the S5 fell out before p3 was taken"
```

Scores are `S1`–`S20`, `D1`–`D20`, `T1`–`T20`, `25`, `50`, and `miss` for a Dart in the Board
outside the double. `out` is a Dart that is not in the Board. Marks are `wire`, `hidden` (not visible
in p1), `hidden-p2` and `hidden-p3` (not visible in that Photo), and `placed` (pushed in by hand;
never in a held-out Capture session). `ingest` appends an `[ingest]` table with each Photo's camera
and capture time.

## The loop, one Capture session at a time

```bash
uv run --directory ml darts-ml ingest s01          # inbox/s01 → photos/s01, upright and stripped
uv run --directory ml darts-ml label s01           # pass 1: Hand points and Entry points
uv run --directory ml darts-ml prefill s01         # pass 2: all 80 crossings; Entry points suggested across Angles
uv run --directory ml darts-ml review s01          # pass 3: confirm each Photo (run twice, on different days, if held-out)
uv run --directory ml darts-ml check s01           # label QA; must come back clean
uv run --directory ml darts-ml overlay s01         # QA renders into overlays/s01; flip through them
```

`ingest` keeps the phone's files in `inbox/<capture-session>/`: delete them, GPS and all, once the
Photos look right. It never guesses: a count that is not three Photos per Visit stops it, and so do
capture times that do not fall three to a Visit (a gap inside a Visit as long as one between two);
either way it lists the files in capture order.

**The gate** (phase-M1.md §1) repeats the labelling in its own directories and compares the rounds:

```bash
uv run --directory ml darts-ml label s01 --round b      # then prefill, review and check with --round b
uv run --directory ml darts-ml label s01 --round c      # no pre-fill: click every visible crossing; then review
uv run --directory ml darts-ml repeatability s01
```

`repeatability` reads only reviewed labels. A Hand point counts as dragged, because it was placed by
hand.

## The Held-out set and the bar

phase-M1.md §6 and §7. The bar's numbers live once, in `BAR` in `evaluate.py`, and `BarTest` pins
them; a change to the bar is a change to §7 first.

```bash
uv run --directory ml darts-ml freeze-held-out     # G: hash every held-out file into ml/splits/held-out.toml
uv run --directory ml darts-ml verify-held-out     # fails on any held-out file missing or changed since
uv run --directory ml darts-ml build               # build/records.jsonl, refusing every held-out Photo
uv run --directory ml darts-ml evaluate --predictions labels           # R7: the harness reads perfect as perfect
uv run --directory ml darts-ml evaluate --predictions predictions.json # a model's reading
```

- **`freeze-held-out`** freezes every Capture session whose sheet says `set = "held-out"`, and only
  once `check` is clean on each. The manifest holds the SHA-256 of each held-out Photo and label, and
  of each held-out sheet and review manifest; it is committed, and a later change to it says why in
  its commit body. It refuses to overwrite an existing manifest unless given `--replace`, which
  states the intent and skips none of the checks. A frozen Capture session is only ever added to:
  it refuses any freeze that would leave out one the manifest, or any commit of it, froze, even
  once its sheet says training or the manifest is deleted.
- **`verify-held-out`** fails on a frozen file that is missing or changed, on a Photo a frozen sheet
  lists and the manifest leaves out, on a frozen Photo its frozen sheet does not list, on a sheet it
  cannot read, on a Capture session an earlier commit of the manifest froze and this one leaves out,
  and on a held-out sheet the manifest does not freeze. `evaluate` runs the same check first and
  reads nothing that fails it.
- **`build`** writes one record per reviewed training Photo (phase-M1.md §4, *The common record*). It
  refuses a Photo whose sheet says held-out, one of a Capture session the manifest or any earlier
  commit of it freezes, and one whose Photo or label has the bytes of a held-out one. It needs the
  frozen manifest to run.
- **`evaluate`** counts Photos and Visits from the manifest, never from the predictions: a Photo the
  predictions leave out is a Board not found. It exits 0 when the bar is met and 1 when it is not.

### The predictions file

JSON, pixel positions on the held-out Photo as ingested:

```json
{
  "photos": {
    "s04-v01-p1": {
      "calibration": {"do-5-20": [812.4, 140.9], "ti-6-10": [1180.2, 603.5]},
      "entries": [{"x": 940.1, "y": 512.8}, {"x": 951.7, "y": 498.0, "low_confidence": true}]
    }
  }
}
```

- `calibration` names crossings from `board.py`'s list. *Ĥ* is the least-squares homography through
  every point given, so a model that fits with RANSAC passes its inliers only. Fewer than four points,
  or a degenerate set, is a Board not found. A position that is not a finite number, here or in
  `entries`, is refused: the file is broken, not the Board unseen.
- `entries` are Entry points. `low_confidence`, optional, is the model's own flag; it feeds only the
  trigger figure below.

### How the figures beside the bar are read

The plan names them; these are the rules this code applies where it leaves one open.

- **Merged** (B2 on all three Photos, and the Visits hidden in p1): each Photo's Entry points, in
  board mm, join the Darts found so far one to one, nearest pair first, within 2 mm (pre-fill's
  same-Dart distance); the rest are new Darts. A merged Dart scores at its points' mean.
- **Darts scored right**: over the Visits B2 counts, from p1, the predicted and recorded Scores in
  common as multisets, out of the Darts in the Board.
- **Triggers** (ADR-0008), on p1 alone: the Board not found; fewer Darts found than were thrown, `out`
  included; a `low_confidence` Entry point; an Entry point within 2 mm of a wire's centre line. The
  fourth, Photos disagreeing on a segment, needs a second Photo and is not read on p1.

## labelme

`label` and `review` open one labelme window per Photo through `uvx`, so labelme (GPL-3.0) stays out
of this lockfile and out of anything that trains or ships. The pin lives in `labelme.py`:

- **labelme 7.9.1**, the newest release at least two weeks old on 2026-11-13.
- **Resolved as of 2026-10-26** (`uvx --exclude-newer`). labelme's own dependencies are unbounded,
  and on 2026-11-13 a fresh `uvx labelme==7.9.1` pulled osam 0.11.3, released that day, which crashes
  7.9.1 at start-up (`module 'osam' has no attribute 'apis'`). Resolving as of the release date gives
  the environment 7.9.1 shipped against.
- **`--python`, the version in `.python-version`**, so the interpreter labelme runs on does not
  depend on the machine.
- **`--config '{with_image_data: false, auto_save: true}'`**, so a stray `~/.labelmerc` cannot embed
  the Photo in a label: given `--config`, labelme does not read `~/.labelmerc`.
- **Offline.** The only network code in 7.9.1 is its AI tools' model download, which runs only when a
  model's download button is clicked; there is no setting that turns the tools off. The windows run
  with `UV_OFFLINE=1` and every proxy variable pointed at an unreachable address, so a click by mistake
  fails instead of downloading. Checked on 2026-11-13 by running a window for 20 s under
  `strace -f -e trace=connect`: no connection of any kind. Only `label` and `review` first run
  `uvx … labelme --version` with the network, to fetch labelme into uv's cache.

To move the pin: pick the newest release at least two weeks old, set `RESOLVED_AS_OF` to the day
after it, read its CLI (`--config`, `--labels`, `--validate-label`, `--label-flags`, `--output`) and
`_config/default_config.yaml` again, and open one Photo with a pre-filled label before relabelling
anything.

## Scoring at a wire

`board.py` scores a board-millimetre point by ADR-0008's bands with *w* = 1.5 mm. A point that lands
inside a wire scores on the side of the wire's centre line it falls on, since a Dart enters on one
side or the other (WDF §3.03); a point exactly on a centre line scores on its outer, or clockwise,
side. Board millimetres put x to the right and y up, with the bull at the origin.
`tests/scoring-cases.toml` holds the cases phase 1's Kotlin test reads too.

## Tests

```bash
uv run --directory ml python -m unittest discover -s tests
```

They need `jpegtran` and no data: the Photos and labels are built from `board.py` in the test.

## Dependencies and their licences

Re-read this table whenever the lockfile gains a package. The rule is ADR-0008's: permissive licences
only for the code we adapt, train with, or ship. A runtime library bundled inside a wheel under a
runtime exception or the LGPL is allowed, because `ml/` never ships and the app ships only weights,
and is listed in the last column: today NumPy's libgfortran and libquadmath.

| Package | Licence | Bundled in the Linux wheel |
| --- | --- | --- |
| NumPy 2.5.4 | BSD-3-Clause | OpenBLAS (BSD-3-Clause); libgfortran (GPL-3.0 with the GCC Runtime Library Exception); libquadmath (LGPL-2.1-or-later) |
| Pillow 13.0.0 | MIT-CMU | libjpeg-turbo, libpng, zlib, libtiff, libwebp, lcms2, OpenJPEG, HarfBuzz, Brotli, libavif and others, all permissive; FreeType under its FTL (dual-licensed FTL or GPL-2.0) |
| tomli-w 1.2.0 | MIT | — |

Outside the lockfile: **labelme** (GPL-3.0) runs beside it through `uvx` and never ships;
**jpegtran** (libjpeg-turbo, IJG and BSD-style) is a system tool. **OpenCV is not used**: nothing in
the loop needs it.
