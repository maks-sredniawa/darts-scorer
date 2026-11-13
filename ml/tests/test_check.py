import unittest


from darts_ml.check import check
from darts_ml.homography import invert, project
from darts_ml.labelme import ENTRY, Shape, read_label, write_label
from darts_ml.manifest import Review, ReviewManifest
from darts_ml.review import label_sha256
from synthetic import SIZE, TemporaryData, crossings, entries, session

VISITS = [["T20", "T20", "S1"], ["D3", "S19 wire", "out"], ["S5", "T5", "S20"]]


def drop_an_entry_in(target):
    def edit(photo, to_image, shapes):
        if photo != target:
            return shapes
        return [s for s in shapes if s.label != ENTRY] + [s for s in shapes if s.label == ENTRY][:-1]

    return edit


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data

    def tearDown(self):
        self.td.cleanup()

    def build(self, visits=VISITS, held_out=False, mismatches=(), edit=None, recorded=None):
        truths = session(self.td, "s01", visits, held_out=held_out, mismatches=mismatches)
        if recorded is not None:
            self.td.write_sheet("s01", recorded, held_out=held_out, mismatches=mismatches)
        manifest = ReviewManifest.load(self.data.labels("s01"))
        for photo, (to_image, in_board) in truths.items():
            shapes = crossings(to_image) + entries(to_image, in_board)
            if edit:
                shapes = edit(photo, to_image, shapes)
            path = self.td.write_label("s01", photo, shapes)
            record = manifest.record(photo)
            record.reviews = [Review(day, label_sha256(path)) for day in ("2026-11-14", "2026-11-15")]
        manifest.save()
        return check(self.data, "s01")

    @staticmethod
    def steps(report):
        return sorted((f.where, f.step) for f in report.findings)

    def test_true_labels_are_clean(self):
        report = self.build()
        self.assertEqual(report.findings, [])
        self.assertLess(max(report.across_angles_mm), 1e-6)

    def test_a_dart_hidden_in_p1_must_be_marked_hidden(self):
        marked = [*VISITS[:2], ["S5", "T5", "S20 hidden"]]
        self.assertEqual(self.build(edit=drop_an_entry_in("s01-v03-p1"), recorded=marked).findings, [])
        report = self.build(edit=drop_an_entry_in("s01-v03-p1"))
        self.assertEqual(self.steps(report), [("s01-v03-p1", "hidden")])

    def test_a_dart_missed_in_p2_is_found_unless_marked_hidden_there_or_excused(self):
        report = self.build(edit=drop_an_entry_in("s01-v03-p2"))
        self.assertEqual(self.steps(report), [("s01-v03-p2", "score")])
        self.assertIn("2 Entry points for the 3 Darts", report.findings[0].message)
        marked = [*VISITS[:2], ["S5", "T5", "S20 hidden-p2"]]
        self.assertEqual(self.build(edit=drop_an_entry_in("s01-v03-p2"), recorded=marked).findings, [])
        excused = self.build(edit=drop_an_entry_in("s01-v03-p2"), mismatches=[("s01-v03-p2", "the S20 was knocked out before p2")])
        self.assertEqual(excused.findings, [])

    def test_a_hidden_mark_for_another_angle_does_not_excuse_p2(self):
        marked = [*VISITS[:2], ["S5", "T5", "S20 hidden-p3"]]
        report = self.build(edit=drop_an_entry_in("s01-v03-p2"), recorded=marked)
        self.assertEqual(self.steps(report), [("s01-v03-p2", "score")])

    def test_a_wrong_score_is_found_and_an_open_mismatch_excuses_it(self):
        recorded = [["T20", "T20", "S5"], *VISITS[1:]]
        report = self.build(recorded=recorded)
        self.assertEqual(self.steps(report), [(f"s01-v01-p{a}", "score") for a in (1, 2, 3)])
        self.assertIn("S1 not recorded", report.findings[0].message)
        mismatches = [(f"s01-v01-p{a}", "fell out before the reading") for a in (1, 2, 3)]
        excused = self.build(recorded=recorded, mismatches=mismatches)
        self.assertEqual(excused.findings, [])
        self.assertEqual(len(excused.open_mismatches), 3)

    def test_entry_points_that_disagree_across_angles_are_found(self):
        def shift(photo, to_image, shapes):
            if photo != "s01-v02-p2":
                return shapes
            first = next(i for i, shape in enumerate(shapes) if shape.label == ENTRY)
            mm = project(invert(to_image), [shapes[first].xy])[0] + [0.0, 2.5]
            x, y = project(to_image, [mm])[0]
            return [*shapes[:first], Shape(ENTRY, float(x), float(y)), *shapes[first + 1 :]]

        report = self.build(edit=shift)
        self.assertEqual({f.step for f in report.findings}, {"angles"})
        self.assertTrue(all("2.5 mm apart" in f.message for f in report.findings))

    def test_a_misclicked_crossing_is_listed_by_the_fit(self):
        def misclick(photo, to_image, shapes):
            if photo != "s01-v01-p1":
                return shapes
            return [Shape(s.label, s.x + 8.0, s.y) if s.label == "ti-6-10" else s for s in shapes]

        report = self.build(edit=misclick)
        self.assertEqual(self.steps(report), [("s01-v01-p1", "fit")])
        self.assertIn("ti-6-10", report.findings[0].message)

    def test_lint(self):
        def spoil(photo, to_image, shapes):
            if photo == "s01-v01-p1":
                return shapes + [Shape("bullseye", 10.0, 10.0), shapes[0], Shape(ENTRY, 300.0, 200.0)]
            return shapes

        report = self.build(edit=spoil)
        messages = " | ".join(f.message for f in report.findings if f.where == "s01-v01-p1")
        for expected in ("not in the list: bullseye", "labelled twice", "4 Entry points, but 3 Darts"):
            self.assertIn(expected, messages)

    def test_lint_image_data_size_and_placed_darts(self):
        report = self.build(visits=[["T20", "T20 placed", "S1"]], held_out=True)
        self.assertIn(("s01 Visit 1", "lint"), self.steps(report))
        path = self.data.labels("s01") / "s01-v01-p1.json"
        label = read_label(path)
        write_label(path, label.photo_path(), SIZE[0] + 2, SIZE[1], label.shapes)
        text = path.read_text().replace('"imageData": null', '"imageData": "aGk="')
        path.write_text(text)
        messages = " | ".join(f.message for f in check(self.data, "s01").findings if f.where == "s01-v01-p1")
        self.assertIn("embeds the image", messages)
        self.assertIn("642×480", messages)
        self.assertIn("edited after its last review", messages)


if __name__ == "__main__":
    unittest.main()
