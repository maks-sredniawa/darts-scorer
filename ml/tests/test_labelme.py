import unittest
from pathlib import Path

from darts_ml.labelme import LABELS, PINNED, PYTHON, RESOLVED_AS_OF, label, offline_environment, window_command
from darts_ml.manifest import ReviewManifest
from darts_ml.paths import Round
from synthetic import TemporaryData, idle_window, pass_one_window, session


class LabelmeTest(unittest.TestCase):
    def test_the_window_is_the_pinned_labelme_with_its_safeguards(self):
        command = window_command("/data/photos/s01/s01-v01-p1.jpg", "/data/labels/s01")
        self.assertEqual(
            command[:8], ["uvx", "--python", PYTHON, "--exclude-newer", RESOLVED_AS_OF, "--from", f"labelme=={PINNED}", "labelme"]
        )
        options = {flag: command[command.index(flag) + 1] for flag in ("--output", "--validate-label", "--labels", "--config", "--label-flags")}
        self.assertEqual(options["--output"], "/data/labels/s01")
        self.assertEqual(options["--validate-label"], "exact")
        self.assertEqual(options["--labels"].split(","), list(LABELS))
        self.assertIn("with_image_data: false", options["--config"])
        self.assertIn("entry", options["--label-flags"])
        self.assertIn("inferred", options["--label-flags"])
        self.assertEqual(len(LABELS), 81)

    def test_labelme_runs_on_the_python_ml_is_pinned_to(self):
        self.assertEqual(PYTHON, (Path(__file__).resolve().parents[1] / ".python-version").read_text().strip())

    def test_the_window_runs_offline(self):
        env = offline_environment({"PATH": "/usr/bin", "NO_PROXY": "*"})
        self.assertEqual(env["UV_OFFLINE"], "1")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "https_proxy"):
            self.assertEqual(env[name], "http://127.0.0.1:9")
        self.assertEqual(env["NO_PROXY"], "")


class LabelTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.truths = session(self.td, "s01", [["T20", "T20", "S1"]])

    def tearDown(self):
        self.td.cleanup()

    def test_label_opens_each_unlabelled_photo_once_and_times_it(self):
        said = []
        self.assertEqual(label(self.data, "s01", window=pass_one_window(self.truths), say=said.append), 3)
        self.assertEqual(label(self.data, "s01", window=pass_one_window(self.truths), say=said.append), 0)
        manifest = ReviewManifest.load(self.data.labels("s01"))
        self.assertEqual({p: r.label_seconds for p, r in manifest.photos.items()},
                         {f"s01-v01-p{a}": 60.0 for a in (1, 2, 3)})
        self.assertIn("Hand points", said[0])

    def test_a_window_closed_without_saving_is_not_counted(self):
        said = []
        label(self.data, "s01", window=idle_window(), say=said.append)
        self.assertEqual(ReviewManifest.load(self.data.labels("s01")).photos, {})
        self.assertEqual(sum("no label was saved" in line for line in said), 3)

    def test_repeat_rounds_label_into_their_own_directory(self):
        label(self.data, "s01", Round.B, window=pass_one_window(self.truths), say=lambda _: None)
        self.assertEqual(len(list((self.data.root / "rounds" / "s01" / "b").glob("*.json"))), 3)
        self.assertFalse(self.data.labels("s01").exists() and any(self.data.labels("s01").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
