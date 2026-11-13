import datetime as dt
import unittest

from darts_ml.check import check
from darts_ml.labelme import read_label, write_label
from darts_ml.manifest import ReviewManifest
from darts_ml.review import is_reviewed, review
from synthetic import SIZE, TemporaryData, full_labels, idle_window, session

DAY_1, DAY_2, DAY_3 = dt.date(2026, 11, 14), dt.date(2026, 11, 15), dt.date(2026, 11, 16)


def nudge_window(photo: str):
    def window(photo_path, labels):
        if photo_path.stem == photo:
            path = labels / f"{photo}.json"
            label = read_label(path)
            first, *rest = label.shapes
            moved = first.__class__(first.label, first.x + 3.0, first.y, first.shape_type, first.flags, first.description)
            write_label(path, photo_path, SIZE[0], SIZE[1], [moved, *rest])
        return 20.0

    return window


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data

    def tearDown(self):
        self.td.cleanup()

    def labelled(self, held_out=False):
        truths = session(self.td, "s01", [["T20", "T20", "S1"]], held_out=held_out)
        full_labels(self.td, "s01", truths)

    def run_review(self, day, window=None, answer="y"):
        return review(self.data, "s01", window=window or idle_window(), ask=lambda _: answer, say=lambda _: None, today=day)

    def review_findings(self):
        return [f for f in check(self.data, "s01").findings if "review" in f.message]

    def test_a_reviewed_label_is_reviewed_until_it_is_edited(self):
        self.labelled()
        self.assertEqual(self.run_review(DAY_1), 3)
        self.assertTrue(check(self.data, "s01").clean)
        path = self.data.labels("s01") / "s01-v01-p2.json"
        label = read_label(path)
        write_label(path, label.photo_path(), label.width, label.height, label.shapes[1:])
        self.assertFalse(is_reviewed(ReviewManifest.load(self.data.labels("s01")).get("s01-v01-p2"), path, False))
        findings = self.review_findings()
        self.assertEqual([f.where for f in findings], ["s01-v01-p2"])
        self.assertIn("edited after its last review", findings[0].message)

    def test_answering_no_records_nothing(self):
        self.labelled()
        self.assertEqual(self.run_review(DAY_1, answer="n"), 0)
        self.assertEqual(len(self.review_findings()), 3)

    def test_a_held_out_photo_reviewed_once_fails(self):
        self.labelled(held_out=True)
        self.run_review(DAY_1)
        self.assertEqual(len(self.review_findings()), 3)
        self.assertEqual(self.run_review(DAY_1), 0, "a second review on the same day counted")
        self.assertEqual(len(self.review_findings()), 3)
        self.run_review(DAY_2)
        self.assertEqual(self.review_findings(), [])
        self.assertTrue(check(self.data, "s01").clean)

    def test_a_held_out_photo_changed_by_its_second_review_needs_a_third(self):
        self.labelled(held_out=True)
        self.run_review(DAY_1)
        self.run_review(DAY_2, window=nudge_window("s01-v01-p3"))
        self.assertEqual([f.where for f in self.review_findings()], ["s01-v01-p3"])
        self.run_review(DAY_3)
        self.assertEqual(self.review_findings(), [])

    def test_review_seconds_are_recorded(self):
        self.labelled()
        self.run_review(DAY_1)
        record = ReviewManifest.load(self.data.labels("s01")).get("s01-v01-p1")
        self.assertEqual(record.review_seconds, 30.0)
        self.assertEqual(record.reviews[0].day, DAY_1)


if __name__ == "__main__":
    unittest.main()
