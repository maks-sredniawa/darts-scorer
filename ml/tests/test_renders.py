import contextlib
import datetime as dt
import io
import json
import tempfile
import os
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, SEGMENTS, board_point
from darts_ml.cli import main
from darts_ml.deepdarts import RECORDS as DEEPDARTS_RECORDS
from darts_ml.homography import project
from darts_ml.renders import MANIFEST, RECORDS, Renderer, import_renders, renderer_mm
from darts_ml.train import RunConfig, mixing, train, training_loader
from darts_ml.training_data import RefusedRecord, Sample, deepdarts_samples, render_samples, render_split
from synthetic import TemporaryData, board_image, camera, dart_mm

SIZE = (480, 640)
OLD_RADII = {"double": 170.0, "outer": 170.0, "inner": 162.0, "triple": 99.0}


def keypoint_names() -> list[str]:
    names = ["center"]
    names += [f"double_{n}" for n in SEGMENTS]
    names += [f"triple_{n}" for n in SEGMENTS]
    pairs = [f"{n}_{SEGMENTS[(i + 1) % len(SEGMENTS)]}" for i, n in enumerate(SEGMENTS)]
    names += [f"double_outer_{p}" for p in pairs]
    names += [f"double_inner_{p}" for p in pairs]
    return names


def old_radii_mm(name: str) -> tuple[float, float]:
    """Where the renderer put a keypoint before its rings moved onto the wire centres."""
    x, y = renderer_mm(name)
    if name == "center":
        return x, y
    parts = name.split("_")
    radius = OLD_RADII[parts[1] if len(parts) == 4 else parts[0]]
    scale = radius / np.hypot(x, y)
    return x * scale, y * scale


def annotation(to_image, darts=(), size=SIZE, place=renderer_mm, nudge=None) -> dict:
    keypoints = []
    for name in keypoint_names():
        x, y = project(to_image, [place(name)])[0]
        if name == nudge:
            x += 3.0
        keypoints.append({"name": name, "x": round(float(x), 1), "y": round(float(y), 1)})
    placed = []
    for item in darts:
        if isinstance(item, tuple):
            x, y, zone = item
        else:
            (x, y), zone = project(to_image, [dart_mm(item)])[0], {"50": "DB", "25": "SB", "miss": "MISS"}.get(item, item)
        placed.append({"x": round(float(x), 1), "y": round(float(y), 1), "flight_x": 0.0, "flight_y": 0.0,
                       "flight_in_front": True, "score_zone": zone})
    return {"board_keypoints": keypoints, "darts": placed, "image_path": None,
            "camera_params": {"resolution": list(size)}}


class RenderOutput:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "annotations").mkdir(parents=True)
        (root / "rgb").mkdir()

    def frame(self, frame: str, to_image, darts=(), **kwargs) -> dict:
        made = annotation(to_image, darts, **kwargs)
        made["image_path"] = f"rgb/{frame}.jpg"
        board_image(to_image, size=SIZE).save(self.root / "rgb" / f"{frame}.jpg", "JPEG", quality=90)
        (self.root / "annotations" / f"{frame}.json").write_text(json.dumps(made), encoding="utf-8")
        return made


RENDERER = Renderer("8cc7fe14b33ceb465e14b8ada039d4ce683d16eb", "owner", {"width": "480"})


