import contextlib
import io
import json
import unittest
from collections import Counter
from fractions import Fraction
from unittest import mock

import numpy as np

from darts_ml.board import CALIBRATION_POINTS, INNER_DOUBLE, SEGMENTS, Score, board_point, boundary_degrees
from darts_ml.cli import main
from darts_ml.evaluate import BAR, Bar, PredictionsError, Share, board_met, evaluate, visits_met
from darts_ml.heldout import HeldOutError, freeze
from darts_ml.homography import project
from darts_ml.repeatability import Spread
from synthetic import TemporaryData, dart_mm, reviewed_session, without_last_entry_in

VISITS = [["T20", "T20", "S1"], ["S5", "T5", "S20"], ["D3", "S19", "out"], ["25", "T19", "S7 hidden"]]
HIDDEN_IN_P1 = "s04-v04-p1"


class BarTest(unittest.TestCase):
    def test_the_bar_is_d1(self):
        self.assertEqual(
            BAR,
            Bar(board_found=Fraction(98, 100), wire_median_mm=0.5, wire_p95_mm=1.0,
                visits_exact=Fraction(80, 100), visits_counted=60),
        )

    def test_board_found_in_98_percent_is_met_and_one_photo_fewer_is_not(self):
        exact = Spread(400, 0.5, 1.0)
        self.assertTrue(board_met(Share(49, 50), exact, exact))
        self.assertFalse(board_met(Share(97, 99), exact, exact))
        self.assertFalse(board_met(Share(0, 0), exact, exact))

    def test_each_wire_row_is_held_to_both_its_median_and_its_95th_percentile(self):
        at_the_bar = Spread(400, 0.5, 1.0)
        for spoilt in (Spread(400, 0.5001, 1.0), Spread(400, 0.5, 1.0001)):
            with self.subTest(spoilt=spoilt):
                self.assertFalse(board_met(Share(50, 50), spoilt, at_the_bar))
                self.assertFalse(board_met(Share(50, 50), at_the_bar, spoilt))
        self.assertTrue(board_met(Share(50, 50), at_the_bar, at_the_bar))
        self.assertFalse(board_met(Share(50, 50), None, at_the_bar))
        self.assertFalse(board_met(Share(50, 50), at_the_bar, None))

    def test_visits_need_80_percent_over_at_least_60(self):
        self.assertTrue(visits_met(Share(48, 60)))
        self.assertFalse(visits_met(Share(47, 60)))
        self.assertFalse(visits_met(Share(59, 59)))
        self.assertTrue(visits_met(Share(60, 60)))


