import unittest

import numpy as np

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_POINTS, HAND_POINTS, CALIBRATION_BY_NAME
from darts_ml.homography import crossing_errors_mm, fit, invert, project, residuals_mm

from synthetic import camera

BOARD = np.array([p.mm for p in CALIBRATION_POINTS])


class HomographyTest(unittest.TestCase):
    def test_recovers_an_oblique_view_to_well_under_a_micron(self):
        to_image = camera(yaw_deg=55.0, pitch_deg=20.0)
        pixels = project(to_image, BOARD)
        to_board = fit(pixels, BOARD)
        self.assertLess(residuals_mm(to_board, pixels, BOARD).max(), 1e-6)
        self.assertLess(crossing_errors_mm(to_board, invert(to_image)).max(), 1e-6)

    def test_four_hand_points_fit_exactly(self):
        to_image = camera(yaw_deg=-35.0)
        board = np.array([CALIBRATION_BY_NAME[n].mm for n in HAND_POINTS])
        to_board = fit(project(to_image, board), board)
        self.assertLess(crossing_errors_mm(to_board, invert(to_image)).max(), 1e-6)

    def test_a_one_millimetre_offset_reads_one_millimetre(self):
        to_board = invert(camera(yaw_deg=30.0))
        shifted = np.array([[1, 0, 0.6], [0, 1, 0.8], [0, 0, 1]]) @ to_board
        errors = crossing_errors_mm(to_board, shifted)
        np.testing.assert_allclose(errors, 1.0, atol=1e-9)

    def test_least_squares_averages_click_noise(self):
        to_image = camera(yaw_deg=40.0)
        noisy = project(to_image, BOARD) + np.random.default_rng(7).normal(0, 0.5, (len(BOARD), 2))
        errors = crossing_errors_mm(fit(noisy, BOARD), invert(to_image))
        self.assertLess(np.median(errors), 0.5)

    def test_refuses_fewer_than_four_points_and_a_line(self):
        with self.assertRaises(DartsMlError):
            fit(BOARD[:3], BOARD[:3])
        line = np.array([[0, 0], [1, 1], [2, 2], [3, 3]], dtype=float)
        with self.assertRaises(DartsMlError):
            fit(line, line)


if __name__ == "__main__":
    unittest.main()
