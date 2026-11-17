from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import DartsMlError, labelme
from .check import check
from .deepdarts import RECORDS as DEEPDARTS_RECORDS, convert, overlay_sample
from .evaluate import LABELS, evaluate, report
from .heldout import MANIFEST, HeldOutError, HeldOutSet, freeze, frozen_before, verify
from .ingest import ingest, jpegtran_version
from .overlay import overlay
from .paths import DataDir, Round, repo_roots
from .prefill import prefill
from .records import RECORDS, build
from .repeatability import repeatability
from .review import review

_INPUT_MULTIPLE = 32


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except DartsMlError as error:
        print(f"darts-ml {args.step}: {error}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darts-ml", description="Darts Scorer's labelling loop (phase M1)")
    steps = parser.add_subparsers(dest="step", required=True)

    def step(name: str, run, help_: str, *, capture_session=True, round_=False):
        sub = steps.add_parser(name, help=help_, description=help_)
        if capture_session:
            sub.add_argument("capture_session", help="such as s01")
        if round_:
            sub.add_argument("--round", dest="round_", type=Round, choices=list(Round), default=Round.A,
                             metavar="{a,b,c}", help="the labelling round; b and c are the gate's repeats")
        sub.set_defaults(run=run)
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
    evaluator = step("evaluate", _evaluate, "the bar for opening phase 1 (phase-M1.md §7), read on the Held-out set",
                     capture_session=False)
    evaluator.add_argument("--predictions", required=True, metavar="{labels,FILE}",
                           help=f"`{LABELS}` to read the labels as the predictions, or a predictions JSON file (ml/README.md)")
    evaluator.add_argument("--manifest", type=Path, default=MANIFEST, help=manifest_help)
    trainer = step("train", _train, "train the keypoint model (phase-M2.md); --probe times 200 steps for the gate",
                   capture_session=False)
    trainer.add_argument("--probe", action="store_true", required=True,
                         help="time 200 steps on DeepDarts' training split and project an epoch (gate A)")
    trainer.add_argument("--device", choices=("auto", "gpu", "cpu"), default="auto",
                         help="gpu: an AMD GPU through ROCm or an NVIDIA one through CUDA; auto: the GPU if PyTorch sees one, else the CPU")
    trainer.add_argument("--steps", type=_positive, default=200)
    trainer.add_argument("--size", type=_input_size, default=512,
                         help=f"input size in pixels, a multiple of {_INPUT_MULTIPLE}; default 512")
    trainer.add_argument("--batch", type=_positive, default=16)
    trainer.add_argument("--workers", type=_non_negative, default=8)
    deepdarts = steps.add_parser("deepdarts", help="DeepDarts' labels: convert them safely, and check the conversion by eye",
                                 description="DeepDarts' labels (phase-M1.md §4)")
    actions = deepdarts.add_subparsers(dest="action", required=True)
    actions.add_parser("convert", help="labels.pkl → deepdarts/records.jsonl, through the restricted unpickler"
                       ).set_defaults(run=_deepdarts_convert)
    sampler = actions.add_parser("overlay", help="draw the Board from DeepDarts' four points onto a sample of its Photos")
    sampler.add_argument("--sample", type=_positive, default=10, help="how many Photos; default 10")
    sampler.add_argument("--seed", type=int, default=0, help="which sample; default 0")
    sampler.set_defaults(run=_deepdarts_overlay)
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
    from .train import probe, save

    data = DataDir.from_environment()
    result = probe(data, args.device, args.steps, args.size, args.batch, args.workers)
    target = data.runs() / "probes" / f"{result.device}-{result.size}-{result.batch}.json"
    save(result, target)
    print(f"{result.hardware}: {result.images_per_second:.1f} Photos/s at {result.size} px, batch {result.batch}; "
          f"an epoch of {result.training_photos} Photos takes {result.epoch_minutes:.1f} min")
    print(f"loss: step 1 {result.losses[0]:.3f}, step {result.steps} {result.losses[-1]:.3f}; written to {target}")
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
