from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

from . import DartsMlError, labelme
from .check import check
from .deepdarts import RECORDS as DEEPDARTS_RECORDS, convert, overlay_sample
from .evaluate import LABELS, evaluate, report
from .export_format import Format, check_record, exported_path
from .heldout import MANIFEST, HeldOutError, HeldOutSet, file_sha256, freeze, frozen_before, verify
from .ingest import ingest, jpegtran_version
from .kernel_search import explain_failed_search, seconds_asleep
from .marked import PACKAGE
from .overlay import overlay
from .paths import DataDir, Round, public_set, render_set, repo_roots, run_config
from .prefill import prefill
from .records import RECORDS, build
from .renders import LOOKS, MAX_RESIDUAL_PX
from .repeatability import repeatability
from .review import review

_INPUT_MULTIPLE = 32
ENTRY_STRIDES = (2, 4)
WEIGHTS = ("best", "last")
TUNE_THRESHOLDS = (0.12, 0.15, 0.18, 0.20, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.29, 0.30, 0.32, 0.34,
                   0.36, 0.38, 0.40, 0.45, 0.55)
TUNE_APART_MM = (0.0, 4.0, 6.0, 8.0, 10.0, 12.0)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except DartsMlError as error:
        print(f"darts-ml {args.step}: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        explained = explain_failed_search(error, seconds_asleep())
        if explained is None:
            raise
        print(f"darts-ml {args.step}: {explained}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darts-ml", description="Darts Scorer's labelling loop (phase M1) and its model (phase M2)")
    steps = parser.add_subparsers(dest="step", required=True)

    def step(name: str, handler, help_: str, *, capture_session=True, round_=False):
        sub = steps.add_parser(name, help=help_, description=help_)
        if capture_session:
            sub.add_argument("capture_session", help="such as s01")
        if round_:
            sub.add_argument("--round", dest="round_", type=Round, choices=list(Round), default=Round.A,
                             metavar="{a,b,c}", help="the labelling round; b and c are the gate's repeats")
        sub.set_defaults(handler=handler)
        return sub

    step("paths", _paths, "print DARTS_DATA, refuse one inside the repo, and check for jpegtran", capture_session=False)
    step("ingest", _ingest, "inbox → named, losslessly rotated, metadata-stripped Photos")
    step("label", _label, f"pass 1: open each unlabelled Photo in labelme {labelme.PINNED}", round_=True)
    step("prefill", _prefill, "pass 2: Hand points → all 80 crossings; Entry points suggested across a Visit", round_=True)
    step("review", _review, "pass 3: confirm each Photo and record it in the review manifest", round_=True)
    checker = step("check", _check, "label QA; must come back clean", capture_session=False, round_=True)
    checker.add_argument("capture_sessions", nargs="*", help="such as s01; or --all")
    checker.add_argument("--all", action="store_true", help="every Capture session with a sheet")
    step("overlay", _overlay, "draw the rings, crossings and scored Entry points onto each Photo", round_=True)
    step("repeatability", _repeatability, "the gate's figures: rounds a, b and c compared in board mm")
    manifest_help = f"the frozen manifest; default {MANIFEST}"
    frozen = step("freeze-held-out", _freeze, "hash every held-out Photo, label, sheet and review manifest into the manifest",
                  capture_session=False)
    frozen.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    frozen.add_argument("--replace", action="store_true",
                        help="overwrite an existing manifest; its commit says why (phase-M1.md §6)")
    verifier = step("verify-held-out", _verify, "fail on any held-out file missing or changed since the freeze",
                    capture_session=False)
    verifier.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    builder = step("build", _build, "write the training records, refusing every held-out Photo", capture_session=False)
    builder.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    evaluator = step("evaluate", _evaluate, "the bar for phase 1's model (phase-M1.md §7), read on the Held-out set",
                     capture_session=False)
    evaluator.add_argument("--predictions", required=True, metavar="{labels,FILE}",
                           help=f"`{LABELS}` to read the labels as the predictions, or a predictions JSON file (ml/README.md)")
    evaluator.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    trainer = step("train", _train, "train the keypoint model (phase-M2.md); --probe times 200 steps for the gate",
                   capture_session=False)
    trainer.add_argument("--probe", action="store_true",
                         help="time 200 steps on DeepDarts' training split and project an epoch (gate A)")
    trainer.add_argument("--name", help="the run's name; it is written to $DARTS_DATA/runs/<date>-<name>/")
    trainer.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto",
                         help="gpu: an AMD GPU through ROCm or an NVIDIA one through CUDA; auto: the GPU if PyTorch sees one, else the CPU")
    trainer.add_argument("--steps", type=_positive, default=200, help="--probe only; default 200")
    trainer.add_argument("--epochs", type=_positive, default=30)
    trainer.add_argument("--size", type=_input_size, default=512,
                         help=f"input size in pixels, a multiple of {_INPUT_MULTIPLE}; default 512")
    trainer.add_argument("--batch", type=_positive, default=16)
    trainer.add_argument("--lr", type=float, default=1e-3)
    trainer.add_argument("--workers", type=_non_negative, default=8)
    trainer.add_argument("--seed", type=int, default=0)
    trainer.add_argument("--no-augment", dest="augment", action="store_false", help="train on the Photos as they are")
    trainer.add_argument("--board-only", action="store_true", help="Calibration points only, no Entry points (checkpoint C)")
    trainer.add_argument("--bf16", action="store_true", help="bfloat16 autocast on the GPU")
    trainer.add_argument("--channels-last", action="store_true", help="channels-last memory layout")
    trainer.add_argument("--init", metavar="RUN",
                         help="start from that run's best weights instead of from scratch; whatever does not fit starts fresh")
    trainer.add_argument("--freeze-norm", action="store_true",
                         help="keep the BatchNorm statistics of the run --init names instead of re-estimating them from "
                              "the training batches")
    trainer.add_argument("--entry-stride", type=int, choices=ENTRY_STRIDES, default=2,
                         help="the Entry heatmap's stride; 4 is C's and D's layout, one output with the Calibration points")
    trainer.add_argument("--ring-weight", type=_non_negative_float, default=None,
                         help="extra penalty on a false Entry peak in the ring around a real one, in units of the "
                              "ordinary one; 0 turns the ring off; default 4")
    trainer.add_argument("--ring-mm", type=_non_negative_float, nargs=2, metavar=("INNER", "OUTER"), default=None,
                         help="the ring's edges in Board millimetres from the Entry point; default 4 20")
    trainer.add_argument("--renders", type=_render_sets, default=(), metavar="SET[,SET]",
                         help="also train on these render sets under $DARTS_DATA/renders/, a tenth of each set's frames "
                              "held out by --seed and read each epoch beside DeepDarts val, never chosen on")
    trainer.add_argument("--render-weight", type=_positive_float, default=None,
                         help="how often a render is drawn against a DeepDarts Photo, overall; 0.5, the default, makes "
                              "renders a third of each batch")
    trainer.add_argument("--public", type=_public_sets, default=(), metavar="SET[,SET]",
                         help="also train on these public sets under $DARTS_DATA/public/, the last tenth of each "
                              "series' frame numbers held out and read each epoch beside DeepDarts val, never chosen on")
    trainer.add_argument("--public-weight", type=_positive_float, default=None,
                         help="how often a public frame is drawn against a DeepDarts Photo, overall; default 0.3")
    predictor = step("predict", _predict, "the predictions file `evaluate` reads, from a run's weights, on the Held-out set",
                     capture_session=False)
    predictor.add_argument("--run", required=True, help="the run folder's name under $DARTS_DATA/runs/")
    predictor.add_argument("--weights", choices=WEIGHTS, default="best")
    predictor.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto")
    predictor.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    predictor.add_argument("--out", type=Path, help="default: predictions-held-out-<weights>-<time>.json in the run folder")
    predictor.add_argument("--workers", type=_non_negative, default=4)
    formats = {"type": Format, "choices": list(Format), "required": True, "dest": "format_"}
    exporter = step("export", _export, "a run's model in an on-device runtime's format, written into the run folder "
                    "(phase-M2.md §5)", capture_session=False)
    exporter.add_argument("--run", required=True, help="the run folder's name under $DARTS_DATA/runs/")
    exporter.add_argument("--weights", choices=WEIGHTS, default="best")
    exporter.add_argument("--format", **formats)
    parity = step("export-parity", _export_parity, "the exported model's points against PyTorch's, both on the CPU, "
                  "through both passes on DeepDarts' Photos", capture_session=False)
    parity.add_argument("--run", required=True)
    parity.add_argument("--weights", choices=WEIGHTS, default="best")
    parity.add_argument("--format", **formats)
    parity.add_argument("--split", choices=("train", "val"), default="val")
    parity.add_argument("--workers", type=_non_negative, default=4)
    parity.add_argument("--threads", type=_positive, help="CPU threads for each runtime; default: each runtime's own")
    bench = step("runtime-bench", _runtime_bench, "each runtime's native libraries per ABI, from its pinned AAR; with a "
                 "device attached, the exported models' latency on it (phase-M2.md §5)", capture_session=False)
    bench.add_argument("--run", help="the run whose exported models to time; without it, sizes only")
    bench.add_argument("--weights", choices=WEIGHTS, default="best")
    bench.add_argument("--threads", type=_non_negative, nargs="+", default=[0, 4],
                       help="CPU thread counts to time, 0 for the runtime's default; default: 0 4")
    bench.add_argument("--warmup", type=_non_negative, default=5)
    bench.add_argument("--runs", type=_positive, default=60)
    fixtures = step("phone-fixtures", _phone_fixtures, "the files phase 1's Kotlin unit tests hold the port to, "
                    "written into app/src/test/resources/scoring/ (phase-1.md Tests), and MediaFilesTest's Display P3 "
                    "source, into app/src/androidTest/assets/", capture_session=False)
    fixtures.add_argument("--run", help="also the decoding fixtures, from that run's exported LiteRT model on "
                          "DeepDarts' val Photos; without it, the scoring table, RANSAC's draws and the warp only")
    fixtures.add_argument("--weights", choices=WEIGHTS, default="best")
    phone = step("phone-parity", _phone_parity, "phase 1's gate: the app's pipeline on the attached phone or "
                 "emulator against Python's locate(), on DeepDarts' val Photos written through MediaFiles "
                 "(phase-1.md §1)", capture_session=False)
    phone.add_argument("--run", required=True, help="the run whose best.tflite the app ships")
    phone.add_argument("--weights", choices=WEIGHTS, default="best")
    phone.add_argument("--photos", type=_positive, default=150, help="how many val Photos; default 150")
    phone.add_argument("--display-p3", type=_non_negative, default=20,
                       help="how many of those also go as a Display P3 copy, as a Xiaomi tags its Photos, to check "
                       "the app stores them as sRGB and reads them as Python reads the stored files; default 20")
    phone.add_argument("--workers", type=_non_negative, default=4)
    puller = step("pull-marked", _pull_marked, "copy the debug build's marked Visits off a phone into "
                  "$DARTS_DATA/phone-captures/<date>/, and again each one kept again since", capture_session=False)
    puller.add_argument("--serial", required=True, help="the adb serial of the phone or emulator to pull from")
    puller.add_argument("--package", default=PACKAGE, help=f"the debug build's applicationId; default {PACKAGE}")
    puller.add_argument("--delete-after", action="store_true",
                        help="then delete on the phone each file that is here unchanged")
    marked = step("evaluate-marked", _evaluate_marked, "a run's reading of the owner's marked Visits under "
                  "$DARTS_DATA/phone-captures/, the real test set: read once a run is chosen, never to choose one",
                  capture_session=False)
    marked.add_argument("--run", required=True, help="the run folder's name under $DARTS_DATA/runs/")
    marked.add_argument("--weights", choices=WEIGHTS, default="best")
    marked.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto")
    marked.add_argument("--workers", type=_non_negative, default=4)
    renders = steps.add_parser("renders", help="synthetic renders from darts-render, as training records",
                               description="synthetic renders from darts-render (ml/README.md, *Synthetic renders*)")
    render_actions = renders.add_subparsers(dest="action", required=True)
    importer = render_actions.add_parser("import", help="a renderer output folder → renders/<set>/, its images and "
                                         "records.jsonl, with a manifest naming the renderer's commit and options")
    importer.add_argument("source", type=Path, help="the folder the renderer wrote, holding annotations/ and rgb/")
    importer.add_argument("--set", dest="set_", type=_render_set, required=True, help="the set's name, such as owner-768")
    made = importer.add_mutually_exclusive_group(required=True)
    made.add_argument("--renderer", type=Path, help="the darts-render clone that rendered it; its HEAD is recorded")
    made.add_argument("--renderer-commit", help="the darts-render commit that rendered it, when the clone is elsewhere")
    importer.add_argument("--look", choices=LOOKS, required=True, help="the --look it was rendered with")
    importer.add_argument("--option", action="append", default=[], type=_option, metavar="KEY=VALUE",
                          help="any other renderer setting to record, such as width=768; repeat for each")
    importer.add_argument("--max-residual-px", type=_positive_float, default=MAX_RESIDUAL_PX,
                          help=f"refuse a frame whose keypoints fit one plane worse than this; default {MAX_RESIDUAL_PX}")
    importer.set_defaults(handler=_renders_import)
    deepdarts = steps.add_parser("deepdarts", help="DeepDarts' labels: convert them safely, and check the conversion by eye",
                                 description="DeepDarts' labels (phase-M1.md §4)")
    actions = deepdarts.add_subparsers(dest="action", required=True)
    actions.add_parser("convert", help="labels.pkl → deepdarts/records.jsonl, through the restricted unpickler"
                       ).set_defaults(handler=_deepdarts_convert)
    sampler = actions.add_parser("overlay", help="draw the Board from DeepDarts' four points onto a sample of its Photos")
    sampler.add_argument("--sample", type=_positive, default=10, help="how many Photos; default 10")
    sampler.add_argument("--seed", type=int, default=0, help="which sample; default 0")
    sampler.set_defaults(handler=_deepdarts_overlay)
    scorer = actions.add_parser("score", help="a run's figures on DeepDarts' val or test split (phase-M2.md R2, R3)")
    scorer.add_argument("--run", required=True)
    scorer.add_argument("--weights", choices=WEIGHTS, default="best")
    scorer.add_argument("--split", choices=("val", "test"), default="val")
    scorer.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto")
    scorer.add_argument("--workers", type=_non_negative, default=4)
    scorer.add_argument("--as-stored", action="store_true", help="score copies written as MediaFiles writes the "
                        "photos kind (2048 px long edge, JPEG q85) instead of the Photos as they are (phase-1.md §1)")
    scorer.add_argument("--entry-threshold", type=_probability, default=None,
                        help="the heat an Entry point must reach to be kept; the shipped ENTRY_THRESHOLD by default")
    scorer.set_defaults(handler=_deepdarts_score)
    tuner = actions.add_parser("tune", help="a run's figures on DeepDarts' val split under each rule for keeping Entry points")
    tuner.add_argument("--run", required=True)
    tuner.add_argument("--weights", choices=WEIGHTS, default="best")
    tuner.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto")
    tuner.add_argument("--workers", type=_non_negative, default=4)
    tuner.set_defaults(handler=_deepdarts_tune)
    grouped = actions.add_parser("grouped", help="the share of Dart pairs under 10 mm that the targets decode as two")
    grouped.add_argument("--split", choices=("train", "val"), default="val")
    grouped.add_argument("--size", type=_input_size, default=512)
    grouped.add_argument("--entry-stride", type=int, choices=ENTRY_STRIDES, default=2)
    grouped.set_defaults(handler=_deepdarts_grouped)
    return parser


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive count")
    return value


