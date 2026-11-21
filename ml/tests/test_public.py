import contextlib
import datetime as dt
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_POINTS
from darts_ml.cli import main
from darts_ml.deepdarts import RECORDS as DEEPDARTS_RECORDS
from darts_ml.homography import project
from darts_ml.train import RunConfig, mixing, train, training_loader
from darts_ml.training_data import (PROJECTED_WEIGHT, PUBLIC_GUARD_FRAMES, PUBLIC_MANIFEST, PUBLIC_RECORDS,
                                    RefusedRecord, Sample, deepdarts_samples, framed_targets, public_samples,
                                    public_split)
from synthetic import TemporaryData, board_image, camera, dart_mm

SIZE = (480, 640)
SET = "pose"
MANIFEST = {"set": SET, "title": "Pose", "author": "someone", "url": "https://example.org/pose", "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "mirror": {"url": "https://example.org/mirror", "sha256": "ab" * 32}, "records": 0,
            "refused": [], "credit": "Pose by someone, CC BY 4.0"}


def write_public_set(data, frames, name: str = SET, manifest: dict | None = MANIFEST) -> list[dict]:
    folder = data.public_set(name)
    (folder / "photos").mkdir(parents=True)
    records = []
    for i, frame in enumerate(frames):
        to_image = camera(yaw_deg=i % 7 - 3.0, pitch_deg=8.0, distance_mm=1100.0, focal_px=1500.0, size=SIZE)
        photo = folder / "photos" / f"{frame}.jpg"
        board_image(to_image, size=SIZE).save(photo, "JPEG", quality=90)
        calibration = [{"name": p.name, "x": float(x), "y": float(y), "source": "model", "detected": j % 3 != 0}
                       for j, (p, (x, y)) in enumerate(zip(CALIBRATION_POINTS,
                                                           project(to_image, [p.mm for p in CALIBRATION_POINTS])))]
        tip = project(to_image, [dart_mm("T20")])[0]
        records.append({"source": "public", "set": name, "capture_session": name, "frame": frame,
                        "photo": photo.relative_to(data.root).as_posix(), "width": SIZE[1], "height": SIZE[0],
                        "calibration": calibration,
                        "entries": [{"x": float(tip[0]), "y": float(tip[1]), "inferred": False,
                                     "source": "public-label", "flight": [0.0, 0.0]}], "scores": ["T20"]})
    (folder / PUBLIC_RECORDS).write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    if manifest is not None:
        (folder / PUBLIC_MANIFEST).write_text(json.dumps({**manifest, "records": len(records)}), encoding="utf-8")
    return records


def _sample(frame: str, name: str = SET) -> Sample:
    return Sample(Path(f"/public/{name}/photos/{frame}.jpg"), (), (), name)


def _number(sample: Sample) -> int:
    return int(sample.photo.stem.rsplit("_", 1)[1])


def _series(sample: Sample) -> str:
    return sample.photo.stem.rsplit("_", 1)[0].removesuffix("_cam1").removesuffix("_cam2")


class PublicSamplesTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.records = write_public_set(self.data, ["snap_cam1_1", "snap_cam2_1"])

    def tearDown(self):
        self.td.cleanup()

    def test_a_projected_calibration_point_weighs_less_than_one_the_model_found(self):
        [sample, _] = public_samples(self.data, (SET,))
        detected = [c["detected"] for c in self.records[0]["calibration"]]
        self.assertEqual([w for *_, w in sample.calibration], [1.0 if d else PROJECTED_WEIGHT for d in detected])
        self.assertEqual(len(sample.entries), 1)
        made = framed_targets(sample, np.diag([0.1, 0.1, 1.0]), 64)
        self.assertEqual(made.board_weights[0], PROJECTED_WEIGHT)
        self.assertEqual(made.board_weights[1], 1.0)

    def test_another_source_and_a_missing_set_are_refused(self):
        with self.assertRaisesRegex(DartsMlError, "public/missing"):
            public_samples(self.data, ("missing",))
        path = self.data.public_set(SET) / PUBLIC_RECORDS
        path.write_text(json.dumps({**self.records[0], "source": "render"}) + "\n", encoding="utf-8")
        with self.assertRaises(RefusedRecord):
            public_samples(self.data, (SET,))


class PublicSplitTest(unittest.TestCase):
    def setUp(self):
        gaps = {17, 18, 40}
        self.samples = [_sample(f"snap_usb_cam{c}_{n}") for c in (1, 2) for n in range(1, 101) if n not in gaps]
        self.samples += [_sample(f"snap_{n}") for n in range(23, 999, 11)]

    def test_the_held_out_block_is_the_last_tenth_of_each_series_with_every_camera_at_it(self):
        training, validation = public_split(self.samples)
        self.assertFalse(set(training) & set(validation))
        for series in ("snap_usb", "snap"):
            held = sorted(_number(s) for s in validation if _series(s) == series)
            every = sorted({_number(s) for s in self.samples if _series(s) == series})
            self.assertEqual(sorted(set(held)), every[-round(0.1 * len(every)):], series)
        usb = {(s.photo.stem.split("_")[2], _number(s)) for s in validation if _series(s) == "snap_usb"}
        self.assertEqual({n for c, n in usb if c == "cam1"}, {n for c, n in usb if c == "cam2"})

    def test_no_training_frame_neighbours_a_held_out_one(self):
        training, validation = public_split(self.samples)
        for kept in training:
            for held in validation:
                if _series(kept) == _series(held):
                    self.assertGreater(abs(_number(kept) - _number(held)), PUBLIC_GUARD_FRAMES,
                                       (kept.photo.name, held.photo.name))
        dropped = set(self.samples) - set(training) - set(validation)
        self.assertEqual(sorted(s.photo.stem for s in dropped),
                         sorted(f"snap_usb_cam{c}_{n}" for c in (1, 2) for n in range(86, 91)))

    def test_another_set_leaves_this_sets_held_out_frames_alone(self):
        other = [_sample(f"snap_{n}", "other") for n in range(1, 50)]
        self.assertEqual(public_split(self.samples + other)[1][:len(public_split(self.samples)[1])],
                         public_split(self.samples)[1])

    def test_a_frame_without_a_number_is_refused(self):
        with self.assertRaisesRegex(DartsMlError, "frame number"):
            public_split([_sample("snap")])


