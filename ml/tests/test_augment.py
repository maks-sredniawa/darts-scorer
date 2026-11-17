import unittest

import numpy as np
from PIL import Image, ImageDraw

from darts_ml.augment import random_matrix, warp
from darts_ml.board import CALIBRATION_BY_NAME, CALIBRATION_POINTS
from darts_ml.homography import fit, project
from darts_ml.training_data import KeypointDataset, Sample
from synthetic import TemporaryData, board_image, camera

PHOTO = (1200, 900)
SIZE = 256
DART_MM = (40.0, 75.0)
CLOCKWISE = ("do-20-1", "do-6-10", "do-3-19")


def _orientation(points) -> float:
    (ax, ay), (bx, by), (cx, cy) = points
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


class AugmentTest(unittest.TestCase):
    def setUp(self):
        self.to_image = camera(yaw_deg=15.0, pitch_deg=6.0, size=PHOTO)
        self.board = np.array([p.mm for p in CALIBRATION_POINTS])

    def test_labels_land_on_the_same_board_positions_after_any_warp(self):
        rng = np.random.default_rng(1)
        dart = project(self.to_image, [DART_MM])
        for _ in range(50):
            matrix = random_matrix(self.to_image, SIZE, rng)
            moved = project(matrix, project(self.to_image, self.board))
            to_board = fit(moved, self.board)
            np.testing.assert_allclose(project(to_board, project(matrix, dart))[0], DART_MM, atol=1e-6)

    def test_the_pixels_move_with_the_labels(self):
        photo = Image.new("RGB", PHOTO, (0, 0, 0))
        x, y = project(self.to_image, [DART_MM])[0]
        ImageDraw.Draw(photo).ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255))
        rng = np.random.default_rng(2)
        checked = 0
        for _ in range(10):
            matrix = random_matrix(self.to_image, SIZE, rng)
            pixels = np.asarray(warp(photo, matrix, SIZE).convert("L"), dtype=float)
            if pixels.max() < 64:
                continue
            ys, xs = np.nonzero(pixels >= pixels.max() / 2)
            centre = np.average(np.column_stack([xs, ys]) + 0.5, axis=0, weights=pixels[ys, xs])
            np.testing.assert_allclose(centre, project(matrix, [(x, y)])[0], atol=1.5)
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_no_warp_ever_mirrors_the_board(self):
        rng = np.random.default_rng(3)
        crossings = project(self.to_image, [CALIBRATION_BY_NAME[n].mm for n in CLOCKWISE])
        before = np.sign(_orientation(crossings))
        for _ in range(500):
            matrix = random_matrix(self.to_image, SIZE, rng)
            self.assertEqual(np.sign(_orientation(project(matrix, crossings))), before)

    def test_the_dataset_serves_augmented_samples_of_the_right_shape(self):
        td = TemporaryData()
        self.addCleanup(td.cleanup)
        photo = td.data.root / "board.jpg"
        board_image(self.to_image, [DART_MM], size=PHOTO).save(photo, "JPEG", quality=90)
        pixels = project(self.to_image, self.board)
        sample = Sample(photo, tuple((i, float(x), float(y), 1.0) for i, (x, y) in enumerate(pixels)),
                        tuple(map(tuple, project(self.to_image, [DART_MM]))))
        image, heatmaps, *_ = KeypointDataset([sample], SIZE, augment=True)[0]
        self.assertEqual(tuple(image.shape), (3, SIZE, SIZE))
        self.assertEqual(heatmaps.shape[-1], SIZE // 4)


if __name__ == "__main__":
    unittest.main()