def _non_negative(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"{value} is negative")
    return value


def _non_negative_float(text: str) -> float:
    value = float(text)
    if not value >= 0:
        raise argparse.ArgumentTypeError(f"{text} is not a non-negative number")
    return value


def _positive_float(text: str) -> float:
    value = float(text)
    if not 0 < value < float("inf"):
        raise argparse.ArgumentTypeError(f"{text} is not a positive number")
    return value


def _render_set(text: str) -> str:
    try:
        return render_set(text)
    except DartsMlError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _render_sets(text: str) -> tuple[str, ...]:
    return _distinct(tuple(map(_render_set, text.split(","))), text)


def _public_sets(text: str) -> tuple[str, ...]:
    try:
        return _distinct(tuple(map(public_set, text.split(","))), text)
    except DartsMlError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _distinct(names: tuple[str, ...], text: str) -> tuple[str, ...]:
    if len(set(names)) != len(names):
        raise argparse.ArgumentTypeError(f"{text} names a set twice")
    return names


def _option(text: str) -> tuple[str, str]:
    key, equals, value = text.partition("=")
    if not equals or not key:
        raise argparse.ArgumentTypeError(f"{text!r} is not KEY=VALUE")
    return key, value


def _probability(text: str) -> float:
    value = float(text)
    if not 0 < value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not between 0 and 1")
    return value


