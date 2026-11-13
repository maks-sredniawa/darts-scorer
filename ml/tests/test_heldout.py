import contextlib
import io
import json
import shutil
import unittest
from unittest import mock

from darts_ml.board import HAND_POINTS
from darts_ml.cli import main
from darts_ml.heldout import HeldOutError, HeldOutSet, freeze, verify
from darts_ml.labelme import read_label, write_label
from darts_ml.manifest import Review, ReviewManifest
from darts_ml.records import RECORDS, build
from darts_ml.review import label_sha256
from synthetic import REVIEW_DAYS, SIZE, TemporaryData, reviewed_session, sheet_text

TRAINING = [["T20", "T20", "S1"], ["D3", "S19", "out"]]
HELD_OUT = [["S5", "T5", "S20"], ["25", "T19", "S7"]]


def flip_a_byte(path):
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))


class HeldOutTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        reviewed_session(self.td, "s01", TRAINING)
        reviewed_session(self.td, "s04", HELD_OUT, held_out=True)
        self.manifest = self.data.root / "splits" / "held-out.toml"
        freeze(self.data).save(self.manifest)
        self.held = HeldOutSet.load(self.manifest)

    def tearDown(self):
        self.td.cleanup()

    def refused(self):
        return dict(build(self.data, HeldOutSet.load(self.manifest)).refused)

    def test_the_freeze_holds_every_held_out_photo_and_nothing_else(self):
        self.assertEqual(set(self.held.capture_sessions), {"s04"})
        self.assertEqual(sorted(self.held.photos), [f"s04-v0{v}-p{a}" for v in (1, 2) for a in (1, 2, 3)])
        self.assertEqual(verify(self.data, self.held), [])

    def test_the_freeze_refuses_a_held_out_capture_session_check_does_not_pass(self):
        path = self.data.labels("s04") / "s04-v01-p1.json"
        label = read_label(path)
        write_label(path, label.photo_path(), SIZE[0], SIZE[1], label.shapes[1:])
        with self.assertRaisesRegex(HeldOutError, "not clean on s04"):
            freeze(self.data)

    def test_verify_fails_on_one_changed_byte_in_each_frozen_file(self):
        frozen = {
            "s04-v02-p3 Photo": self.data.photo("s04", "s04-v02-p3"),
            "s04-v02-p3 label": self.data.labels("s04") / "s04-v02-p3.json",
            "s04 sheet": self.data.sheet("s04"),
            "s04 review manifest": self.data.labels("s04") / "review.toml",
        }
        for what, path in frozen.items():
            with self.subTest(what):
                original = path.read_bytes()
                flip_a_byte(path)
                problems = verify(self.data, self.held)
                path.write_bytes(original)
                self.assertEqual(len(problems), 1)
                self.assertTrue(problems[0].startswith(f"{what}: changed since the freeze"))
        self.assertEqual(verify(self.data, self.held), [])

    def test_verify_fails_on_a_missing_file(self):
        self.data.photo("s04", "s04-v01-p2").unlink()
        self.assertEqual(len(verify(self.data, self.held)), 1)
        self.assertIn("s04-v01-p2 Photo: missing", verify(self.data, self.held)[0])

    def test_verify_fails_on_a_held_out_sheet_the_manifest_does_not_freeze(self):
        reviewed_session(self.td, "s07", [["S1", "S1", "S1"]], held_out=True)
        self.assertEqual(verify(self.data, self.held), ["s07: its sheet says held-out, and the manifest does not freeze it"])

    def without(self, *photos):
        return HeldOutSet(self.held.capture_sessions, {n: p for n, p in self.held.photos.items() if n not in photos})

    def test_verify_fails_on_a_manifest_missing_a_photo_its_frozen_sheet_lists(self):
        for removed in (["s04-v02-p2"], [f"s04-v01-p{a}" for a in (1, 2, 3)]):
            with self.subTest(removed=removed):
                self.assertEqual(
                    verify(self.data, self.without(*removed)),
                    [f"{photo}: in the s04 sheet, and the manifest does not freeze it" for photo in removed],
                )

    def test_load_refuses_a_photo_of_a_capture_session_the_manifest_does_not_freeze(self):
        stray = {**self.held.photos, "s01-v01-p1": self.held.photos["s04-v01-p1"]}
        HeldOutSet(self.held.capture_sessions, stray).save(self.manifest)
        with self.assertRaisesRegex(HeldOutError, "Photos of Capture sessions the manifest does not freeze: s01-v01-p1$"):
            HeldOutSet.load(self.manifest)

    def test_the_builder_writes_training_photos_and_refuses_a_held_out_capture_session(self):
        built = build(self.data, self.held)
        self.assertEqual(built.records, 6)
        self.assertEqual(len(built.refused), 6)
        self.assertTrue(all(name.startswith("s04-") for name, _ in built.refused))
        records = [json.loads(line) for line in (self.data.build() / RECORDS).read_text().splitlines()]
        self.assertEqual({r["capture_session"] for r in records}, {"s01"})
        self.assertEqual(records[0]["photo"], "photos/s01/s01-v01-p1.jpg")
        self.assertEqual(records[0]["scores"], ["T20", "T20", "S1"])
        self.assertEqual(len(records[0]["calibration"]), len(read_label(self.data.labels("s01") / "s01-v01-p1.json").calibration))

    def test_a_record_marks_its_hand_points_hand_and_every_other_crossing_checked(self):
        manifest = ReviewManifest.load(self.data.labels("s01"))
        label = read_label(self.data.labels("s01") / "s01-v01-p1.json")
        manifest.record("s01-v01-p1").hand_points = {name: label.calibration[name] for name in HAND_POINTS}
        manifest.save()
        build(self.data, self.held)
        records = {r["photo"]: r for r in map(json.loads, (self.data.build() / RECORDS).read_text().splitlines())}
        sources = {c["name"]: c["source"] for c in records["photos/s01/s01-v01-p1.jpg"]["calibration"]}
        self.assertEqual({name for name, source in sources.items() if source == "hand"}, set(HAND_POINTS))
        self.assertEqual(set(sources.values()), {"hand", "checked"})
        hand_throughout = records["photos/s01/s01-v01-p2.jpg"]["calibration"]
        self.assertEqual({c["source"] for c in hand_throughout}, {"hand"})

    def test_the_builder_refuses_a_frozen_capture_session_by_name_even_when_its_sheet_says_training(self):
        self.data.sheet("s04").write_text(sheet_text(HELD_OUT, held_out=False), encoding="utf-8")
        refused = self.refused()
        self.assertEqual(len(refused), 6)
        self.assertEqual(refused["s04-v01-p1"], "s04 is a held-out Capture session")

    def test_the_builder_refuses_a_capture_session_whose_sheet_says_held_out_before_it_is_frozen(self):
        reviewed_session(self.td, "s07", [["S1", "S1", "S1"]], held_out=True)
        refused = self.refused()
        self.assertEqual(refused["s07-v01-p2"], "its sheet says s07 is held-out")

    def test_the_builder_refuses_a_held_out_photo_by_its_bytes_under_a_training_name(self):
        shutil.copyfile(self.data.photo("s04", "s04-v02-p1"), self.data.photo("s01", "s01-v01-p1"))
        refused = self.refused()
        self.assertEqual(refused["s01-v01-p1"], "its bytes are a held-out Photo's")
        self.assertNotIn("s01-v01-p2", refused)

    def test_the_builder_refuses_a_held_out_label_by_its_bytes_under_a_training_name(self):
        target = self.data.labels("s01") / "s01-v02-p3.json"
        shutil.copyfile(self.data.labels("s04") / "s04-v01-p1.json", target)
        manifest = ReviewManifest.load(self.data.labels("s01"))
        manifest.record("s01-v02-p3").reviews = [Review(day, label_sha256(target)) for day in REVIEW_DAYS]
        manifest.save()
        refused = self.refused()
        self.assertEqual(refused["s01-v02-p3"], "its label's bytes are a held-out Photo's label")

    def test_the_builder_skips_an_unreviewed_training_photo(self):
        manifest = ReviewManifest.load(self.data.labels("s01"))
        manifest.record("s01-v01-p3").reviews = []
        manifest.save()
        built = build(self.data, self.held)
        self.assertEqual(built.skipped, [("s01-v01-p3", "not reviewed")])
        self.assertEqual(built.records, 5)

    def run_cli(self, *argv):
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DARTS_DATA": str(self.data.root)}), contextlib.redirect_stdout(out):
            code = main([*argv, "--manifest", str(self.manifest)])
        return code, out.getvalue()

    def test_the_commands(self):
        self.assertEqual(self.run_cli("verify-held-out")[0], 0)
        code, out = self.run_cli("build")
        self.assertEqual(code, 0)
        self.assertIn("6 records written", out)
        self.assertIn("6 held-out Photos refused", out)
        flip_a_byte(self.data.photo("s04", "s04-v01-p1"))
        code, out = self.run_cli("verify-held-out")
        self.assertEqual(code, 1)
        self.assertIn("s04-v01-p1 Photo: changed since the freeze", out)

    def test_freeze_held_out_replaces_a_manifest_only_when_told_to(self):
        self.manifest.write_text("# stale\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_cli("freeze-held-out")[0], 2)
        self.assertIn("--replace", err.getvalue())
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), "# stale\n")
        self.assertEqual(self.run_cli("freeze-held-out", "--replace")[0], 0)
        self.assertEqual(HeldOutSet.load(self.manifest), self.held)

    def test_replace_does_not_get_round_the_clean_check(self):
        before = self.manifest.read_bytes()
        path = self.data.labels("s04") / "s04-v01-p1.json"
        label = read_label(path)
        write_label(path, label.photo_path(), SIZE[0], SIZE[1], label.shapes[1:])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_cli("freeze-held-out", "--replace")[0], 2)
        self.assertIn("not clean on s04", err.getvalue())
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_freeze_held_out_writes_a_first_manifest_without_replace(self):
        self.manifest.unlink()
        self.assertEqual(self.run_cli("freeze-held-out")[0], 0)
        self.assertEqual(HeldOutSet.load(self.manifest), self.held)

    def test_build_and_verify_refuse_to_run_without_a_frozen_manifest(self):
        self.manifest.unlink()
        for step in ("build", "verify-held-out"):
            with self.subTest(step), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_cli(step)[0], 2)
                self.assertIn("no frozen Held-out set", err.getvalue())


if __name__ == "__main__":
    unittest.main()
