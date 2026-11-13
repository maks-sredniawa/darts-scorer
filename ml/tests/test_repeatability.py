import datetime as dt
import unittest

import numpy as np

from darts_ml.board import CALIBRATION_POINTS, HAND_POINTS
from darts_ml.homography import project
from darts_ml.labelme import Shape
from darts_ml.manifest import Review, ReviewManifest
from darts_ml.paths import Round
from darts_ml.repeatability import repeatability
from darts_ml.review import label_sha256
from synthetic import SIZE, TemporaryData, session

DAY = dt.date(2026, 11, 14)


class RepeatabilityTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.truths = session(self.td, "s01", [["T20", "T20", "S1"], ["S5", "S5", "S5"]])

    def tearDown(self):
        self.td.cleanup()

    def write_round(self, round_, offset_mm=(0.0, 0.0), dragged=(), hand=True, photos=None):
        labels = self.data.labels("s01", round_)
        manifest = ReviewManifest.load(labels)
        for photo, (to_image, _) in self.truths.items():
            if photos is not None and photo not in photos:
                continue
            shapes = []
            for point in CALIBRATION_POINTS:
                x, y = project(to_image, [np.add(point.mm, offset_mm)])[0]
                if point.name in dragged:
                    x += 2.0
                if 0 <= x < SIZE[0] and 0 <= y < SIZE[1]:
                    shapes.append(Shape(point.name, float(x), float(y)))
            path = self.td.write_label("s01", photo, shapes, labels)
            record = manifest.record(photo)
            record.label_seconds, record.review_seconds = 90.0, 30.0
            if hand:
                record.hand_points = {s.label: s.xy for s in shapes if s.label in HAND_POINTS}
            record.reviews = [Review(DAY, label_sha256(path))]
        manifest.save()

    def test_identical_rounds_read_zero_and_verdict_1(self):
        self.write_round(Round.A)
        self.write_round(Round.B)
        self.write_round(Round.C, hand=False, photos={"s01-v01-p1", "s01-v02-p3"})
        reading = repeatability(self.data, "s01")
        self.assertLess(reading.spreads["a–b, all crossings"].median_mm, 1e-6)
        self.assertEqual(reading.spreads["a–b, all crossings"].count, 6 * 80)
        self.assertEqual(reading.spreads["a–c, all crossings"].count, 2 * 80)
        self.assertEqual(reading.verdict, 1)
        self.assertAlmostEqual(reading.minutes[Round.A].pass_1, 1.5)
        self.assertAlmostEqual(reading.minutes[Round.A].pass_3, 0.5)

    def test_a_known_shift_reads_its_millimetres_and_verdict_2(self):
        self.write_round(Round.A)
        self.write_round(Round.B, offset_mm=(0.24, 0.32))
        self.write_round(Round.C, hand=False)
        reading = repeatability(self.data, "s01")
        ab = reading.spreads["a–b, all crossings"]
        self.assertAlmostEqual(ab.median_mm, 0.4, places=6)
        self.assertAlmostEqual(ab.p95_mm, 0.4, places=6)
        self.assertEqual(reading.verdict, 2)

    def test_the_worse_of_a_b_and_a_c_decides_and_verdict_3(self):
        self.write_round(Round.A)
        self.write_round(Round.B)
        self.write_round(Round.C, offset_mm=(0.0, 0.8), hand=False)
        self.assertEqual(repeatability(self.data, "s01").verdict, 3)

    def test_without_round_c_there_is_no_verdict(self):
        self.write_round(Round.A)
        self.write_round(Round.B)
        self.assertIsNone(repeatability(self.data, "s01").verdict)

    def test_dragged_and_undragged_crossings_are_split(self):
        moved = {"ti-20-1", "to-3-19"}
        self.write_round(Round.A, dragged=moved)
        self.write_round(Round.B, dragged=moved | {"di-6-10"})
        reading = repeatability(self.data, "s01")
        dragged = reading.spreads["a–b, dragged in both"]
        undragged = reading.spreads["a–b, undragged in either"]
        self.assertEqual(dragged.count + undragged.count, 6 * 80)
        self.assertEqual(dragged.count, 6 * (len(moved) + len(HAND_POINTS)))

    def test_unreviewed_labels_are_left_out(self):
        self.write_round(Round.A)
        self.write_round(Round.B)
        path = self.data.labels("s01", Round.B) / "s01-v01-p1.json"
        path.write_text(path.read_text().replace('"flags": {}', '"flags": {"x": false}', 1))
        reading = repeatability(self.data, "s01")
        self.assertEqual(reading.spreads["a–b, all crossings"].count, 5 * 80)
        self.assertIn("s01-v01-p1 (round b, not reviewed)", reading.skipped)


if __name__ == "__main__":
    unittest.main()
