import datetime as dt
import shutil
import unittest

from PIL import Image

from darts_ml.check import check
from darts_ml.ingest import ingest
from darts_ml.labelme import label
from darts_ml.overlay import overlay
from darts_ml.paths import Round
from darts_ml.prefill import prefill
from darts_ml.repeatability import repeatability
from darts_ml.review import review
from synthetic import TemporaryData, as_stored, idle_window, jpeg_with_exif, pass_one_window, session

VISITS = [["T20", "T20", "S1"], ["D3", "S19 wire", "out"], ["S5", "T5", "25"]]
ORIENTATIONS = (6, 1, 3, 8)


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data

    def tearDown(self):
        self.td.cleanup()

    def capture(self):
        truths = session(self.td, "s01", VISITS)
        inbox = self.data.inbox("s01")
        inbox.mkdir(parents=True)
        start = dt.datetime(2026, 11, 14, 19, 0, 0)
        for index, photo in enumerate(sorted(truths)):
            with Image.open(self.data.photo("s01", photo)) as upright:
                orientation = ORIENTATIONS[index % len(ORIENTATIONS)]
                stored = as_stored(upright.convert("RGB"), orientation)
            jpeg_with_exif(stored, inbox / f"IMG_{900 - index}.jpg", orientation=orientation,
                           taken=start + dt.timedelta(seconds=20 * index))
        shutil.rmtree(self.data.photos("s01"))
        return truths

    def labelling_round(self, truths, round_, day):
        quiet = {"say": lambda _: None}
        label(self.data, "s01", round_, window=pass_one_window(truths, every_crossing=round_ is Round.C), **quiet)
        if round_ is not Round.C:
            prefill(self.data, "s01", round_)
        review(self.data, "s01", round_, window=idle_window(), ask=lambda _: "y", today=day, **quiet)

    def test_the_whole_loop_on_a_synthetic_capture_session(self):
        truths = self.capture()
        self.assertEqual(len(ingest(self.data, "s01")), 9)
        self.labelling_round(truths, Round.A, dt.date(2026, 11, 15))
        report = check(self.data, "s01")
        self.assertEqual(report.findings, [])
        self.assertEqual(len(overlay(self.data, "s01")), 9)
        self.labelling_round(truths, Round.B, dt.date(2026, 11, 18))
        self.labelling_round(truths, Round.C, dt.date(2026, 11, 19))
        self.assertTrue(check(self.data, "s01", Round.B).clean)
        reading = repeatability(self.data, "s01")
        self.assertEqual(reading.verdict, 1)
        self.assertEqual(reading.spreads["a–c, all crossings"].count, 9 * 80)
        self.assertEqual(reading.skipped, [])


if __name__ == "__main__":
    unittest.main()
