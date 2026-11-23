import contextlib
import datetime as dt
import io
import json
import tomllib
import unittest
from unittest import mock

from PIL import Image

from darts_ml.capture_sessions import Light, Mount, load_sheet
from darts_ml.check import check
from darts_ml.cli import main
from darts_ml.evaluate import Share, evaluate, report
from darts_ml.heldout import HeldOutError, HeldOutSet
from darts_ml.labelme import label
from darts_ml.mounted import MountedError, build_mounted
from darts_ml.prefill import prefill
from darts_ml.records import build
from darts_ml.review import review
from synthetic import SIZE, TemporaryData, board_image, camera, idle_window, pass_one_window

DAY = "2026-11-24"
MOUNT = Mount(160.0, 75.0, 30.0)
START = dt.datetime(2026, 11, 24, 18, 0, tzinfo=dt.UTC)
FILLED = [{"number": n, "read": None, "at": None, "score": "miss", "unsure": False, "corrected": False,
           "moved": False, "filled": True} for n in (1, 2, 3)]


def thrown(score: str, **extra) -> dict:
    return {"number": 1, "read": None, "at": {"x": 1.0, "y": 2.0}, "score": score, "unsure": False,
            "corrected": False, "moved": False, **extra}


class PhoneCaptures:
    """A pulled day of marked Visits: a Photo and its record per Visit, as KeepMarked.kt writes them."""

    def __init__(self, td: TemporaryData) -> None:
        self.data = td.data
        self.day = td.data.phone_captures() / DAY
        self.day.mkdir(parents=True)
        self.truths: dict[str, tuple] = {}

    def keep(self, uuid: str, minutes: float, darts=FILLED, found=True, yaw: float = 0.0, exif=None) -> None:
        to_image = camera(yaw_deg=yaw, pitch_deg=20.0)
        image = board_image(to_image)
        image.save(self.day / f"{uuid}.jpg", "JPEG", quality=90, **({"exif": exif} if exif else {}))
        self.truths[uuid] = (to_image, [])
        kept_at = (START + dt.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
        record = {"versionName": "0.2.0", "versionCode": 200, "keptAt": kept_at, "photo": f"{uuid}.jpg",
                  "width": SIZE[0], "height": SIZE[1], "boardFound": found, "toBoard": None, "crop": None,
                  "total": 0, "darts": list(darts), "removed": []}
        (self.day / f"{uuid}.json").write_text(json.dumps(record, indent=4), encoding="utf-8")


class MountedSessionTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.captures = PhoneCaptures(self.td)

    def tearDown(self):
        self.td.cleanup()

    def build(self, name="s20", **window):
        return build_mounted(self.data, name, DAY, MOUNT, Light.DAY, "Redmi Note 8 Pro", **window)

    def test_one_photo_per_visit_in_the_order_kept_whatever_the_file_names(self):
        for uuid, minutes, yaw in (("a", 2, 10.0), ("b", 0, 20.0), ("c", 1, 30.0)):
            self.captures.keep(uuid, minutes, yaw=yaw)
        built = self.build()
        self.assertEqual(list(map(str, built.photos)), ["s20-v01-p1", "s20-v02-p1", "s20-v03-p1"])
        for photo, uuid in zip(built.photos, "bca", strict=True):
            self.assertEqual(self.data.photo("s20", str(photo)).read_bytes(),
                             (self.captures.day / f"{uuid}.jpg").read_bytes(), "a byte copy, in keptAt order")
        self.assertEqual(sorted(p.name for p in self.data.photos("s20").iterdir()),
                         ["s20-v01-p1.jpg", "s20-v02-p1.jpg", "s20-v03-p1.jpg"])

    def test_the_sheet_is_a_gate_session_with_its_mount_that_the_later_steps_read(self):
        self.captures.keep("a", 0)
        self.captures.keep("b", 1, darts=[thrown("T20"), *FILLED[1:]])
        self.build()
        sheet = load_sheet(self.data.sheet("s20"))
        self.assertTrue(sheet.gate)
        self.assertFalse(sheet.held_out)
        self.assertTrue(sheet.ingested, "ingest refuses a session already built")
        self.assertEqual(sheet.mount, MOUNT)
        self.assertEqual((sheet.phone, sheet.light, sheet.date), ("Redmi Note 8 Pro", Light.DAY, dt.date(2026, 11, 24)))
        self.assertEqual(list(map(str, sheet.photo_names())), ["s20-v01-p1", "s20-v02-p1"])
        self.assertEqual([[str(d.score) for d in v.darts] for v in sheet.visits], [[], ["T20"]],
                         "a Dart the app filled in to make up three was never thrown")

    def test_a_visit_where_the_app_found_no_board_is_kept_and_says_so(self):
        self.captures.keep("a", 0)
        self.captures.keep("b", 1, found=False)
        built = self.build()
        self.assertEqual(len(built.photos), 2)
        raw = tomllib.loads(self.data.sheet("s20").read_text(encoding="utf-8"))
        photos = raw["ingest"]["photos"]
        self.assertEqual({n: e["board_found"] for n, e in photos.items()}, {"s20-v01-p1": True, "s20-v02-p1": False})
        self.assertEqual(photos["s20-v02-p1"]["marked"], f"phone-captures/{DAY}/b.json")
        self.assertEqual(photos["s20-v02-p1"]["kept_at"], START + dt.timedelta(minutes=1))

    def test_a_record_from_before_filled_existed_keeps_every_dart(self):
        self.captures.keep("a", 0, darts=[{k: v for k, v in d.items() if k != "filled"} for d in FILLED])
        self.build()
        self.assertEqual(len(load_sheet(self.data.sheet("s20")).visits[0].darts), 3)

    def test_a_second_position_on_the_same_day_takes_only_the_visits_no_session_holds(self):
        self.captures.keep("a", 0)
        self.captures.keep("b", 1)
        self.build("s20")
        self.captures.keep("c", 30)
        built = self.build("s21")
        self.assertEqual(len(built.photos), 1)
        self.assertEqual(sorted(built.left_out), [("a.json", "already in s20"), ("b.json", "already in s20")])
        self.assertEqual(self.data.photo("s21", "s21-v01-p1").read_bytes(), (self.captures.day / "c.jpg").read_bytes())

    def test_a_window_of_keptat_splits_a_day_between_positions(self):
        for uuid, minutes in (("a", 0), ("b", 10), ("c", 20)):
            self.captures.keep(uuid, minutes)
        built = self.build(kept_from=START + dt.timedelta(minutes=5), kept_until=START + dt.timedelta(minutes=20))
        self.assertEqual(len(built.photos), 1)
        self.assertEqual([name for name, _ in built.left_out], ["a.json", "c.json"])

    def test_nothing_is_built_from_a_record_it_cannot_read_or_a_photo_with_metadata(self):
        exif = Image.Exif()
        exif[0x0110] = "TestPhone"
        self.captures.keep("a", 0)
        self.captures.keep("b", 1, exif=exif)
        (self.captures.day / "c.json").write_text("{", encoding="utf-8")
        with self.assertRaises(MountedError) as refused:
            self.build()
        self.assertIn("b.json", str(refused.exception))
        self.assertIn("carries APP1", str(refused.exception))
        self.assertIn("c.json", str(refused.exception))
        self.assertFalse(self.data.sheet("s20").exists())
        self.assertFalse(self.data.photos("s20").exists())

    def test_it_never_overwrites_a_session(self):
        self.captures.keep("a", 0)
        self.build()
        with self.assertRaisesRegex(MountedError, "already exists"):
            self.build()

    def test_the_command_builds_and_names_the_next_steps(self):
        self.captures.keep("a", 0)
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DARTS_DATA": str(self.data.root)}), contextlib.redirect_stdout(out):
            code = main(["mounted-session", "s20", "--day", DAY, "--height-cm", "160", "--distance-cm", "75",
                         "--angle-deg", "30", "--light", "day", "--phone", "Redmi Note 8 Pro"])
        self.assertEqual(code, 0)
        self.assertIn("1 Photos, one per Visit", out.getvalue())
        self.assertEqual(load_sheet(self.data.sheet("s20")).mount, MOUNT)


class MountedLoopTest(unittest.TestCase):
    """label, prefill, review and check read the built sheet, and evaluate reads it outside the Held-out set."""

    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        captures = PhoneCaptures(self.td)
        for uuid, minutes, yaw in (("b", 1, 15.0), ("a", 0, -15.0), ("c", 2, 0.0)):
            captures.keep(uuid, minutes, yaw=yaw, found=uuid != "c")
        built = build_mounted(self.data, "s20", DAY, MOUNT, Light.DAY, "Redmi Note 8 Pro")
        order = {"a": 0, "b": 1, "c": 2}
        truths = {str(built.photos[order[uuid]]): truth for uuid, truth in captures.truths.items()}
        quiet = {"say": lambda *_: None}
        label(self.data, "s20", window=pass_one_window(truths), **quiet)
        prefill(self.data, "s20")
        review(self.data, "s20", window=idle_window(), ask=lambda _: "y", today=dt.date(2026, 11, 25), **quiet)

    def tearDown(self):
        self.td.cleanup()

    def test_check_is_clean_on_one_photo_per_visit(self):
        report_ = check(self.data, "s20")
        self.assertEqual(report_.findings, [])

    def test_evaluate_reads_the_session_outside_the_held_out_set(self):
        result = evaluate(self.data, "labels", sessions=("s20",))
        self.assertEqual(result.found, Share(3, 3))
        self.assertEqual(result.treble.count, 3 * 40)
        self.assertLess(result.treble.p95_mm, 1e-6)
        self.assertLess(result.double.p95_mm, 1e-6)
        self.assertEqual((result.b2_p2, result.b2_p3), (Share(0, 0), Share(0, 0)))
        self.assertTrue(result.board_met)
        self.assertIn("s20, outside the Held-out set: 1 Capture sessions, 3 Photos, 3 Visits, each clean in `check`",
                      report(result)[0])

    def test_the_command_reads_a_session_through_session(self):
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DARTS_DATA": str(self.data.root)}), contextlib.redirect_stdout(out):
            main(["evaluate", "--predictions", "labels", "--session", "s20"])
        self.assertIn("Board found              3/3 (100.0%)", out.getvalue())

    def test_a_session_unclean_in_check_or_held_out_is_not_read_by_session(self):
        (self.data.labels("s20") / "s20-v02-p1.json").unlink()
        with self.assertRaisesRegex(HeldOutError, "not clean on s20"):
            evaluate(self.data, "labels", sessions=("s20",))
        sheet = self.data.sheet("s20")
        sheet.write_text(sheet.read_text(encoding="utf-8").replace('set = "gate"', 'set = "held-out"'), encoding="utf-8")
        with self.assertRaisesRegex(HeldOutError, "s20 is held-out"):
            evaluate(self.data, "labels", sessions=("s20",))

    def test_build_leaves_a_gate_session_out_of_the_training_records(self):
        built = build(self.data, HeldOutSet({}, {}))
        self.assertEqual(built.records, 0)
        self.assertEqual(len(built.skipped), 3)
        self.assertTrue(all("gate" in reason for _, reason in built.skipped))


if __name__ == "__main__":
    unittest.main()
