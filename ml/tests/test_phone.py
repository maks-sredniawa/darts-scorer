import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_POINTS, SEGMENTS, score
from darts_ml.evaluate import PredictedEntry
from darts_ml.homography import project
from darts_ml.locate import Located
from darts_ml.model import ENTRY_POINT, Heads
from darts_ml.phone import (DEVICE_DIR, EXPECTED, FIXTURES, PHOTOS_LONG_EDGE, REPORT, as_stored, as_stored_samples,
                            device_name, expected_record, heads_case, heads_from_record, picked, rng_choices,
                            run_parity, same_model, scoring_table, warp_cases, write_fixtures)
from darts_ml.training_data import Sample, targets
from synthetic import camera

SIZE = 512


def logits_of(points) -> Heads:
    made = targets(points, SIZE)

    def logit(heat):
        clipped = np.clip(heat, 1e-6, 1 - 1e-6)
        return np.log(clipped / (1 - clipped)).astype(np.float32)

    return Heads(np.concatenate([logit(made.board_heat), made.board_offsets]).astype(np.float32),
                 np.concatenate([logit(made.entry_heat[None]), made.entry_offsets]).astype(np.float32))


class ScoringTableTest(unittest.TestCase):
    def test_every_bed_both_bulls_and_a_miss(self):
        tokens = {t for _, _, t in scoring_table()}
        beds = {f"{ring}{n}" for ring in "SDT" for n in SEGMENTS}
        self.assertLessEqual(beds | {"25", "50", "miss"}, tokens)

    def test_each_row_is_pythons_score(self):
        for x, y, token in scoring_table():
            self.assertEqual(score(x, y).token, token)

    def test_both_sides_of_a_wire_differ(self):
        rows = scoring_table()
        pairs = sum(1 for a, b in zip(rows, rows[1:]) if np.hypot(a[0] - b[0], a[1] - b[1]) < 0.21 and a[2] != b[2])
        self.assertGreater(pairs, 200)


class FixturesTest(unittest.TestCase):
    def test_rng_draws_are_numpys_from_seed_zero(self):
        draws = rng_choices()
        rng = np.random.default_rng(0)
        for population, picked_ in draws:
            self.assertEqual(picked_, [int(i) for i in rng.choice(population, 4, replace=False)])

    def test_warp_cases_cover_reducing_and_enlarging(self):
        cases = warp_cases()
        self.assertEqual(len(cases["pixels"]), cases["width"] * cases["height"])
        for case in cases["cases"]:
            self.assertEqual(len(case["expected"]), case["size"] ** 2 * 3)

    def test_sparse_heads_decode_and_locate_as_the_full_ones(self):
        to_image = camera(size=(SIZE, SIZE))
        board = project(to_image, [p.mm for p in CALIBRATION_POINTS])
        darts = project(to_image, [(0.0, 102.0), (30.0, 140.0)])
        heads = logits_of([(c, x, y, 1.0) for c, (x, y) in enumerate(board)] +
                          [(ENTRY_POINT, x, y, 1.0) for x, y in darts])
        case = heads_case("synthetic", np.eye(3), heads)
        self.assertTrue(case["located"]["found"])
        self.assertEqual(sorted(d[3] for d in case["located"]["darts"]), ["S1", "T20"])
        self.assertEqual(len(case["calibration"]), 80)
        self.assertLess(len(case["board"]["cells"]), heads.board.size // 50)

    def test_write_fixtures_writes_the_table_draws_warp_and_heads(self):
        with tempfile.TemporaryDirectory() as folder:
            written = write_fixtures(Path(folder), [{"name": "x", "board": {}}])
            self.assertEqual([p.name for p in written], ["scores.tsv", "rng.json", "warp.json", "heads-x.json"])
            header = written[0].read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(header, "x_mm\ty_mm\tscore")


class CommittedFixturesTest(unittest.TestCase):
    """The Kotlin tests read these files; a change to board.py, decode.py, homography.py or augment.py that is not
    carried into them by `darts-ml phone-fixtures` fails here instead of leaving the port held to stale answers."""

    def test_table_draws_and_warp_are_what_phone_fixtures_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            for written in write_fixtures(Path(folder)):
                with self.subTest(written.name):
                    self.assertEqual(written.read_bytes(), (FIXTURES / written.name).read_bytes())

    def test_each_heads_fixture_still_decodes_and_locates_as_recorded(self):
        committed = sorted(FIXTURES.glob("heads-*.json"))
        self.assertEqual(len(committed), 3)
        for path in committed:
            with self.subTest(path.name):
                stored = json.loads(path.read_text(encoding="utf-8"))
                matrix, heads = heads_from_record(stored)
                again = json.loads(json.dumps(heads_case(stored["name"], matrix, heads)))
                self.assert_same_record(again, stored)

    def assert_same_record(self, actual, expected, where="record"):
        # OpenBLAS picks its kernels by CPU, so a refit's small perspective terms move by up to ~1e-11 between
        # runners. Floats get DecodingTest.kt's 1e-9 bound; everything discrete must match exactly.
        if isinstance(expected, float) or isinstance(actual, float):
            self.assertTrue(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), f"{where}: {actual} != {expected}")
        elif isinstance(expected, dict):
            self.assertEqual(sorted(actual), sorted(expected), where)
            for key in expected:
                self.assert_same_record(actual[key], expected[key], f"{where}.{key}")
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), where)
            for index, (a, e) in enumerate(zip(actual, expected, strict=True)):
                self.assert_same_record(a, e, f"{where}[{index}]")
        else:
            self.assertEqual(actual, expected, where)


