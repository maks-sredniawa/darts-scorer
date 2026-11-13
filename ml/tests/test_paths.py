import os
import tempfile
import unittest
from pathlib import Path

from darts_ml import DartsMlError
from darts_ml.paths import DataDir, DataInsideRepo, data_root, repo_roots

REPO = Path(__file__).resolve().parents[2]


class PathsTest(unittest.TestCase):
    def test_the_repository_is_found(self):
        self.assertIn(REPO, repo_roots())

    def test_a_data_directory_inside_the_repo_is_refused(self):
        for inside in (REPO, REPO / "ml", REPO / "ml" / "data-that-does-not-exist"):
            with self.subTest(str(inside)), self.assertRaises(DataInsideRepo) as caught:
                data_root({"DARTS_DATA": str(inside)})
            self.assertIn("never enter git", str(caught.exception))

    def test_a_symlink_into_the_repo_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            link = Path(outside) / "data"
            os.symlink(REPO / "ml", link)
            with self.assertRaises(DataInsideRepo):
                data_root({"DARTS_DATA": str(link)})
            with self.assertRaises(DataInsideRepo):
                data_root({"DARTS_DATA": str(link / "photos")})

    def test_a_directory_outside_is_accepted(self):
        with tempfile.TemporaryDirectory() as outside:
            self.assertEqual(data_root({"DARTS_DATA": outside}), Path(outside).resolve())

    def test_capture_session_names_cannot_escape(self):
        data = DataDir(Path("/nowhere"))
        for bad in ("../s01", "s1", "s01/..", "x01", ""):
            with self.subTest(bad), self.assertRaises(DartsMlError):
                data.photos(bad)


if __name__ == "__main__":
    unittest.main()