class KeypointTest(unittest.TestCase):
    def test_the_crossings_are_board_pys_and_the_segment_points_its_wire_centres(self):
        self.assertEqual(renderer_mm("double_outer_20_1"), CALIBRATION_BY_NAME["do-20-1"].mm)
        self.assertEqual(renderer_mm("double_inner_5_20"), CALIBRATION_BY_NAME["di-5-20"].mm)
        np.testing.assert_allclose(renderer_mm("double_20"), (0.0, 169.25), atol=1e-9)
        np.testing.assert_allclose(renderer_mm("triple_6"), (97.15, 0.0), atol=1e-9)
        np.testing.assert_allclose(renderer_mm("double_3"), board_point(169.25, 180.0), atol=1e-9)
        self.assertEqual(renderer_mm("center"), (0.0, 0.0))

    def test_a_name_the_renderer_never_writes_is_refused(self):
        for name in ("double_21", "double_outer_20_18", "bull", "triple_outer_20_1"):
            with self.subTest(name=name), self.assertRaisesRegex(DartsMlError, "keypoint"):
                renderer_mm(name)


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.scratch = tempfile.TemporaryDirectory()
        self.output = RenderOutput(Path(self.scratch.name) / "out")
        self.to_image = camera(yaw_deg=15.0, pitch_deg=10.0, distance_mm=1100.0, focal_px=1500.0, size=SIZE)

    def tearDown(self):
        self.td.cleanup()
        self.scratch.cleanup()

    def test_the_keypoints_become_the_80_crossings_and_darts_off_the_image_are_dropped(self):
        self.output.frame("000000", self.to_image, ["T20", "50", (-12.0, 30.0, "S11")])
        (self.output.root / "manifest.json").write_text(json.dumps({"seed": 7}), encoding="utf-8")
        imported = import_renders(self.data, self.output.root, "synth", RENDERER)
        self.assertEqual((imported.records, imported.darts, imported.off_image, imported.zones_differ), (1, 2, 1, 0))
        [record] = [json.loads(line) for line in (imported.folder / RECORDS).read_text().splitlines()]
        self.assertEqual(record["source"], "render")
        self.assertEqual([c["name"] for c in record["calibration"]], [p.name for p in CALIBRATION_POINTS])
        truth = project(self.to_image, [p.mm for p in CALIBRATION_POINTS])
        found = np.array([(c["x"], c["y"]) for c in record["calibration"]])
        self.assertLess(np.abs(found - truth).max(), 0.1)
        self.assertEqual(record["scores"], ["T20", "50"])
        self.assertEqual(len(record["entries"]), 2)
        self.assertTrue((self.data.root / record["photo"]).is_file())
        manifest = json.loads((imported.folder / MANIFEST).read_text())
        self.assertEqual(manifest["renderer"]["commit"], RENDERER.commit)
        self.assertEqual((manifest["renderer"]["look"], manifest["renderer"]["options"]), ("owner", {"width": "480"}))
        self.assertEqual(manifest["renderer"]["manifest"], {"seed": 7})
        self.assertEqual(manifest["darts_off_image"], 1)

    def test_a_frame_off_one_plane_or_on_the_old_radii_is_refused(self):
        self.output.frame("000000", self.to_image, ["S5"])
        self.output.frame("000001", self.to_image, ["S5"], nudge="triple_6")
        self.output.frame("000002", self.to_image, ["S5"], place=old_radii_mm)
        imported = import_renders(self.data, self.output.root, "synth", RENDERER)
        self.assertEqual(imported.records, 1)
        self.assertEqual([frame for frame, _ in imported.refused], ["000001", "000002"])
        self.assertTrue(all("fit one plane" in reason for _, reason in imported.refused))
        self.assertFalse((imported.folder / "rgb" / "000001.jpg").exists())

    def test_a_set_is_written_once_and_a_set_with_nothing_kept_not_at_all(self):
        self.output.frame("000000", self.to_image, ["S5"], place=old_radii_mm)
        with self.assertRaisesRegex(DartsMlError, "every one"):
            import_renders(self.data, self.output.root, "synth", RENDERER)
        self.assertEqual(list(self.data.renders().iterdir()), [])
        self.output.frame("000000", self.to_image, ["S5"])
        import_renders(self.data, self.output.root, "synth", RENDERER)
        with self.assertRaisesRegex(DartsMlError, "never overwritten"):
            import_renders(self.data, self.output.root, "synth", RENDERER)

    def test_an_image_path_leaving_the_folder_is_refused(self):
        made = self.output.frame("000000", self.to_image, ["S5"])
        made["image_path"] = "../elsewhere.jpg"
        (self.output.root / "annotations" / "000000.json").write_text(json.dumps(made))
        self.output.frame("000001", self.to_image, ["S5"])
        imported = import_renders(self.data, self.output.root, "synth", RENDERER)
        self.assertEqual([frame for frame, _ in imported.refused], ["000000"])

    def test_the_step_needs_a_look_and_a_renderer_and_a_plain_set_name(self):
        for argv in (["renders", "import", "x", "--set", "a", "--renderer-commit", "c"],
                     ["renders", "import", "x", "--set", "a", "--look", "owner"],
                     ["renders", "import", "x", "--set", "../a", "--look", "owner", "--renderer-commit", "c"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(argv)


def _sample(session: str, frame: int) -> Sample:
    return Sample(Path(f"/renders/{session}/rgb/{frame:06d}.jpg"), (), (), f"render-{session}")


class MixingTest(unittest.TestCase):
    def test_the_split_is_whole_frames_fixed_by_the_seed_and_blind_to_other_sets(self):
        first = [_sample("a", i) for i in range(400)]
        second = [_sample("b", i) for i in range(400)]
        training, validation = render_split(first, seed=0)
        self.assertEqual(sorted(training + validation, key=lambda s: s.photo), first)
        self.assertFalse(set(training) & set(validation))
        self.assertTrue(20 <= len(validation) <= 60, len(validation))
        self.assertEqual(render_split(first, seed=0), (training, validation))
        self.assertNotEqual(render_split(first, seed=1)[1], validation)
        both = render_split(first + second, seed=0)[1]
        self.assertEqual([s for s in both if s.capture_session == "render-a"], validation)

    def test_renders_are_drawn_their_weight_against_deepdarts_whatever_the_counts(self):
        weights, draws = mixing(1000, 50, 0.5)
        self.assertEqual(len(weights), 1050)
        self.assertAlmostEqual(sum(weights[1000:]) / sum(weights), 0.5 / 1.5)
        self.assertEqual(draws, 1500)


class RenderTrainingTest(unittest.TestCase):
    def setUp(self):
        from test_training_data import SIZE as DEEPDARTS_SIZE, TrainingDataTest

        self.td = TemporaryData()
        self.data = self.td.data
        holder = TrainingDataTest()
        holder.data, holder.to_image = self.data, camera(yaw_deg=10.0, pitch_deg=5.0, distance_mm=900.0,
                                                          focal_px=1200.0, size=DEEPDARTS_SIZE)
        lines = [TrainingDataTest._record(holder, n, s) for n, s in (("a", "train"), ("b", "train"), ("c", "val"))]
        (self.data.deepdarts() / DEEPDARTS_RECORDS).write_text("".join(json.dumps(r) + "\n" for r in lines))
        self.scratch = tempfile.TemporaryDirectory()
        output = RenderOutput(Path(self.scratch.name) / "out")
        for frame in range(12):
            to_image = camera(yaw_deg=frame - 6.0, pitch_deg=8.0, distance_mm=1100.0, focal_px=1500.0, size=SIZE)
            output.frame(f"{frame:06d}", to_image, ["T20", "S5"])
        import_renders(self.data, output.root, "synth", RENDERER)

    def tearDown(self):
        self.td.cleanup()
        self.scratch.cleanup()

    def test_records_are_read_as_samples_and_a_stray_source_is_refused(self):
        samples = render_samples(self.data, ("synth",))
        self.assertEqual(len(samples), 12)
        self.assertTrue(all(len(s.calibration) == 80 and len(s.entries) == 2 for s in samples))
        with self.assertRaisesRegex(DartsMlError, "renders import"):
            render_samples(self.data, ("missing",))
        path = self.data.render_set("synth") / RECORDS
        record = json.loads(path.read_text().splitlines()[0])
        path.write_text(json.dumps({**record, "source": "owner"}) + "\n")
        with self.assertRaises(RefusedRecord):
            render_samples(self.data, ("synth",))

    def test_the_loader_draws_from_both_and_an_epoch_is_deepdarts_plus_its_weight(self):
        config = RunConfig("mix", size=64, batch=2, workers=0, renders=("synth",), render_weight=1.0)
        deepdarts = deepdarts_samples(self.data, "train")
        renders = render_samples(self.data, ("synth",))
        loader = training_loader(deepdarts, renders, config)
        self.assertEqual(len(loader.sampler), 2 * len(deepdarts))
        self.assertEqual(len(training_loader(deepdarts, [], config).sampler), len(deepdarts))

    def test_a_run_reads_rendered_val_beside_deepdarts_val_and_chooses_on_deepdarts(self):
        seed = next(s for s in range(100) if len(render_split(render_samples(self.data, ("synth",)), s)[1]) >= 1)
        config = RunConfig("mix", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0, seed=seed,
                           renders=("synth",), render_weight=1.0)
        log = io.StringIO()
        folder = train(self.data, config, dt.date(2026, 11, 21), log)
        recorded = json.loads((folder / "config.json").read_text())
        training, validation = render_split(render_samples(self.data, ("synth",)), seed)
        self.assertEqual((recorded["training_renders"], recorded["validation_renders"]), (len(training), len(validation)))
        self.assertEqual(recorded["validation"], "DeepDarts val")
        self.assertEqual(recorded["render_sets"]["synth"]["renderer"]["commit"], RENDERER.commit)
        self.assertEqual(recorded["renders"], ["synth"])
        [epoch] = [json.loads(line) for line in (folder / "epochs.jsonl").read_text().splitlines()]
        self.assertEqual(epoch["render_figures"]["found"][1], len(validation))
        self.assertEqual(epoch["figures"]["found"][1], 1)
        self.assertIn("never chosen on", log.getvalue())

    def test_render_weight_without_renders_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), mock.patch.dict(os.environ, {"DARTS_DATA": str(self.data.root)}):
            self.assertEqual(main(["train", "--name", "x", "--render-weight", "1"]), 2)
            with self.assertRaises(SystemExit):
                main(["train", "--name", "x", "--renders", "Bad"])


if __name__ == "__main__":
    unittest.main()
