import contextlib
import dataclasses
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import torch

from darts_ml import DartsMlError
from darts_ml.cli import main
from darts_ml.evaluate import PredictedEntry
from darts_ml.export import PARITY_MM, export, exported_path, parity, runtime
from darts_ml.export_format import Format
from darts_ml.locate import Located
from darts_ml.model import ENTRY_STRIDES, KeypointNet
from darts_ml.train import RunConfig
from synthetic import TemporaryData

SIZE = 64
RUN = "2026-11-19-tiny"
ONNX = all(importlib.util.find_spec(m) for m in ("onnx", "onnxscript", "onnxruntime"))
LITERT = all(importlib.util.find_spec(m) for m in ("litert_torch", "ai_edge_litert"))


def _model(stride: int) -> KeypointNet:
    torch.manual_seed(stride)
    model = KeypointNet(stride)
    for module in model.modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.running_mean.uniform_(-0.5, 0.5)
            module.running_var.uniform_(0.5, 1.5)
    return model.eval()


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="darts-ml-export-")
        self.folder = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def _round_trip(self, format_: Format, tolerance: float):
        for stride in ENTRY_STRIDES:
            with self.subTest(stride=stride):
                model = _model(stride)
                path = self.folder / f"{stride}{format_.suffix}"
                exported = export(model, SIZE, format_, path)
                self.assertEqual(exported.size_bytes, path.stat().st_size)
                self.assertEqual(exported.outside, [])
                self.assertTrue(exported.operations)
                images = torch.randn(2, 3, SIZE, SIZE)
                with torch.no_grad():
                    expected = model(images)
                got = runtime(format_, path, threads=1)(images)
                for name, want, have in zip(("board", "entry"), expected, got, strict=True):
                    self.assertEqual(have.shape, want.shape, name)
                    self.assertLess(float((have - want).abs().max()), tolerance, name)

    @unittest.skipUnless(ONNX, "needs --extra export")
    def test_onnx_runtime_gives_pytorch_heads_for_both_entry_layouts_in_one_file(self):
        self._round_trip(Format.ONNX, 1e-4)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["2.onnx", "4.onnx"])

    @unittest.skipUnless(LITERT, "needs --extra litert --extra export")
    def test_litert_interpreter_gives_pytorch_heads_for_both_entry_layouts(self):
        self._round_trip(Format.LITERT, 1e-4)

    @unittest.skipIf(importlib.util.find_spec("litert_torch"), "the LiteRT converter is installed")
    def test_litert_without_its_converter_names_the_extra(self):
        with self.assertRaisesRegex(DartsMlError, "--extra litert"):
            export(_model(2), SIZE, Format.LITERT, self.folder / "best.tflite")


class ParityTest(unittest.TestCase):
    TO_BOARD = np.diag([0.5, 0.5, 1.0])

    def located(self, nudge: float = 0.0, entries=((300.0, 100.0),)) -> Located:
        return Located(self.TO_BOARD, {"a": (100.0 + nudge, 100.0), "b": (200.0, 100.0)},
                       tuple(PredictedEntry(x, y, confidence=0.9) for x, y in entries))

    def test_the_same_points_read_the_same(self):
        reading = parity([self.located()], [self.located()])
        self.assertTrue(reading.same)
        self.assertEqual((len(reading.calibration.values), len(reading.entries.values)), (2, 1))
        self.assertEqual(max(reading.calibration.values), 0.0)

    def test_a_point_moved_past_the_limit_is_counted_in_board_millimetres(self):
        reading = parity([self.located()], [self.located(nudge=4 * PARITY_MM)])
        self.assertEqual(reading.calibration.over, 1)
        self.assertAlmostEqual(max(reading.calibration.values), 2 * PARITY_MM)
        self.assertFalse(reading.same)

    def test_a_lost_dart_changes_the_visit_and_a_lost_board_is_named(self):
        reading = parity([self.located(), self.located()], [self.located(entries=()), Located(None)])
        self.assertEqual((reading.unmatched, reading.visits_differ, reading.boards_differ), (1, 2, 1))


class ExportCliTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.folder = self.td.data.runs() / RUN

    def tearDown(self):
        self.td.cleanup()

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.dict("os.environ", {"DARTS_DATA": str(self.td.data.root)}),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def write_run(self, seed: int) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        config = dataclasses.asdict(RunConfig("tiny", device="cpu", size=SIZE, batch=2))
        (self.folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
        torch.manual_seed(seed)
        torch.save({"model": KeypointNet().state_dict(), "epoch": 1}, self.folder / "best.pt")

    def test_a_missing_run_is_named_not_a_traceback(self):
        for step in ("export", "export-parity"):
            code, _, err = self.run_cli(step, "--run", "nope", "--format", "onnx")
            self.assertEqual(code, 2, step)
            self.assertIn(f"no run at {self.td.data.runs() / 'nope'}", err)

    def test_parity_refuses_a_run_never_exported(self):
        self.write_run(0)
        code, _, err = self.run_cli("export-parity", "--run", RUN, "--format", "onnx")
        self.assertEqual(code, 2)
        self.assertIn("no exported model", err)

    @unittest.skipUnless(ONNX, "needs --extra export")
    def test_export_writes_into_the_run_and_parity_refuses_weights_changed_since(self):
        self.write_run(0)
        code, out, _ = self.run_cli("export", "--run", RUN, "--format", "onnx")
        path = exported_path(self.folder, "best", Format.ONNX)
        self.assertEqual(code, 0)
        self.assertIn(f"{path}: {path.stat().st_size} bytes", out)
        self.assertIn("left outside onnx's own operations: none", out)
        self.write_run(1)
        code, _, err = self.run_cli("export-parity", "--run", RUN, "--format", "onnx")
        self.assertEqual(code, 2)
        self.assertIn("export it again", err)


if __name__ == "__main__":
    unittest.main()
