import contextlib
import io
import json
import os
import unittest
from unittest import mock

import numpy as np
import torch

from darts_ml.board import Score
from darts_ml.cli import main
from darts_ml.evaluate import PredictedEntry, Share
from darts_ml.homography import invert, project
from darts_ml.locate import Located
from darts_ml.marked_reading import NOTE, marked_visits, read_marked
from darts_ml.model import KeypointNet
from synthetic import TemporaryData, board_image, camera, dart_mm

SIZE = (480, 640)


def dart(token, to_image, read=None, moved=False, corrected=False, at=True):
    x, y = project(to_image, [dart_mm(token)])[0]
    point = {"x": float(x), "y": float(y)}
    seen = None if read is None else {"at": point if not moved else {"x": 1.0, "y": 1.0}, "score": read, "unsure": False}
    return {"number": 1, "read": seen, "at": point if at else None, "score": token, "unsure": False,
            "corrected": corrected, "moved": moved}


class MarkedFixture:
    def __init__(self, td: TemporaryData) -> None:
        self.day = td.data.phone_captures() / "2026-11-20"
        self.day.mkdir(parents=True)
        self.to_image = camera(yaw_deg=5.0, pitch_deg=6.0, distance_mm=1100.0, focal_px=1500.0, size=SIZE)

    def visit(self, uuid: str, darts, removed=(), found=True, photo=True) -> None:
        if photo:
            board_image(self.to_image, size=SIZE).save(self.day / f"{uuid}.jpg", "JPEG", quality=90)
        record = {"versionName": "0.1.0", "versionCode": 179, "photo": f"{uuid}.jpg", "width": SIZE[0],
                  "height": SIZE[1], "boardFound": found, "toBoard": None, "crop": None, "total": 0,
                  "darts": list(darts), "removed": [{"number": 9, "read": {"at": {"x": 0, "y": 0}, "score": s,
                                                                          "unsure": True}} for s in removed]}
        (self.day / f"{uuid}.json").write_text(json.dumps(record), encoding="utf-8")


class MarkedVisitsTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.fixture = MarkedFixture(self.td)

    def tearDown(self):
        self.td.cleanup()

    def test_the_owners_darts_are_the_truth_and_only_the_points_the_owner_stands_behind_are_kept(self):
        m = self.fixture.to_image
        self.fixture.visit("a", [dart("T20", m, read="T20"), dart("S5", m, read="S1", moved=True, corrected=True),
                                 dart("25", m, read="S18", corrected=True), dart("miss", m, corrected=True, at=False)],
                           removed=["D12"])
        [visit], skipped = marked_visits(self.td.data.phone_captures())
        self.assertEqual(skipped, [])
        self.assertEqual(sorted(map(str, visit.truth)), ["25", "S5", "T20", "miss"])
        self.assertEqual(sorted(map(str, visit.app_read)), ["D12", "S1", "S18", "T20"])
        self.assertEqual((len(visit.placed), len(visit.accepted)), (1, 1))

    def test_a_record_without_its_photo_or_unreadable_is_skipped_by_name(self):
        self.fixture.visit("gone", [], photo=False)
        (self.fixture.day / "broken.json").write_text("{", encoding="utf-8")
        visits, skipped = marked_visits(self.td.data.phone_captures())
        self.assertEqual(visits, [])
        self.assertEqual(sorted(name for name, _ in skipped), ["broken.json", "gone.json"])


class ReadMarkedTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.fixture = MarkedFixture(self.td)
        m = self.fixture.to_image
        self.fixture.visit("1-right", [dart("T20", m, read="T20"), dart("S5", m, read="S1", moved=True, corrected=True)])
        self.fixture.visit("2-wrong", [dart("D16", m, read="D16"), dart("S3", m, read="S3")])
        self.fixture.visit("3-unfound", [dart("50", m, read="50")], found=False)
        self.visits, _ = marked_visits(self.td.data.phone_captures())

    def tearDown(self):
        self.td.cleanup()

    def test_exactly_right_darts_right_and_the_error_in_board_mm(self):
        to_board = invert(self.fixture.to_image)

        def entries(*mm):
            return tuple(PredictedEntry(float(x), float(y)) for x, y in project(self.fixture.to_image, list(mm)))

        x20, y20 = dart_mm("T20")
        x5, y5 = dart_mm("S5")
        located = [
            Located(to_board, entries=entries((x20, y20 + 0.5), (x5 + 2.0, y5))),
            Located(to_board, entries=entries(dart_mm("D16"))),
            Located(None),
        ]
        reading = read_marked(self.visits, located)
        self.assertEqual(reading.found, Share(2, 3))
        self.assertEqual(reading.exact, Share(1, 3))
        self.assertEqual(reading.darts_right, Share(3, 5))
        self.assertAlmostEqual(reading.placed.median_mm, 2.0, places=3)
        self.assertEqual(reading.placed_unmatched, 0)
        self.assertEqual(reading.accepted.count, 2)
        self.assertEqual(reading.accepted_unmatched, 2)
        self.assertEqual(reading.app_exact, Share(2, 3))
        self.assertEqual(reading.app_found, Share(2, 3))
        self.assertTrue(any("exactly right 1/3" in line for line in reading.lines()))


class StepTest(unittest.TestCase):
    def test_the_step_reads_a_run_on_the_marked_visits_and_says_it_is_read_once(self):
        td = TemporaryData()
        self.addCleanup(td.cleanup)
        MarkedFixture(td).visit("v", [dart("S5", camera(size=SIZE), read="S5")])
        run = td.data.runs() / "2026-11-21-tiny"
        run.mkdir(parents=True)
        torch.save({"model": KeypointNet().state_dict(), "epoch": 1}, run / "best.pt")
        (run / "config.json").write_text(json.dumps({"size": 64, "batch": 2, "bf16": False, "channels_last": False}))
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"DARTS_DATA": str(td.data.root)}), contextlib.redirect_stdout(out), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["evaluate-marked", "--run", run.name, "--device", "cpu", "--workers", "0"]), 0)
        self.assertIn("1 marked Visits", out.getvalue())
        self.assertIn("Board found", out.getvalue())
        self.assertIn(NOTE, out.getvalue())

    def test_no_marked_visits_is_a_refusal(self):
        td = TemporaryData()
        self.addCleanup(td.cleanup)
        run = td.data.runs() / "r"
        run.mkdir(parents=True)
        (run / "config.json").write_text(json.dumps({"size": 64, "batch": 2}))
        with mock.patch.dict(os.environ, {"DARTS_DATA": str(td.data.root)}), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["evaluate-marked", "--run", "r", "--device", "cpu"]), 2)


if __name__ == "__main__":
    unittest.main()
