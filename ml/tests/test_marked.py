import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from darts_ml import DartsMlError
from darts_ml.cli import main
from darts_ml.marked import Phone, Remote, parse_listing, pull, to_copy

REPO = Path(__file__).resolve().parents[2]


class FakeAdb:
    """The app's `files/marked/` as name -> (bytes, mtime), answering the commands `Phone` sends."""

    def __init__(self, files: dict[str, tuple[bytes, int]]) -> None:
        self.files = dict(files)
        self.deleted: list[str] = []

    def __call__(self, command, capture_output):
        args = command[3:]
        if args[0] == "shell" and " sh -c " in args[1]:
            out = "".join(f"{name} {len(data)} {mtime}\n" for name, (data, mtime) in self.files.items())
            return subprocess.CompletedProcess(command, 0, out.encode(), b"")
        if args[0] == "exec-out":
            return subprocess.CompletedProcess(command, 0, self.files[args[-1].split("/")[-1]][0], b"")
        if args[0] == "shell" and " rm " in args[1]:
            name = args[1].split("/")[-1]
            self.deleted.append(name)
            del self.files[name]
            return subprocess.CompletedProcess(command, 0, b"", b"")
        raise AssertionError(command)


def run_pull(captures: Path, adb: FakeAdb, day: str, delete_after: bool = False) -> int:
    return pull(Phone("emulator-5600", run=adb), captures, day, lambda line: None, delete_after)


class ListingTest(unittest.TestCase):
    def test_only_whole_photos_and_records_are_taken(self):
        listing = "b.json 9 100\na.jpg 4 100\nb.jpg.1f.part 3 100\nstat: bad\na.json 2 101\n"
        self.assertEqual([r.name for r in parse_listing(listing)], ["a.jpg", "a.json", "b.json"])
        self.assertEqual(parse_listing(listing)[1], Remote("a.json", 2, 101))

    def test_a_record_already_here_goes_back_where_it_lies(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "2026-11-19" / "a.json"
            old.parent.mkdir()
            old.write_bytes(b"{}")
            os.utime(old, (100, 100))
            todo = to_copy([Remote("a.json", 2, 100), Remote("a.json", 2, 105), Remote("b.json", 2, 100)],
                           {"a.json": old}, Path(tmp) / "2026-11-20")
            self.assertEqual([(r.mtime, p) for r, p in todo],
                             [(105, old), (100, Path(tmp) / "2026-11-20" / "b.json")])


class PullTest(unittest.TestCase):
    def test_a_record_kept_again_is_copied_again_and_the_rest_skipped(self):
        adb = FakeAdb({"u1.jpg": (b"jpeg", 100), "u1.json": (b'{"total": 60}', 100)})
        with tempfile.TemporaryDirectory() as tmp:
            captures = Path(tmp)
            self.assertEqual(run_pull(captures, adb, "2026-11-19"), 2)
            self.assertEqual(run_pull(captures, adb, "2026-11-19"), 0)
            adb.files["u1.json"] = (b'{"total": 45}', 160)
            self.assertEqual(run_pull(captures, adb, "2026-11-20"), 1)
            self.assertEqual((captures / "2026-11-19" / "u1.json").read_bytes(), b'{"total": 45}')
            self.assertFalse((captures / "2026-11-20").exists())
            self.assertEqual(sorted(p.name for p in captures.rglob("*")), ["2026-11-19", "u1.jpg", "u1.json"])

    def test_delete_after_removes_only_what_is_here_unchanged(self):
        adb = FakeAdb({"u1.jpg": (b"jpeg", 100), "u1.json": (b"{}", 100)})
        with tempfile.TemporaryDirectory() as tmp:
            run_pull(Path(tmp), adb, "2026-11-20", delete_after=True)
        self.assertEqual(sorted(adb.deleted), ["u1.jpg", "u1.json"])
        self.assertEqual(adb.files, {})

    def test_a_short_read_is_refused(self):
        adb = FakeAdb({"u1.jpg": (b"jpeg", 100)})
        listing = adb.__call__

        def short(command, capture_output):
            done = listing(command, capture_output)
            return subprocess.CompletedProcess(command, 0, done.stdout[:2], b"") if command[3] == "exec-out" else done

        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(DartsMlError):
            pull(Phone("emulator-5600", run=short), Path(tmp), "2026-11-20", lambda line: None)

    def test_a_phone_that_refuses_run_as_says_so(self):
        def refused(command, capture_output):
            return subprocess.CompletedProcess(command, 0, b"run-as: package not debuggable: x\n", b"")

        with self.assertRaises(DartsMlError):
            Phone("emulator-5600", run=refused).listing()


class StepTest(unittest.TestCase):
    def test_the_step_refuses_darts_data_inside_the_repo(self):
        with mock.patch.dict(os.environ, {"DARTS_DATA": str(REPO / "ml" / "phone-data")}):
            self.assertEqual(main(["pull-marked", "--serial", "emulator-5600"]), 2)

    def test_the_step_needs_a_serial(self):
        with self.assertRaises(SystemExit):
            main(["pull-marked"])


if __name__ == "__main__":
    unittest.main()
