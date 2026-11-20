"""python3 -m unittest discover -s scripts"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("pull_marked", Path(__file__).with_name("pull-marked.py"))
pull_marked = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pull_marked)


class Listing(unittest.TestCase):
    def test_only_whole_photos_and_records_are_taken(self):
        listing = "b.json\na.jpg\na.json\nb.jpg.part\nc.json.part\n"
        self.assertEqual(pull_marked.marked_names(listing), ["a.jpg", "a.json", "b.json"])

    def test_a_file_pulled_on_any_earlier_date_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            captures = Path(tmp)
            (captures / "2026-11-19").mkdir()
            (captures / "2026-11-19" / "a.jpg").write_bytes(b"x")
            pulled = pull_marked.already_pulled(captures)
            self.assertEqual(pull_marked.to_pull(["a.jpg", "a.json"], pulled), ["a.json"])

    def test_no_captures_folder_means_nothing_pulled(self):
        self.assertEqual(pull_marked.already_pulled(Path("/nonexistent/phone-captures")), set())


class DataRoot(unittest.TestCase):
    def test_a_path_inside_the_repo_is_refused(self):
        root = Path(__file__).resolve().parent.parent
        with self.assertRaises(SystemExit):
            pull_marked.data_root({"DARTS_DATA": str(root / "data")}, {root})

    def test_the_default_is_outside_the_repo(self):
        self.assertEqual(pull_marked.data_root({}, set()), Path("~/darts-scorer-data").expanduser().resolve())


if __name__ == "__main__":
    unittest.main()
