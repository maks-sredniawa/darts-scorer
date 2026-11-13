import unittest

import numpy as np

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_BY_NAME, HAND_POINTS
from darts_ml.homography import project
from darts_ml.labelme import label, read_label
from darts_ml.manifest import ReviewManifest
from darts_ml.paths import Round
from darts_ml.prefill import SUGGESTED, prefill
from synthetic import TemporaryData, pass_one_window, session


class PrefillTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.truths = session(self.td, "s01", [["T20", "T20", "S1"], ["D3", "S19", "out"]])

    def tearDown(self):
        self.td.cleanup()

    def label(self, **kwargs):
        label(self.data, "s01", window=pass_one_window(self.truths, **kwargs), say=lambda _: None)

    def test_hand_points_become_every_visible_crossing(self):
        self.label()
        self.assertEqual(len(prefill(self.data, "s01")), 6)
        manifest = ReviewManifest.load(self.data.labels("s01"))
        for photo, (to_image, _) in self.truths.items():
            filled = read_label(self.data.labels("s01") / f"{photo}.json")
            self.assertEqual(len(filled.calibration), 80, photo)
            for name, xy in filled.calibration.items():
                expected = project(to_image, [CALIBRATION_BY_NAME[name].mm])[0]
                self.assertLess(np.linalg.norm(np.asarray(xy) - expected), 1e-6, (photo, name))
            self.assertEqual(set(manifest.get(photo).hand_points), set(HAND_POINTS))
            self.assertEqual(manifest.get(photo).label_seconds, 60.0)

    def test_an_entry_point_is_suggested_where_another_angle_saw_it(self):
        self.label(skip_entries={("s01-v01-p2", 2)})
        prefill(self.data, "s01")
        p2 = read_label(self.data.labels("s01") / "s01-v01-p2.json")
        suggested = [e for e in p2.entries if e.description == SUGGESTED]
        self.assertEqual(len(suggested), 1)
        to_image, in_board = self.truths["s01-v01-p2"]
        expected = project(to_image, [in_board[2]])[0]
        self.assertLess(np.linalg.norm(np.asarray(suggested[0].xy) - expected), 1e-6)
        for photo in ("s01-v01-p1", "s01-v01-p3", "s01-v02-p1"):
            entries = read_label(self.data.labels("s01") / f"{photo}.json").entries
            self.assertFalse([e for e in entries if e.description == SUGGESTED], photo)

    def test_running_twice_changes_nothing(self):
        self.label()
        prefill(self.data, "s01")
        before = {p: p.read_bytes() for p in self.data.labels("s01").glob("*.json")}
        self.assertEqual(prefill(self.data, "s01"), [])
        self.assertEqual(before, {p: p.read_bytes() for p in self.data.labels("s01").glob("*.json")})

    def test_refusals(self):
        with self.assertRaisesRegex(DartsMlError, "pass 1 is not finished"):
            prefill(self.data, "s01")
        with self.assertRaisesRegex(DartsMlError, "without pre-fill"):
            prefill(self.data, "s01", Round.C)


if __name__ == "__main__":
    unittest.main()