def _input_size(text: str) -> int:
    value = _positive(text)
    if value % _INPUT_MULTIPLE:
        raise argparse.ArgumentTypeError(
            f"{value} is not a multiple of {_INPUT_MULTIPLE}, the backbone's stride; the output grid would not match the targets")
    return value


def _paths(args) -> int:
    data = DataDir.from_environment()
    print(f"DARTS_DATA  {data.root}")
    print(f"repository  {', '.join(map(str, sorted(repo_roots()))) or 'not found'}")
    version = jpegtran_version()
    print(f"jpegtran    {version or 'MISSING: install libjpeg-turbo (libjpeg-turbo-progs)'}")
    return 0 if version else 1


def _ingest(args) -> int:
    data = DataDir.from_environment()
    names = ingest(data, args.capture_session)
    print(f"{len(names)} Photos ingested into {data.photos(args.capture_session)}")
    print(f"{data.inbox(args.capture_session)} still holds the phone's files, GPS included: "
          "delete them once you have looked at the Photos")
    return 0


def _label(args) -> int:
    labelme.fetch()
    opened = labelme.label(DataDir.from_environment(), args.capture_session, args.round_)
    print(f"{opened} Photos opened")
    return 0


def _prefill(args) -> int:
    done = prefill(DataDir.from_environment(), args.capture_session, args.round_)
    print(f"{len(done)} Photos pre-filled" + (f": {', '.join(done)}" if done else ""))
    return 0