class PublicMixingTest(unittest.TestCase):
    def test_each_source_is_drawn_its_weight_against_deepdarts(self):
        weights, draws = mixing(1000, 50, 0.5, 20, 0.3)
        self.assertEqual(len(weights), 1070)
        self.assertAlmostEqual(sum(weights[1050:]) / sum(weights), 0.3 / 1.8)
        self.assertAlmostEqual(sum(weights[1000:1050]) / sum(weights), 0.5 / 1.8)
        self.assertEqual(draws, 1800)
        weights, draws = mixing(1000, 0, 0.5, 20, 0.3)
        self.assertEqual((len(weights), draws), (1020, 1300))
        self.assertAlmostEqual(sum(weights[1000:]) / sum(weights), 0.3 / 1.3)


class PublicTrainingTest(unittest.TestCase):
    def setUp(self):
        from test_training_data import SIZE as DEEPDARTS_SIZE, TrainingDataTest

        self.td = TemporaryData()
        self.data = self.td.data
        holder = TrainingDataTest()
        holder.data, holder.to_image = self.data, camera(yaw_deg=10.0, pitch_deg=5.0, distance_mm=900.0,
                                                          focal_px=1200.0, size=DEEPDARTS_SIZE)
        lines = [TrainingDataTest._record(holder, n, s) for n, s in (("a", "train"), ("b", "train"), ("c", "val"))]
        (self.data.deepdarts() / DEEPDARTS_RECORDS).write_text("".join(json.dumps(r) + "\n" for r in lines))
        write_public_set(self.data, [f"snap_cam{c}_{n}" for c in (1, 2) for n in range(1, 13)])

    def tearDown(self):
        self.td.cleanup()

    def test_the_loader_draws_public_frames_their_weight(self):
        config = RunConfig("mix", size=64, batch=2, workers=0, public=(SET,), public_weight=1.0)
        deepdarts = deepdarts_samples(self.data, "train")
        public, _ = public_split(public_samples(self.data, (SET,)))
        self.assertEqual(len(public), 12)
        self.assertEqual(len(training_loader(deepdarts, [], config, public).sampler), 2 * len(deepdarts))
        self.assertEqual(len(training_loader(deepdarts, [], config).sampler), len(deepdarts))

    def test_a_run_reads_public_val_beside_deepdarts_val_records_the_licence_and_chooses_on_deepdarts(self):
        config = RunConfig("public", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0,
                           public=(SET,), public_weight=1.0)
        log = io.StringIO()
        folder = train(self.data, config, dt.date(2026, 11, 21), log)
        recorded = json.loads((folder / "config.json").read_text())
        self.assertEqual((recorded["training_public"], recorded["validation_public"]), (12, 2))
        self.assertEqual(recorded["validation"], "DeepDarts val")
        self.assertEqual(recorded["public"], [SET])
        provenance = recorded["public_sets"][SET]
        self.assertEqual((provenance["licence"], provenance["credit"]), (MANIFEST["licence"], MANIFEST["credit"]))
        self.assertEqual(provenance["mirror"], MANIFEST["mirror"])
        self.assertEqual(provenance["records"], 24)
        [epoch] = [json.loads(line) for line in (folder / "epochs.jsonl").read_text().splitlines()]
        self.assertEqual(epoch["public_figures"]["found"][1], 2)
        self.assertEqual(epoch["figures"]["found"][1], 1)
        self.assertIn("public val frames, never chosen on", log.getvalue())

    def test_a_set_without_its_licence_is_not_trained_on(self):
        (self.data.public_set(SET) / PUBLIC_MANIFEST).write_text(json.dumps({"set": SET}), encoding="utf-8")
        config = RunConfig("public", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0,
                           public=(SET,))
        with self.assertRaisesRegex(DartsMlError, "licence"):
            train(self.data, config, dt.date(2026, 11, 21), io.StringIO())
        self.assertFalse(self.data.runs().exists() and any(self.data.runs().iterdir()))

    def test_a_set_without_its_mirror_checksum_or_refusals_is_not_trained_on(self):
        config = RunConfig("public", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0,
                           public=(SET,))
        for broken, named in (({**MANIFEST, "mirror": {"url": "https://example.org/mirror"}}, "mirror.sha256"),
                              ({k: v for k, v in MANIFEST.items() if k != "refused"}, "refused")):
            (self.data.public_set(SET) / PUBLIC_MANIFEST).write_text(json.dumps(broken), encoding="utf-8")
            with self.subTest(named), self.assertRaisesRegex(DartsMlError, f"has no {named}"):
                train(self.data, config, dt.date(2026, 11, 21), io.StringIO())

    def test_public_weight_without_public_and_a_bad_name_are_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), mock.patch.dict(os.environ, {"DARTS_DATA": str(self.data.root)}):
            self.assertEqual(main(["train", "--name", "x", "--public-weight", "1"]), 2)
            with self.assertRaises(SystemExit):
                main(["train", "--name", "x", "--public", "Bad"])
            with self.assertRaises(SystemExit):
                main(["train", "--name", "x", "--public", f"{SET},{SET}"])


if __name__ == "__main__":
    unittest.main()
