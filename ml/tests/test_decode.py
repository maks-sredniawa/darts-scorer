import unittest

import numpy as np

from darts_ml.board import CALIBRATION_POINTS
from darts_ml.decode import MIN_INLIERS, THRESHOLD, EntryRule, decode, kept_entries, ransac
from darts_ml.homography import project
from darts_ml.model import BOARD_STRIDE, ENTRY_POINT, ENTRY_STRIDE, Heads
from darts_ml.training_data import targets
from synthetic import camera

SIZE = 512


def logits_of(points, size=SIZE, entry_stride=ENTRY_STRIDE) -> Heads:
    made = targets(points, size, entry_stride)

    def logit(heat):
        clipped = np.clip(heat, 1e-6, 1 - 1e-6)
        return np.log(clipped / (1 - clipped))

    return Heads(np.concatenate([logit(made.board_heat), made.board_offsets]),
                 np.concatenate([logit(made.entry_heat[None]), made.entry_offsets]))


class DecodeTest(unittest.TestCase):
    def test_calibration_points_come_back_within_a_twentieth_of_a_pixel(self):
        known = {0: (101.37, 240.81), 17: (300.02, 77.5), 79: (455.9, 401.26)}
        decoded = decode(logits_of([(c, x, y, 1.0) for c, (x, y) in known.items()]))
        self.assertEqual(set(decoded.calibration), set(known))
        for channel, (x, y) in known.items():
            peak = decoded.calibration[channel]
            self.assertLess(abs(peak.x - x), 0.05)
            self.assertLess(abs(peak.y - y), 0.05)

    def test_every_entry_point_in_a_channel_holding_three_at_either_stride(self):
        known = [(200.3, 210.9), (209.7, 214.2), (350.55, 120.1)]
        for stride in (ENTRY_STRIDE, BOARD_STRIDE):
            with self.subTest(stride=stride):
                heads = logits_of([(ENTRY_POINT, x, y, 1.0) for x, y in known], entry_stride=stride)
                self.assertEqual(heads.entry.shape[-1], SIZE // stride)
                decoded = decode(heads)
                self.assertEqual(len(decoded.entries), 3)
                found = sorted((p.x, p.y) for p in decoded.entries)
                for (x, y), (fx, fy) in zip(sorted(known), found, strict=True):
                    self.assertLess(abs(fx - x), 0.05)
                    self.assertLess(abs(fy - y), 0.05)

    def test_two_entry_points_three_pixels_apart_are_two_only_at_stride_two(self):
        known = [(200.5, 200.5), (203.5, 200.5)]
        points = [(ENTRY_POINT, x, y, 1.0) for x, y in known]
        self.assertEqual(len(decode(logits_of(points, entry_stride=ENTRY_STRIDE)).entries), 2)
        self.assertEqual(len(decode(logits_of(points, entry_stride=BOARD_STRIDE)).entries), 1)

    def test_a_channel_below_the_threshold_returns_nothing(self):
        heads = logits_of([(3, 100.0, 100.0, 1.0), (ENTRY_POINT, 200.0, 200.0, 1.0)])
        below = np.log(THRESHOLD * 0.9 / (1 - THRESHOLD * 0.9))
        for heat in (heads.board[3], heads.entry[0]):
            np.minimum(heat, below, out=heat)
        decoded = decode(heads)
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


class EntryRuleTest(unittest.TestCase):
    BOARD_MM = np.array([[0.0, 100.0], [0.0, 96.0], [40.0, 0.0], [48.0, 0.0], [-90.0, 0.0]])
    CONFIDENCES = [0.9, 0.4, 0.8, 0.7, 0.3]

    def test_a_rule_without_limits_keeps_every_peak(self):
        self.assertEqual(kept_entries(self.BOARD_MM, self.CONFIDENCES, EntryRule(0.0, 0.0, None)), [0, 1, 2, 3, 4])

    def test_a_weaker_peak_close_to_a_stronger_one_is_dropped(self):
        kept = kept_entries(self.BOARD_MM, self.CONFIDENCES, EntryRule(threshold=0.0, apart_mm=6.0, most=None))
        self.assertEqual(kept, [0, 2, 3, 4])

    def test_the_most_confident_are_kept_up_to_the_cap(self):
        kept = kept_entries(self.BOARD_MM, self.CONFIDENCES, EntryRule(threshold=0.0, apart_mm=6.0, most=3))
        self.assertEqual(kept, [0, 2, 3])

    def test_peaks_under_the_threshold_are_dropped(self):
        self.assertEqual(kept_entries(self.BOARD_MM, self.CONFIDENCES, EntryRule(0.5, 0.0, None)), [0, 2, 3])


if __name__ == "__main__":
    unittest.main()
