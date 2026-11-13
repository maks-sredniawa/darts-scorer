import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from darts_ml import DartsMlError
from darts_ml.paths import DataDir, DataInsideRepo, Round, data_root, repo_roots

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

    def test_a_symlinked_folder_under_the_data_directory_is_refused(self):
        for link_at in ("photos", "labels", "rounds", "overlays", "capture-sessions", "inbox"):
            with self.subTest(link_at), tempfile.TemporaryDirectory() as outside:
                os.symlink(REPO / "ml", Path(outside) / link_at)
                data = DataDir(data_root({"DARTS_DATA": outside}))
                writes = {
                    "photos": lambda: data.photo("s01", "s01-v01-p1"),
                    "labels": lambda: data.labels("s01"),
                    "rounds": lambda: data.labels("s01", Round.B),
                    "overlays": lambda: data.overlays("s01", Round.C),
                    "capture-sessions": lambda: data.sheet("s01"),
                    "inbox": lambda: data.inbox("s01"),
                }
                with self.assertRaises(DataInsideRepo) as caught:
                    writes[link_at]()
                self.assertIn("under DARTS_DATA", str(caught.exception))

    def test_a_symlinked_capture_session_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "labels").mkdir()
            os.symlink(REPO / "ml", Path(outside) / "labels" / "s02")
            data = DataDir(data_root({"DARTS_DATA": outside}))
            self.assertEqual(data.labels("s01"), Path(outside).resolve() / "labels" / "s01")
            with self.assertRaises(DataInsideRepo):
                data.labels("s02")

    @unittest.skipIf(shutil.which("git") is None, "needs git")
    def test_sibling_worktrees_are_fenced_from_either_side(self):
        with tempfile.TemporaryDirectory() as outside:
            main, sibling = Path(outside).resolve() / "clone", Path(outside).resolve() / "clone-pr-1"
            main.mkdir()
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
            for command in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"], ["worktree", "add", "-q", str(sibling)]):
                subprocess.run([*git, "-C", str(main), *command], check=True, capture_output=True)
            for start in (main / "ml", sibling / "ml"):
                with self.subTest(str(start)):
                    roots = repo_roots([start])
                    self.assertEqual(roots, {main, sibling})
                    for inside in (main / "data", sibling / "data"):
                        with self.assertRaises(DataInsideRepo):
                            data_root({"DARTS_DATA": str(inside)}, roots)

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
