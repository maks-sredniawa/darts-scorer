import io
import pickle
import unittest

import numpy as np
import pandas as pd

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, board_point
from darts_ml.deepdarts import (IMAGES, LABELS, ORDER, PROJECTED, RADIUS_MM, SOURCE, RefusedClass, convert,
                                load_labels, overlay_sample, read_records)
from darts_ml.heldout import file_sha256
from darts_ml.homography import project
from synthetic import TemporaryData, board_image, camera, dart_mm

SIZE = (800, 800)
RAN = []


def _mark():
    RAN.append("ran")


class _Calls:
    def __init__(self, function, *arguments):
        self.reduced = (function, arguments)

    def __reduce__(self):
        return self.reduced


def _frame(rows) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["img_folder", "img_name", "bbox", "xy"], dtype=object)
    frame.columns = pd.Index(list(frame.columns), dtype=object)
    return frame


class RestrictedUnpicklerTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.path = self.td.data.root / "labels.pkl"
        RAN.clear()

    def tearDown(self):
        self.td.cleanup()

    def test_loads_a_dataframe_built_in_the_test(self):
        frame = _frame([["d1_02_04_2020", "IMG_1.JPG", [1, 2, 3, 4], [[0.4, 0.1], [0.6, 0.9], [0.1, 0.6], [0.9, 0.4]]]])
        self.path.write_bytes(pickle.dumps(frame, protocol=4))
        loaded = load_labels(self.path)
        self.assertEqual(loaded.to_dict("records"), frame.to_dict("records"))

    def test_refuses_any_other_class_before_running_it(self):
        self.path.write_bytes(pickle.dumps(_Calls(_mark)))
        with self.assertRaisesRegex(RefusedClass, "_mark"):
            load_labels(self.path)
        self.assertEqual(RAN, [])

    def test_refuses_a_pandas_function_off_the_list(self):
        self.path.write_bytes(pickle.dumps(_Calls(pd.eval, "1 + 1")))
        with self.assertRaises(RefusedClass):
            load_labels(self.path)

    def test_refuses_a_table_without_deepdarts_columns(self):
        self.path.write_bytes(pickle.dumps(pd.DataFrame({"a": [1]}, dtype=object).set_axis(pd.Index(["a"], dtype=object), axis=1)))
        with self.assertRaisesRegex(DartsMlError, "img_folder"):
            load_labels(self.path)


class ConvertTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.root = self.data.deepdarts()
        self.to_image = camera(yaw_deg=25.0, pitch_deg=12.0, distance_mm=900.0, focal_px=1200.0, size=SIZE)
        self.darts_mm = [dart_mm("T20"), dart_mm("S5")]

    def tearDown(self):
        self.td.cleanup()

    def _xy(self) -> list[list[float]]:
        four = [board_point(RADIUS_MM, CALIBRATION_BY_NAME[n].degrees) for n in ORDER]
        pixels = project(self.to_image, four + self.darts_mm)
        return [[x / SIZE[0], y / SIZE[1]] for x, y in pixels]

    def _photo(self, folder: str, name: str) -> None:
        path = self.root / IMAGES / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        board_image(self.to_image, self.darts_mm, size=SIZE).save(path, "JPEG", quality=90)

    def _labels(self, rows) -> None:
        path = self.root / LABELS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(_frame(rows), protocol=4))

    def test_converts_the_four_points_and_projects_the_other_76(self):
        self._photo("d1_02_04_2020", "IMG_1.JPG")
        self._labels([["d1_02_04_2020", "IMG_1.JPG", [10, 20, 30, 40], self._xy()]])
        converted = convert(self.data)
        self.assertEqual((converted.records, converted.skipped), (1, []))
        [record] = read_records(self.data)
        self.assertEqual(record["source"], SOURCE)
        self.assertEqual(record["split"], "train")
        self.assertEqual(record["photo"], "deepdarts/cropped_images/800/d1_02_04_2020/IMG_1.JPG")
        self.assertEqual(record["photo_sha256"], file_sha256(self.data.root / record["photo"]))
        self.assertEqual((record["width"], record["height"], record["crop"]), (800, 800, [10, 20, 30, 40]))
        calibration = {c["name"]: c for c in record["calibration"]}
        self.assertEqual(list(calibration), [p.name for p in CALIBRATION_POINTS])
        given = dict(zip(ORDER, self._xy(), strict=False))
        for point in CALIBRATION_POINTS:
            c = calibration[point.name]
            if point.name in ORDER:
                self.assertEqual(c["source"], SOURCE)
                np.testing.assert_allclose([c["x"], c["y"]], np.multiply(given[point.name], SIZE))
            else:
                self.assertEqual(c["source"], PROJECTED)
                np.testing.assert_allclose([c["x"], c["y"]], project(self.to_image, [point.mm])[0], atol=1e-6)
        entries = [[e["x"], e["y"]] for e in record["entries"]]
        np.testing.assert_allclose(entries, project(self.to_image, self.darts_mm), atol=1e-6)
        self.assertFalse(any(e["inferred"] for e in record["entries"]))

    def test_marks_deepdarts_own_test_and_val_folders(self):
        for folder in ("d1_03_03_2020", "d2_02_05_2021"):
            self._photo(folder, "IMG_1.JPG")
        self._labels([[folder, "IMG_1.JPG", [0, 0, 0, 0], self._xy()] for folder in ("d1_03_03_2020", "d2_02_05_2021")])
        convert(self.data)
        self.assertEqual([r["split"] for r in read_records(self.data)], ["test", "val"])

    def test_skips_a_row_it_cannot_trust_and_says_why(self):
        self._photo("d1_02_04_2020", "IMG_1.JPG")
        broken = self._xy()
        broken[2][0] = float("nan")
        corrupt = self.root / IMAGES / "d1_02_04_2020" / "IMG_3.JPG"
        corrupt.write_bytes(b"not a jpeg")
        self._labels([
            ["d1_02_04_2020", "IMG_1.JPG", [0, float("nan"), 0, 0], self._xy()],
            ["d1_02_04_2020", "IMG_3.JPG", [0, 0, 0, 0], self._xy()],
            ["d1_02_04_2020", "../IMG_1.JPG", [0, 0, 0, 0], self._xy()],
            ["d1_02_04_2020", "IMG_2.JPG", [0, 0, 0, 0], self._xy()],
            ["d1_02_04_2020", "IMG_1.JPG", [0, 0, 0, 0], broken],
            ["d1_02_04_2020", "IMG_1.JPG", [0, 0, 0, 0], self._xy()[:3]],
            ["d1_02_04_2020", "IMG_1.JPG", [0, 0, 0, 0], self._xy()],
        ])
        converted = convert(self.data)
        self.assertEqual(converted.records, 1)
        reasons = [reason for _, reason in converted.skipped]
        self.assertEqual(len(reasons), 6)
        self.assertIn("bbox", reasons[0])
        self.assertIn("cannot be read", reasons[1])
        self.assertIn("not a plain name", reasons[2])
        self.assertEqual(reasons[3], "no Photo")
        self.assertIn("finite", reasons[4])
        self.assertIn("3 points", reasons[5])

    def test_overlay_draws_a_sample_from_the_records(self):
        self._photo("d1_02_04_2020", "IMG_1.JPG")
        self._labels([["d1_02_04_2020", "IMG_1.JPG", [0, 0, 0, 0], self._xy()]])
        convert(self.data)
        self.assertEqual(overlay_sample(self.data, 10), ["d1_02_04_2020-IMG_1.jpg"])
        self.assertTrue((self.data.deepdarts_overlays() / "d1_02_04_2020-IMG_1.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