def _review(args) -> int:
    labelme.fetch()
    recorded = review(DataDir.from_environment(), args.capture_session, args.round_)
    print(f"{recorded} reviews recorded")
    return 0


def _check(args) -> int:
    data = DataDir.from_environment()
    names = sorted(p.stem for p in data.sheets().glob("*.toml")) if args.all else args.capture_sessions
    if not names:
        raise DartsMlError("name a Capture session, or pass --all")
    clean = True
    for name in names:
        report = check(data, name, args.round_)
        for finding in report.findings:
            print(finding)
        for mismatch in report.open_mismatches:
            print(f"open mismatch  {mismatch}")
        agreement = report.across_angles_mm
        if agreement:
            ordered = sorted(agreement)
            p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
            print(f"{name}: across Angles, {len(agreement)} Entry point pairs, 95th percentile {p95:.2f} mm")
        print(f"{name}: {'clean' if report.clean else f'{len(report.findings)} findings'}")
        clean &= report.clean
    return 0 if clean else 1


def _overlay(args) -> int:
    data = DataDir.from_environment()
    written = overlay(data, args.capture_session, args.round_)
    print(f"{len(written)} overlays written to {data.overlays(args.capture_session, args.round_)}")
    return 0


def _repeatability(args) -> int:
    reading = repeatability(DataDir.from_environment(), args.capture_session)
    for name, spread in reading.spreads.items():
        if spread is None:
            print(f"{name:28}  no Photos")
        else:
            print(f"{name:28}  median {spread.median_mm:.3f} mm  95th {spread.p95_mm:.3f} mm  ({spread.count})")
    for round_, minutes in reading.minutes.items():
        print(f"round {round_.value}: pass 1 {minutes.pass_1:.1f} min, pass 3 {minutes.pass_3:.1f} min "
              f"per Photo ({minutes.photos} Photos)")
    for skipped in reading.skipped:
        print(f"left out: {skipped}")
    verdict = reading.verdict
    print(f"verdict: {verdict}" if verdict else "verdict: not yet; it needs rounds a, b and c reviewed")
    return 0


