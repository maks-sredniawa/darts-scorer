import contextlib
import dataclasses
import io
import json
import unittest
from unittest import mock

import numpy as np
import torch

from darts_ml.cli import main
from darts_ml.evaluate import PredictedEntry, evaluate
from darts_ml.heldout import file_sha256, freeze
from darts_ml.labelme import label_path, read_label
from darts_ml.locate import Located
from darts_ml.model import KeypointNet
from darts_ml.predict import predict, write_predictions
from darts_ml.train import RunConfig
from synthetic import TemporaryData, reviewed_session

VISITS = [["T20", "T20", "S1"], ["S5", "T5", "S20"], ["D3", "S19", "out"]]
RUN = "2026-11-17-board"


class PredictTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.manifest = self.data.root / "splits" / "held-out.toml"
        reviewed_session(self.td, "s04", VISITS, held_out=True)
        self.held = freeze(self.data)
        self.held.save(self.manifest)

    def tearDown(self):
        self.td.cleanup()

    def test_the_labels_written_as_predictions_read_perfect_and_name_their_run(self):
        located = {}
        for photo in self.held.photo_names():
            label = read_label(label_path(self.data.labels(photo.capture_session), str(photo)))
            located[str(photo)] = Located(np.eye(3), dict(label.calibration),
                                          tuple(PredictedEntry(s.x, s.y) for s in label.entries))
        path = self.data.runs() / RUN / "predictions.json"
        write_predictions(path, RUN, "ab" * 32, located)
        result = evaluate(self.data, path, self.manifest)
        self.assertEqual(result.found.hits, result.found.total)
        self.assertEqual(result.found.total, len(self.held.photos))
        self.assertLess(result.treble.p95_mm, 1e-9)
        self.assertLess(result.double.p95_mm, 1e-9)
        self.assertEqual(result.b2.hits, result.b2.total)
        written = json.loads(path.read_text())
        self.assertEqual((written["run"], written["weights_sha256"]), (RUN, "ab" * 32))
        with self.assertRaises(FileExistsError):
            write_predictions(path, RUN, "ab" * 32, located)

    def test_predict_covers_every_held_out_photo_and_records_the_run_and_its_weights(self):
        folder = self.data.runs() / RUN
        folder.mkdir(parents=True)
        config = dataclasses.asdict(RunConfig("board", device="cpu", size=64, batch=4))
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        torch.manual_seed(0)
        torch.save({"model": KeypointNet().state_dict(), "epoch": 1}, folder / "best.pt")
        path = predict(self.data, RUN, device="cpu", manifest=self.manifest, workers=0)
        written = json.loads(path.read_text())
        self.assertEqual(path.parent, folder)
        self.assertEqual(written["run"], RUN)
        self.assertEqual(written["weights_sha256"], file_sha256(folder / "best.pt"))
        self.assertEqual(set(written["photos"]), set(self.held.photos))
        self.assertTrue(evaluate(self.data, path, self.manifest).found.total)

    def test_predict_reads_a_gate_session_when_named(self):
        reviewed_session(self.td, "s05", VISITS)
        sheet = self.data.sheet("s05")
        sheet.write_text(sheet.read_text(encoding="utf-8").replace('set = "training"', 'set = "gate"'), encoding="utf-8")
        folder = self.data.runs() / RUN
        folder.mkdir(parents=True)
        config = dataclasses.asdict(RunConfig("board", device="cpu", size=64, batch=4))
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        torch.manual_seed(0)
        torch.save({"model": KeypointNet().state_dict(), "epoch": 1}, folder / "best.pt")
        path = predict(self.data, RUN, device="cpu", workers=0, sessions=("s05",))
        self.assertTrue(path.name.startswith("predictions-s05-best-"))
        written = json.loads(path.read_text())
        self.assertEqual(set(written["photos"]), {f"s05-v{v:02d}-p{a}" for v in (1, 2, 3) for a in (1, 2, 3)})
        self.assertEqual(evaluate(self.data, path, sessions=("s05",)).found.total, 9)

    def test_a_missing_run_is_named_not_a_traceback(self):
        for argv in (["predict", "--run", "nope"], ["deepdarts", "score", "--run", "nope"]):
            err = io.StringIO()
            with mock.patch.dict("os.environ", {"DARTS_DATA": str(self.data.root)}), contextlib.redirect_stderr(err):
                code = main(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(f"no run at {self.data.runs() / 'nope'}", err.getvalue())

    def test_an_entry_threshold_outside_zero_to_one_is_refused(self):
        for value in ("0", "1", "1.5", "-0.1"):
            with self.subTest(value), contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
                main(["deepdarts", "score", "--run", "nope", "--entry-threshold", value])
            self.assertIn("is not between 0 and 1", err.getvalue())


if __name__ == "__main__":
    unittest.main()
