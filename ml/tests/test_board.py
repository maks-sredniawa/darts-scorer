import tomllib
import unittest
from pathlib import Path

from darts_ml.board import CALIBRATION_BY_NAME, CALIBRATION_POINTS, HAND_POINTS, Ring, Score, score

CASES = Path(__file__).with_name("scoring-cases.toml")
CLOCKWISE_FROM_20 = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
RADII = {"do": 169.25, "di": 159.75, "to": 106.65, "ti": 97.15}


class BoardTest(unittest.TestCase):
    def test_eighty_crossings_with_unique_names(self):
        self.assertEqual(len(CALIBRATION_POINTS), 80)
        self.assertEqual(len(CALIBRATION_BY_NAME), 80)

    def test_names_run_clockwise_from_20_on_each_ring_wire(self):
        for ring in RADII:
            names = [p.name for p in CALIBRATION_POINTS if p.wire.name == ring]
            expected = [f"{ring}-{a}-{b}" for a, b in zip(CLOCKWISE_FROM_20, CLOCKWISE_FROM_20[1:] + CLOCKWISE_FROM_20[:1], strict=True)]
            self.assertEqual(names, expected)

    def test_radii_are_the_wire_centres(self):
        for point in CALIBRATION_POINTS:
            x, y = point.mm
            self.assertAlmostEqual((x * x + y * y) ** 0.5, RADII[point.wire.name], places=9)

    def test_crossings_sit_on_segment_boundaries(self):
        self.assertAlmostEqual(CALIBRATION_BY_NAME["do-20-1"].degrees, 9.0)
        self.assertAlmostEqual(CALIBRATION_BY_NAME["ti-5-20"].degrees, 351.0)
        x, y = CALIBRATION_BY_NAME["do-20-1"].mm
        self.assertGreater(x, 0)
        self.assertGreater(y, 0)

    def test_hand_points_are_deep_darts_four(self):
        self.assertEqual(HAND_POINTS, ("do-5-20", "do-17-3", "do-8-11", "do-13-6"))
        degrees = [CALIBRATION_BY_NAME[n].degrees for n in HAND_POINTS]
        self.assertEqual(degrees, [351.0, 171.0, 261.0, 81.0])

    def test_shared_scoring_cases(self):
        cases = tomllib.loads(CASES.read_text(encoding="utf-8"))["case"]
        self.assertGreater(len(cases), 80)
        for case in cases:
            with self.subTest(case["why"], x=case["x"], y=case["y"]):
                self.assertEqual(score(case["x"], case["y"]).token, case["score"])

    def test_score_tokens_round_trip_and_value(self):
        for token, value in (("T20", 60), ("D16", 32), ("S5", 5), ("25", 25), ("50", 50), ("miss", 0)):
            parsed = Score.parse(token)
            self.assertEqual(parsed.token, token)
            self.assertEqual(parsed.value, value)
        self.assertEqual(Score.parse("D20").ring, Ring.DOUBLE)
        for bad in ("T21", "X5", "S", "20", "t20"):
            with self.assertRaises(ValueError):
                Score.parse(bad)


if __name__ == "__main__":
    unittest.main()