def _freeze(args) -> int:
    if args.manifest.exists() and not args.replace:
        raise HeldOutError(f"{args.manifest} already freezes a Held-out set; pass --replace to overwrite it on purpose")
    held = freeze(DataDir.from_environment())
    dropped = sorted(frozen_before(args.manifest) - set(held.capture_sessions))
    if dropped:
        raise HeldOutError(f"{args.manifest} has frozen {', '.join(dropped)}, and this freeze would drop it; "
                           "a frozen Capture session is only ever added to (phase-M1.md §6)")
    held.save(args.manifest)
    print(f"{len(held.photos)} Photos of {', '.join(sorted(held.capture_sessions))} frozen into {args.manifest}")
    print("Commit it; a later change to it gives its reason in the commit body (phase-M1.md §6)")
    return 0


def _verify(args) -> int:
    held = HeldOutSet.load(args.manifest)
    problems = verify(DataDir.from_environment(), held)
    for problem in problems:
        print(problem)
    if problems:
        print(f"the Held-out set does not match {args.manifest}: {len(problems)} problems")
        return 1
    print(f"{len(held.photos)} Photos of {len(held.capture_sessions)} Capture sessions match {args.manifest}")
    return 0


def _build(args) -> int:
    data = DataDir.from_environment()
    built = build(data, HeldOutSet.load(args.manifest))
    for photo, reason in built.skipped:
        print(f"skipped  {photo}: {reason}")
    for photo, reason in built.refused:
        print(f"refused  {photo}: {reason}")
    print(f"{built.records} records written to {data.build() / RECORDS}; "
          f"{len(built.refused)} held-out Photos refused, {len(built.skipped)} skipped")
    return 0


def _evaluate(args) -> int:
    result = evaluate(DataDir.from_environment(), args.predictions, args.manifest)
    print("\n".join(report(result)))
    return 0 if result.met else 1


def _train(args) -> int:
    from .locate import Speed
    from .train import PUBLIC_WEIGHT, RENDER_WEIGHT, RING_WEIGHT, RunConfig, probe, probe_path, save, train
    from .training_data import RING_INNER_MM, RING_OUTER_MM

    data = DataDir.from_environment()
    speed = Speed(args.bf16, args.channels_last)
    ring_weight = RING_WEIGHT if args.ring_weight is None else args.ring_weight
    inner, outer = (RING_INNER_MM, RING_OUTER_MM) if args.ring_mm is None else args.ring_mm
    if inner >= outer:
        raise DartsMlError(f"--ring-mm {inner:g} {outer:g}: the inner edge must be inside the outer")
    if args.probe:
        result = probe(data, args.device, args.steps, args.size, args.batch, args.workers, args.seed, speed,
                       args.entry_stride, ring_weight)
        target = probe_path(data, result, dt.datetime.now())
        save(result, target)
        print(f"{result.hardware}: {result.images_per_second:.1f} Photos/s at {result.size} px, batch {result.batch}; "
              f"an epoch of {result.training_photos} Photos takes {result.epoch_minutes:.1f} min")
        print(f"loss: step 1 {result.losses[0]:.3f}, step {result.steps} {result.losses[-1]:.3f}; written to {target}")
        return 0
    if not args.name:
        raise DartsMlError("name the run with --name, or pass --probe")
    if args.render_weight is not None and not args.renders:
        raise DartsMlError("--render-weight weighs the renders --renders names; name a set")
    if args.public_weight is not None and not args.public:
        raise DartsMlError("--public-weight weighs the frames --public names; name a set")
    config = RunConfig(args.name, args.device, args.epochs, args.size, args.batch, args.lr, workers=args.workers,
                       seed=args.seed, augment=args.augment, board_only=args.board_only, bf16=args.bf16,
                       channels_last=args.channels_last, init=args.init, entry_stride=args.entry_stride,
                       ring_weight=ring_weight, ring_inner_mm=inner, ring_outer_mm=outer, renders=args.renders,
                       render_weight=RENDER_WEIGHT if args.render_weight is None else args.render_weight,
                       public=args.public,
                       public_weight=PUBLIC_WEIGHT if args.public_weight is None else args.public_weight,
                       freeze_norm=args.freeze_norm)
    folder = train(data, config)
    print(f"written to {folder}")
    return 0