class AsStoredTest(unittest.TestCase):
    def test_a_large_photo_is_capped_on_its_long_edge_without_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder, "in.jpg"), Path(folder, "out.jpg")
            exif = Image.Exif()
            exif[0x010F] = "camera"
            Image.new("RGB", (5000, 2500), (120, 80, 40)).save(source, exif=exif)
            sx, sy = as_stored(source, target)
            with Image.open(target) as written:
                self.assertEqual(written.size, (PHOTOS_LONG_EDGE, PHOTOS_LONG_EDGE // 2))
                self.assertEqual(len(written.getexif()), 0)
            self.assertAlmostEqual(sx, PHOTOS_LONG_EDGE / 5000)
            self.assertAlmostEqual(sy, (PHOTOS_LONG_EDGE // 2) / 2500)

    def test_a_small_photo_keeps_its_size(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder, "in.jpg"), Path(folder, "out.jpg")
            Image.new("RGB", (800, 800), (10, 200, 30)).save(source)
            self.assertEqual(as_stored(source, target), (1.0, 1.0))
            with Image.open(target) as written:
                self.assertEqual(written.size, (800, 800))

    def test_a_rotated_photo_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, "in.jpg")
            exif = Image.Exif()
            exif[0x0112] = 6
            Image.new("RGB", (40, 20)).save(source, exif=exif)
            with self.assertRaises(DartsMlError):
                as_stored(source, Path(folder, "out.jpg"))

    def test_labels_scale_with_the_photo(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, "in.jpg")
            Image.new("RGB", (4096, 3072)).save(source)
            sample = Sample(source, ((0, 100.0, 200.0, 1.0),), ((400.0, 40.0),), "d1_x")
            [stored] = as_stored_samples([sample], Path(folder, "stored"))
            self.assertEqual(stored.calibration, ((0, 50.0, 100.0, 1.0),))
            self.assertEqual(stored.entries, ((200.0, 20.0),))
            self.assertEqual(stored.capture_session, "d1_x")
            self.assertTrue(stored.photo.exists())


class ParityTest(unittest.TestCase):
    def test_picked_is_spread_and_repeatable(self):
        samples = list(range(1070))
        chosen = picked(samples, 150)
        self.assertEqual(chosen, picked(samples, 150))
        self.assertEqual(len(set(chosen)), 150)
        self.assertEqual(chosen[0], 0)
        self.assertGreater(chosen[-1], 1060)
        with self.assertRaises(DartsMlError):
            picked(samples, 0)
        with self.assertRaises(DartsMlError):
            picked(samples, 1071)

    def test_device_name_is_unique_across_capture_sessions(self):
        a = SimpleNamespace(capture_session="d1_02_06_2020", photo=Path("x/IMG_1.JPG"))
        b = SimpleNamespace(capture_session="d2_02_03_2021", photo=Path("y/IMG_1.JPG"))
        self.assertNotEqual(device_name(a), device_name(b))
        self.assertTrue(device_name(a).endswith(".jpg"))

    def test_expected_crossings_map_back_onto_the_board(self):
        to_board = np.linalg.inv(camera(size=(800, 800)))
        record = expected_record("p.jpg", Located(to_board, {}, (PredictedEntry(400.0, 300.0, False, 0.9),)))
        back = project(to_board, record["crossings_px"])
        np.testing.assert_allclose(back, [p.mm for p in CALIBRATION_POINTS], atol=1e-9)
        self.assertEqual(len(record["darts"]), 1)
        nothing = expected_record("q.jpg", Located(None))
        self.assertEqual((nothing["found"], nothing["crossings_px"], nothing["darts"]), (False, [], []))

    def test_same_model_refuses_a_different_file(self):
        with tempfile.TemporaryDirectory() as folder:
            run, app = Path(folder, "best.tflite"), Path(folder, "darts.tflite")
            run.write_bytes(b"one")
            app.write_bytes(b"two")
            with self.assertRaises(DartsMlError):
                same_model(run, app)
            app.write_bytes(b"one")
            same_model(run, app)

    def test_run_parity_drives_the_phone_and_returns_its_report(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            photos = []
            for name in ("b.jpg", "a.jpg"):
                photos.append((name, root / f"in-{name}"))
                photos[-1][1].write_bytes(b"jpeg")
            device = FakePhone()
            located = []
            report = run_parity(device, photos, root / "out", "run", lambda paths: located.extend(paths) or
                                [Located(None) for _ in paths], lambda _: None)
            self.assertTrue(report.startswith("PASS"))
            self.assertEqual([p.name for p in located], ["a.jpg", "b.jpg"])
            expected = json.loads((root / "out" / EXPECTED).read_text(encoding="utf-8"))
            self.assertEqual([p["name"] for p in expected["photos"]], ["a.jpg", "b.jpg"])
            self.assertEqual(device.methods, ["writesEachPhotoThroughMediaFiles", "matchesPythonOnEachPhoto"])

    def test_run_parity_stops_when_the_phone_wrote_fewer(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "in.jpg").write_bytes(b"jpeg")
            with self.assertRaises(DartsMlError):
                run_parity(FakePhone(write=False), [("a.jpg", root / "in.jpg")], root / "out", "run",
                           lambda paths: [], lambda _: None)


class FakePhone:
    def __init__(self, write: bool = True) -> None:
        self.write = write
        self.pushed: list[str] = []
        self.methods: list[str] = []

    def shell(self, command: str) -> str:
        if command.startswith("am instrument"):
            self.methods.append(command.split("#")[1].split()[0])
            return "OK (1 test)"
        return ""

    def push(self, source: Path, target: str) -> None:
        self.pushed.append(target)

    def adb(self, *args: str) -> str:
        if args[0] == "push":
            self.pushed += [Path(a).name for a in args[1:-1]]
        if args[0] == "pull" and args[1].endswith("/written"):
            folder = Path(args[2]) / "written"
            folder.mkdir(parents=True, exist_ok=True)
            for name in self.pushed if self.write else []:
                if name.endswith(".jpg"):
                    (folder / name).write_bytes(b"written")
        if args[0] == "pull" and args[1] == f"{DEVICE_DIR}/{REPORT}":
            Path(args[2]).write_text("PASS: 2 Photos\n", encoding="utf-8")
        return ""


if __name__ == "__main__":
    unittest.main()
