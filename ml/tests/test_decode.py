import unittest

import numpy as np

from darts_ml.board import CALIBRATION_POINTS
from darts_ml.decode import MIN_INLIERS, THRESHOLD, decode, ransac
from darts_ml.homography import project
from darts_ml.model import ENTRY_CHANNEL
from darts_ml.training_data import targets
from synthetic import camera

SIZE = 512


def logits_of(points, size=SIZE):
    heatmaps, _, calibration_offsets, _, entry_offsets, _ = targets(points, size)
    clipped = np.clip(heatmaps, 1e-6, 1 - 1e-6)
    return np.concatenate([np.log(clipped / (1 - clipped)), calibration_offsets, entry_offsets])


class DecodeTest(unittest.TestCase):
    def test_calibration_points_come_back_within_a_twentieth_of_a_pixel(self):
        known = {0: (101.37, 240.81), 17: (300.02, 77.5), 79: (455.9, 401.26)}
        decoded = decode(logits_of([(c, x, y, 1.0) for c, (x, y) in known.items()]))
        self.assertEqual(set(decoded.calibration), set(known))
        for channel, (x, y) in known.items():
            peak = decoded.calibration[channel]
            self.assertLess(abs(peak.x - x), 0.05)
            self.assertLess(abs(peak.y - y), 0.05)

    def test_every_entry_point_in_a_channel_holding_three(self):
        known = [(200.3, 210.9), (209.7, 214.2), (350.55, 120.1)]
        decoded = decode(logits_of([(ENTRY_CHANNEL, x, y, 1.0) for x, y in known]))
        self.assertEqual(len(decoded.entries), 3)
        found = sorted((p.x, p.y) for p in decoded.entries)
        for (x, y), (fx, fy) in zip(sorted(known), found, strict=True):
            self.assertLess(abs(fx - x), 0.05)
            self.assertLess(abs(fy - y), 0.05)

    def test_a_channel_below_the_threshold_returns_nothing(self):
        logits = logits_of([(3, 100.0, 100.0, 1.0), (ENTRY_CHANNEL, 200.0, 200.0, 1.0)])
        below = np.log(THRESHOLD * 0.9 / (1 - THRESHOLD * 0.9))
        logits[[3, ENTRY_CHANNEL]] = np.minimum(logits[[3, ENTRY_CHANNEL]], below)
        decoded = decode(logits)
        self.assertNotIn(3, decoded.calibration)
        self.assertEqual(decoded.entries, ())

    def test_ransac_fits_the_board_and_leaves_out_a_misplaced_crossing(self):
        to_image = camera(yaw_deg=35.0, pitch_deg=10.0, size=(1600, 1200))
        pixels = project(to_image, [p.mm for p in CALIBRATION_POINTS])
        calibration = {c: tuple(xy) for c, xy in enumerate(pixels)}
        calibration[5] = (pixels[5][0] + 40.0, pixels[5][1] - 25.0)
        to_board, inliers = ransac(calibration)
        self.assertNotIn(5, inliers)
        self.assertEqual(len(inliers), len(CALIBRATION_POINTS) - 1)
        board = np.array([p.mm for p in CALIBRATION_POINTS])
        np.testing.assert_allclose(project(to_board, np.delete(pixels, 5, axis=0)), np.delete(board, 5, axis=0),
                                   atol=1e-6)

    def test_too_few_crossings_is_no_board(self):
        to_image = camera()
        pixels = project(to_image, [p.mm for p in CALIBRATION_POINTS[:MIN_INLIERS - 1]])
        self.assertIsNone(ransac({c: tuple(xy) for c, xy in enumerate(pixels)}))


if __name__ == "__main__":
    unittest.main()