def _predict(args) -> int:
    from .predict import predict

    target = predict(DataDir.from_environment(), args.run, args.weights, args.device, args.manifest, args.out,
                     args.workers)
    print(f"written to {target}")
    print("Reading it with `darts-ml evaluate` is one of phase M2's three readings of the bar (D6)")
    return 0


def _export(args) -> int:
    from .export import export, write_record
    from .train import load_weights

    folder, config = run_config(DataDir.from_environment(), args.run)
    weights, size = folder / f"{args.weights}.pt", config["size"]
    if not weights.exists():
        raise DartsMlError(f"no weights at {weights}")
    weights_sha256 = file_sha256(weights)
    exported = export(load_weights(weights, "cpu"), size, args.format_, exported_path(folder, args.weights, args.format_))
    write_record(exported, args.run, weights.name, weights_sha256, size)
    print(f"{exported.path}: {exported.size_bytes} bytes; input 1×3×{size}×{size} float32, the raw heads out")
    print("operations: " + ", ".join(f"{name} {count}" for name, count in exported.operations.items()))
    print(f"left outside {args.format_}'s own operations: {', '.join(exported.outside) or 'none'}")
    return 0


def _export_parity(args) -> int:
    import torch

    from .export import parity, runtime
    from .locate import Inference, locate
    from .train import load_weights
    from .training_data import deepdarts_samples

    data = DataDir.from_environment()
    folder, config = run_config(data, args.run)
    weights, size = folder / f"{args.weights}.pt", config["size"]
    path = exported_path(folder, args.weights, args.format_)
    check_record(path, weights)
    if args.threads:
        torch.set_num_threads(args.threads)
    photos = [s.photo for s in deepdarts_samples(data, args.split)]
    print(f"{len(photos)} DeepDarts {args.split} Photos through PyTorch, then {args.format_} ...", file=sys.stderr, flush=True)
    reference = locate(Inference(load_weights(weights, "cpu"), "cpu", size, config["batch"], args.workers), photos)
    exported = locate(Inference(runtime(args.format_, path, args.threads), "cpu", size, 1, args.workers), photos)
    reading = parity(reference, exported)
    print("\n".join(reading.lines()))
    return 0 if reading.same else 1


def _runtime_bench(args) -> int:
    import shutil

    from .runtime_bench import (RUNTIMES, Device, attached_devices, bench, choose_device, fetch, latency_lines,
                                native_libraries, run_tool, size_lines)

    sys.stdout.reconfigure(line_buffering=True)
    data = DataDir.from_environment()
    cache = data.runtimes()
    aars = {format_: [fetch(a, cache) for a in runtime.aars] for format_, runtime in RUNTIMES.items()}
    for runtime in RUNTIMES.values():
        print(f"{runtime.label}: " + ", ".join(f"{a.url} sha256 {a.sha256}" for a in runtime.aars))
    print("\n".join(size_lines({RUNTIMES[f].label: [lib for aar in found for lib in native_libraries(aar)]
                                for f, found in aars.items()})))
    print("deflated: raw deflate at zlib's default level, near what a compressed APK or Play's download carries; "
          "an APK built with AGP's default packaging stores them uncompressed")
    if not args.run:
        return 0
    folder, config = run_config(data, args.run)
    size, weights = config["size"], folder / f"{args.weights}.pt"
    models, refused = {}, []
    for format_ in RUNTIMES:
        path = exported_path(folder, args.weights, format_)
        try:
            check_record(path, weights)
        except DartsMlError as error:
            refused.append(f"{format_} not timed: {error}")
            continue
        models[format_] = path
    if not models:
        raise DartsMlError("no exported model to time:\n" + "\n".join(refused))
    for line in refused:
        print(line)
    for path in models.values():
        print(f"model {path.name}: {path.stat().st_size} bytes")
    if shutil.which("adb") is None:
        print("adb is not on PATH: latency not read")
        return 0
    serial = choose_device(attached_devices(run_tool(["adb", "devices"])))
    if serial is None:
        print("no device attached (adb devices): latency not read")
        return 0
    device = Device(serial)
    print("\n".join(device.description()))
    readings, skipped = bench(device, cache, aars, models, size, args.threads, args.warmup, args.runs)
    print(f"1×3×{size}×{size} float32 per inference; a Photo runs it twice (phase-M2.md §2)")
    print("\n".join(latency_lines(readings) + skipped))
    return 0


