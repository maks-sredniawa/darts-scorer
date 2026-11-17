import dataclasses
import unittest
from pathlib import Path

import numpy as np

from darts_ml.board import CALIBRATION_POINTS
from darts_ml.evaluate import Share
from darts_ml.homography import project
from darts_ml.locate import figures, located_from_targets
from darts_ml.training_data import Sample
from synthetic import camera, dart_mm

SIZE = 512
APART_DARTS = (dart_mm("T20"), dart_mm("S5"), dart_mm("D3"))
CLOSE_DARTS = (dart_mm("T20"), dart_mm("T20", nudge_deg=3.5), dart_mm("S11"))


def sample_of(darts_mm, session="s01_day") -> Sample:
    to_photo = camera(yaw_deg=25.0, pitch_deg=10.0)
    pixels = project(to_photo, [p.mm for p in CALIBRATION_POINTS])
    return Sample(
        Path("unread.jpg"),
        tuple((c, float(x), float(y), 1.0) for c, (x, y) in enumerate(pixels)),
        tuple(map(tuple, project(to_photo, list(darts_mm)))),
        session,
    )


class LocateTest(unittest.TestCase):
    def test_targets_decode_back_to_the_photo_pixels_they_came_from(self):
        sample = sample_of(APART_DARTS)
        located = located_from_targets(sample, SIZE)
        self.assertTrue(located.found)
        self.assertEqual(set(located.calibration), {p.name for p in CALIBRATION_POINTS})
        for channel, x, y, _ in sample.calibration:
            np.testing.assert_allclose(located.calibration[CALIBRATION_POINTS[channel].name], (x, y), atol=0.05)
        guessed = sorted((e.x, e.y) for e in located.entries)
        np.testing.assert_allclose(guessed, sorted(sample.entries), atol=0.05)

    def test_targets_read_perfect_on_every_figure(self):
        sample = sample_of(APART_DARTS)
        reading = figures([sample], [located_from_targets(sample, SIZE)])
        self.assertEqual(reading.found, Share(1, 1))
        self.assertEqual(reading.exact, Share(1, 1))
        self.assertEqual(reading.darts_right, Share(3, 3))
        self.assertEqual(reading.grouped, Share(0, 0))
        self.assertEqual(reading.exact_by_folder, {"s01": Share(1, 1)})
        self.assertLess(reading.treble.median_mm, 0.05)
        self.assertLess(reading.double.p95_mm, 0.05)

    def test_a_close_pair_counts_as_grouped_only_when_both_darts_are_matched(self):
        sample = sample_of(CLOSE_DARTS)
        located = located_from_targets(sample, SIZE)
        self.assertEqual(len(located.entries), 3)
        both = figures([sample], [located])
        self.assertEqual(both.grouped, Share(1, 1))
        self.assertEqual(both.exact, Share(1, 1))

        merged = [e for e in located.entries
                  if np.hypot(e.x - sample.entries[1][0], e.y - sample.entries[1][1]) > 0.5]
        one = figures([sample], [dataclasses.replace(located, entries=tuple(merged))])
        self.assertEqual(one.grouped, Share(0, 1))
        self.assertEqual(one.exact, Share(0, 1))
        self.assertEqual(one.darts_right, Share(2, 3))


if __name__ == "__main__":
    unittest.main()
