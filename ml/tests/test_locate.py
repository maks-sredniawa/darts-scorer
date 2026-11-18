import dataclasses
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from darts_ml.augment import letterbox
from darts_ml.board import CALIBRATION_POINTS
from darts_ml.evaluate import Share
from darts_ml.homography import project
from darts_ml.decode import EntryRule
from darts_ml.evaluate import PredictedEntry
from darts_ml.locate import Inference, Located, _logits, figures, located_from_targets, refiltered
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


class _Recording(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.batches: list[int] = []

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        self.batches.append(len(images))
        return images[:, :1]


class LocateTest(unittest.TestCase):
    def test_refiltering_measures_apart_in_board_millimetres(self):
        to_board = np.diag([0.5, 0.5, 1.0])
        entries = (PredictedEntry(100, 100, confidence=0.9), PredictedEntry(110, 100, confidence=0.4),
                   PredictedEntry(300, 100, confidence=0.6))
        kept = refiltered(Located(to_board, entries=entries), EntryRule(threshold=0.0, apart_mm=6.0))
        self.assertEqual(kept.entries, (entries[0], entries[2]))
        self.assertEqual(refiltered(Located(None, entries=entries), EntryRule(most=1)).entries, entries)

    def test_a_short_last_batch_runs_at_full_size_and_yields_only_its_own_photos(self):
        with tempfile.TemporaryDirectory() as folder:
            items = []
            for shade in (10, 60, 110, 160, 210):
                path = Path(folder) / f"{shade}.png"
                Image.new("RGB", (8, 8), (shade, shade, shade)).save(path)
                items.append((path, letterbox((8, 8), 8)))
            model = _Recording()
            outputs = list(_logits(Inference(model, "cpu", 8, batch=2, workers=0), items))
        self.assertEqual(model.batches, [2, 2, 2])
        self.assertEqual(len(outputs), 5)
        means = [float(o.mean()) for o in outputs]
        self.assertEqual(means, sorted(means))
        self.assertEqual(len(set(means)), 5)

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