def _phone_fixtures(args) -> int:
    from .phone import DISPLAY_P3_SOURCE, FIXTURES, chosen_heads, write_display_p3_source, write_fixtures

    heads = None
    if args.run:
        from .export import runtime
        from .locate import Inference
        from .training_data import deepdarts_samples

        data = DataDir.from_environment()
        folder, config = run_config(data, args.run)
        path = exported_path(folder, args.weights, Format.LITERT)
        check_record(path, folder / f"{args.weights}.pt")
        run = Inference(runtime(Format.LITERT, path), "cpu", config["size"], 1, 0)
        heads = chosen_heads(deepdarts_samples(data, "val"), run, data.root / "phone-parity" / "fixtures")
    for path in [*write_fixtures(FIXTURES, heads), write_display_p3_source(DISPLAY_P3_SOURCE)]:
        print(f"{path}: {path.stat().st_size} bytes")
    return 0


def _phone_parity(args) -> int:
    import shutil

    from .export import runtime
    from .locate import Inference, locate
    from .phone import device_name, display_p3_copies, picked, run_parity, same_model
    from .runtime_bench import Device, attached_devices, choose_device, run_tool
    from .training_data import deepdarts_samples

    sys.stdout.reconfigure(line_buffering=True)
    data = DataDir.from_environment()
    folder, config = run_config(data, args.run)
    path = exported_path(folder, args.weights, Format.LITERT)
    check_record(path, folder / f"{args.weights}.pt")
    same_model(path)
    if shutil.which("adb") is None:
        raise DartsMlError("adb is not on PATH")
    serial = choose_device(attached_devices(run_tool(["adb", "devices"])))
    if serial is None:
        raise DartsMlError("no device attached (adb devices); start an emulator and install both APKs first")
    samples = picked(deepdarts_samples(data, "val"), args.photos)
    run = Inference(runtime(Format.LITERT, path), "cpu", config["size"], 1, args.workers)
    sources = [(device_name(s), s.photo) for s in samples]
    parity = data.root / "phone-parity" / args.run
    sources += display_p3_copies(sources, parity / "display-p3", args.display_p3) if args.display_p3 else []
    report = run_parity(Device(serial), sources, parity, args.run, lambda photos: locate(run, photos),
                        lambda line: print(line, file=sys.stderr, flush=True))
    print(report)
    return 0 if report.startswith("PASS") else 1


def _pull_marked(args) -> int:
    import shutil

    from .marked import Phone, pull

    captures = DataDir.from_environment().phone_captures()
    if shutil.which("adb") is None:
        raise DartsMlError("adb is not on PATH")
    copied = pull(Phone(args.serial, args.package), captures, dt.date.today().isoformat(),
                  lambda line: print(line, file=sys.stderr, flush=True), args.delete_after)
    print(f"{copied} copied into {captures}")
    return 0


def _evaluate_marked(args) -> int:
    from .locate import Inference, Speed, locate
    from .marked_reading import NOTE, marked_visits, read_marked
    from .train import load_weights, resolve_device, use_tuned_kernels

    data = DataDir.from_environment()
    folder, config = run_config(data, args.run)
    captures = data.phone_captures()
    visits, skipped = marked_visits(captures)
    for name, reason in skipped:
        print(f"skipped  {name}: {reason}")
    if not visits:
        raise DartsMlError(f"no marked Visit under {captures}; `darts-ml pull-marked` copies them off the phone")
    print(NOTE, file=sys.stderr, flush=True)
    use_tuned_kernels(data)
    device, _ = resolve_device(args.device)
    speed = Speed(config["bf16"] and device == "cuda", config["channels_last"])
    model = load_weights(folder / f"{args.weights}.pt", device).to(memory_format=speed.memory)
    print(f"{len(visits)} marked Visits through {args.run} {args.weights}.pt ...", file=sys.stderr, flush=True)
    located = locate(Inference(model, device, config["size"], config["batch"], args.workers, speed),
                     [v.photo for v in visits])
    print(f"{len(visits)} marked Visits from {captures}, {len(skipped)} skipped; run {args.run}, {args.weights}.pt")
    print("\n".join(read_marked(visits, located).lines()))
    print(NOTE)
    return 0


def _renders_import(args) -> int:
    from .renders import Renderer, import_renders, renderer_commit
    from .train import commit

    commit_ = args.renderer_commit or renderer_commit(args.renderer)
    imported = import_renders(DataDir.from_environment(), args.source, args.set_,
                              Renderer(commit_, args.look, dict(args.option)), args.max_residual_px,
                              lambda line: print(line, file=sys.stderr, flush=True), commit())
    for frame, reason in imported.refused:
        print(f"refused  {frame}: {reason}")
    print(f"{imported.records} frames with {imported.darts} Darts written to {imported.folder}; "
          f"{len(imported.refused)} frames refused, {imported.off_image} Darts off the image dropped, "
          f"{imported.zones_differ} scored otherwise than the renderer's zone; renderer {commit_}")
    return 0