def photo_prediction(to_image, darts_mm, offset_mm=(0.0, 0.0), scale=1.0, calibration=None, low_confidence=()):
    points = [p for p in CALIBRATION_POINTS if calibration is None or p.name in calibration]
    pixels = project(to_image, [np.add(np.multiply(p.mm, scale), offset_mm) for p in points])
    entries = project(to_image, list(darts_mm)) if len(darts_mm) else []
    return {
        "calibration": {p.name: [float(x), float(y)] for p, (x, y) in zip(points, pixels, strict=True)},
        "entries": [
            {"x": float(x), "y": float(y), "low_confidence": index in low_confidence}
            for index, (x, y) in enumerate(entries)
        ],
    }


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.manifest = self.data.root / "splits" / "held-out.toml"

    def tearDown(self):
        self.td.cleanup()

    def freeze(self, short=(), **kwargs):
        edits = [without_last_entry_in(photo) for photo in (HIDDEN_IN_P1, *short)]

        def edit(photo, to_image, shapes):
            for each in edits:
                shapes = each(photo, to_image, shapes)
            return shapes

        self.truths = reviewed_session(self.td, "s04", VISITS, held_out=True, edit=edit, **kwargs)
        freeze(self.data).save(self.manifest)

    def predictions(self, changes=None, drop=()):
        photos = {}
        for photo, (to_image, in_board) in self.truths.items():
            if photo in drop:
                continue
            darts, extra = in_board, {}
            if changes and photo in changes:
                darts, extra = changes[photo](in_board)
            photos[photo] = photo_prediction(to_image, darts, **extra)
        path = self.data.root / "predictions.json"
        path.write_text(json.dumps({"photos": photos}), encoding="utf-8")
        return evaluate(self.data, path, self.manifest)

    def assertNoError(self, spread, crossings):
        self.assertEqual(spread.count, crossings)
        self.assertLess(spread.p95_mm, 1e-6)

    def test_the_labels_read_perfect(self):
        self.freeze()
        result = evaluate(self.data, "labels", self.manifest)
        self.assertEqual(result.found, Share(12, 12))
        self.assertNoError(result.treble, 12 * 40)
        self.assertNoError(result.double, 12 * 40)
        self.assertEqual(result.b2, Share(3, 3))
        self.assertEqual(result.hidden, 1)
        self.assertEqual((result.b2_p2, result.b2_p3, result.b2_merged), (Share(3, 3),) * 3)
        self.assertEqual(result.hidden_merged, Share(1, 1))
        self.assertEqual(result.darts_right, Share(8, 8))
        self.assertEqual(result.wrong_flagged, Share(0, 0))
        self.assertTrue(result.board_met)
        self.assertFalse(result.visits_met, "3 counted Visits are short of the 60 the bar needs")

    def test_every_homography_offset_by_1_mm_reads_1_mm(self):
        self.freeze()
        offset = {photo: (lambda darts: (darts, {"offset_mm": (0.6, 0.8)})) for photo in self.truths}
        result = self.predictions(offset)
        for spread in (result.treble, result.double):
            self.assertAlmostEqual(spread.median_mm, 1.0, places=6)
            self.assertAlmostEqual(spread.p95_mm, 1.0, places=6)
        self.assertFalse(result.board_met)

    def test_the_treble_and_the_double_wires_are_read_apart(self):
        self.freeze()
        larger = {photo: (lambda darts: (darts, {"scale": 1 / 1.005})) for photo in self.truths}
        result = self.predictions(larger)
        self.assertAlmostEqual(result.treble.median_mm, 0.005 * (97.15 + 106.65) / 2, places=5)
        self.assertAlmostEqual(result.double.median_mm, 0.005 * (159.75 + 169.25) / 2, places=5)
        self.assertAlmostEqual(result.treble.p95_mm, 0.005 * 106.65, places=5)
        self.assertAlmostEqual(result.double.p95_mm, 0.005 * 169.25, places=5)

    def test_an_extra_dart_and_two_compensating_wrong_darts_are_both_wrong(self):
        self.freeze()
        extra = lambda darts: ([*darts, dart_mm("T20", nudge_deg=-3.0)], {})
        compensating = lambda darts: ([dart_mm("S10"), dart_mm("S10", nudge_deg=2.0), darts[2]], {})
        self.assertEqual(sum(Score.parse(t).value for t in ("S10", "S10")), sum(Score.parse(t).value for t in ("S5", "T5")))
        result = self.predictions({"s04-v01-p1": extra, "s04-v02-p1": compensating})
        self.assertEqual(result.b2, Share(1, 3))
        self.assertEqual(result.darts_right, Share(6, 8))

    def test_a_visit_hidden_in_p1_is_left_out_of_b2_and_counted_on_its_own(self):
        self.freeze()
        result = self.predictions({HIDDEN_IN_P1: lambda darts: (darts[:1], {})})
        self.assertEqual(result.b2, Share(3, 3))
        self.assertEqual(result.hidden, 1)
        self.assertEqual(result.hidden_p1_short, Share(1, 1))
        self.assertEqual(result.hidden_merged, Share(1, 1))

    def test_merging_keeps_darts_further_apart_than_the_gate_separate(self):
        self.freeze()
        result = self.predictions({
            HIDDEN_IN_P1: lambda darts: (darts[:2], {}),
            "s04-v04-p2": lambda darts: ([darts[0], darts[2]], {}),
        })
        self.assertEqual(result.hidden_merged, Share(1, 1))

    def test_a_board_not_found_counts_against_found_and_is_left_out_of_the_wire_rows(self):
        self.freeze()
        three_points = lambda darts: (darts, {"calibration": {"do-5-20", "do-17-3", "do-8-11"}})
        result = self.predictions({"s04-v02-p2": three_points}, drop={"s04-v03-p3"})
        self.assertEqual(result.found, Share(10, 12))
        self.assertNoError(result.treble, 10 * 40)
        self.assertEqual(result.b2_p2, Share(2, 3))
        self.assertEqual(result.b2_p3, Share(2, 3))

    def test_an_open_mismatch_on_p1_lowers_b2_and_one_on_p2_alone_does_not(self):
        recorded = [["T20", "T20", "S5"], *VISITS[1:]]
        mismatches = [*((f"s04-v01-p{a}", "the S1 was read as S5 at the Board") for a in (1, 2, 3)),
                      ("s04-v02-p2", "the S20 fell out before p2")]
        self.freeze(short=["s04-v02-p2"], recorded=recorded, mismatches=mismatches)
        result = evaluate(self.data, "labels", self.manifest)
        self.assertEqual(result.b2, Share(2, 3))
        self.assertEqual(result.b2_open_p1_mismatches, 1)
        self.assertEqual(result.b2_p2, Share(1, 3))

    def test_a_wrong_visit_is_flagged_only_by_a_trigger_adr_0008_names(self):
        self.freeze()
        on_the_wire = board_point(INNER_DOUBLE.centre_mm - 0.1, boundary_degrees(SEGMENTS.index(3)) - 9.0)
        changes = {
            "s04-v01-p1": lambda darts: (darts[:2], {}),
            "s04-v02-p1": lambda darts: ([darts[0], darts[1], dart_mm("S5")], {}),
            "s04-v03-p1": lambda darts: ([on_the_wire, darts[1]], {}),
        }
        result = self.predictions(changes)
        self.assertEqual(result.b2, Share(0, 3))
        self.assertEqual(result.wrong_flagged, Share(2, 3))
        self.assertEqual(result.flags, Counter({"fewer Darts found than thrown": 2, "an Entry point within 2 mm of a wire": 1}))
        unsure = dict(changes, **{"s04-v02-p1": lambda darts: ([darts[0], darts[1], dart_mm("S5")], {"low_confidence": (2,)})})
        self.assertEqual(self.predictions(unsure).wrong_flagged, Share(3, 3))

    def test_it_reads_only_a_held_out_set_that_matches_its_manifest(self):
        self.freeze()
        path = self.data.photo("s04", "s04-v01-p1")
        path.write_bytes(path.read_bytes() + b"\0")
        with self.assertRaisesRegex(HeldOutError, "s04-v01-p1 Photo: changed"):
            evaluate(self.data, "labels", self.manifest)

    def test_a_prediction_naming_no_calibration_point_is_refused(self):
        self.freeze()
        path = self.data.root / "predictions.json"
        path.write_text(json.dumps({"photos": {"s04-v01-p1": {"calibration": {"bull": [1, 2]}}}}))
        with self.assertRaisesRegex(PredictionsError, "names no Calibration point: bull"):
            evaluate(self.data, path, self.manifest)

    def test_the_command_prints_the_bar_and_exits_1_when_it_is_not_met(self):
        self.freeze()
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DARTS_DATA": str(self.data.root)}), contextlib.redirect_stdout(out):
            code = main(["evaluate", "--predictions", "labels", "--manifest", str(self.manifest)])
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("Board found              12/12 (100.0%)", text)
        self.assertIn("exactly right from p1    3/3 (100.0%)", text)
        self.assertIn("The bar for opening phase 1: NOT met", text)


if __name__ == "__main__":
    unittest.main()