def _deepdarts_score(args) -> int:
    from .decode import EntryRule
    from .locate import Inference, Speed, figures, locate
    from .train import load_weights, resolve_device, use_tuned_kernels
    from .training_data import deepdarts_reading_samples

    data = DataDir.from_environment()
    folder, config = run_config(data, args.run)
    use_tuned_kernels(data)
    device, _ = resolve_device(args.device)
    speed = Speed(config["bf16"] and device == "cuda", config["channels_last"])
    model = load_weights(folder / f"{args.weights}.pt", device).to(memory_format=speed.memory)
    samples = deepdarts_reading_samples(data, args.split)
    with tempfile.TemporaryDirectory(prefix="as-stored-", dir=data.root) as scratch:
        if args.as_stored:
            from .phone import as_stored_samples

            samples = as_stored_samples(samples, Path(scratch))
        print(f"{len(samples)} DeepDarts {args.split} Photos{' as stored' if args.as_stored else ''} ...",
              file=sys.stderr, flush=True)
        rule = EntryRule() if args.entry_threshold is None else EntryRule(threshold=args.entry_threshold)
        reading = figures(samples, locate(Inference(model, device, config["size"], config["batch"], args.workers,
                                                    speed, rule), [s.photo for s in samples]))
    print(f"Entry threshold {rule.threshold}")
    print("\n".join(reading.lines()))
    return 0


def _deepdarts_tune(args) -> int:
    from .decode import EntryRule
    from .locate import Inference, Speed, figures, locate, refiltered
    from .train import load_weights, resolve_device, use_tuned_kernels
    from .training_data import deepdarts_reading_samples

    data = DataDir.from_environment()
    folder, config = run_config(data, args.run)
    use_tuned_kernels(data)
    device, _ = resolve_device(args.device)
    speed = Speed(config["bf16"] and device == "cuda", config["channels_last"])
    model = load_weights(folder / f"{args.weights}.pt", device).to(memory_format=speed.memory)
    samples = deepdarts_reading_samples(data, "val")
    print(f"{len(samples)} DeepDarts val Photos ...", file=sys.stderr, flush=True)
    raw = locate(Inference(model, device, config["size"], config["batch"], args.workers, speed, tune_floor()),
                 [s.photo for s in samples])
    print("threshold  apart mm  most  exactly right        d1      d2      Darts right          pairs as two")
    for threshold in TUNE_THRESHOLDS:
        for apart in TUNE_APART_MM:
            for most in (None, 3):
                rule = EntryRule(threshold, apart, most)
                reading = figures(samples, [refiltered(located, rule) for located in raw])
                d1, d2 = (reading.exact_by_folder.get(k) for k in ("d1", "d2"))
                print(f"{threshold:9.2f}  {apart:8.0f}  {most or '-':>4}  {reading.exact!s:<19}  "
                      f"{_percent(d1):>6}  {_percent(d2):>6}  {reading.darts_right!s:<19}  {reading.grouped}")
    return 0


def tune_floor():
    from .decode import EntryRule

    return EntryRule(min(TUNE_THRESHOLDS), 0.0, None)


def _percent(share) -> str:
    return f"{100 * share.hits / share.total:.1f}%" if share and share.total else "-"


def _deepdarts_grouped(args) -> int:
    from .locate import figures, located_from_targets
    from .training_data import deepdarts_samples

    samples = [s for s in deepdarts_samples(DataDir.from_environment(), args.split) if len(s.entries) > 1]
    print(f"{len(samples)} DeepDarts {args.split} Photos with two or more Darts ...", file=sys.stderr, flush=True)
    reading = figures(samples, [located_from_targets(s, args.size, args.entry_stride) for s in samples])
    print(f"targets at {args.size} px, Entry stride {args.entry_stride}, decode {reading.grouped} of the Dart pairs "
          "under 10 mm as two Darts")
    return 0


def _deepdarts_convert(args) -> int:
    data = DataDir.from_environment()
    converted = convert(data)
    for photo, reason in converted.skipped:
        print(f"skipped  {photo}: {reason}")
    splits = ", ".join(f"{count} {split}" for split, count in sorted(converted.splits.items()))
    print(f"{converted.rows} label rows; {converted.records} records of {len(converted.capture_sessions)} "
          f"Capture sessions written to {data.deepdarts() / DEEPDARTS_RECORDS} ({splits}); "
          f"{len(converted.skipped)} skipped")
    return 1 if converted.skipped else 0


def _deepdarts_overlay(args) -> int:
    data = DataDir.from_environment()
    written = overlay_sample(data, args.sample, args.seed)
    print(f"{len(written)} overlays written to {data.deepdarts_overlays()}; "
          "the numbers drawn must match the Board's own (phase-M1.md R3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
