import contextlib
import datetime as dt
import io
import json
import unittest
from unittest import mock

from pathlib import Path

import numpy as np
import torch

from darts_ml import DartsMlError
from darts_ml.board import CALIBRATION_BY_NAME, CALIBRATION_POINTS
from darts_ml.deepdarts import ORDER, PROJECTED, RECORDS, SOURCE, deepdarts_mm
from darts_ml.homography import project
from darts_ml.cli import main
from darts_ml.model import ENTRY_CHANNEL, HEATMAPS, OUTPUTS, STRIDE, KeypointNet
from darts_ml.heldout import FrozenPhoto, FrozenSession, HeldOutSet, file_sha256
from darts_ml.records import RECORDS as OWNER_RECORDS
from darts_ml.train import WARMUP, Probe, RunConfig, loss_terms, probe, probe_path, resolve_device, save, train
from darts_ml.training_data import (
    PROJECTED_WEIGHT,
    TRAIN,
    VALIDATION,
    KeypointDataset,
    RefusedRecord,
    Sample,
    deepdarts_reading_samples,
    deepdarts_samples,
    owner_samples,
)
from synthetic import TemporaryData, board_image, camera

SIZE = (800, 800)


class TrainingDataTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.to_image = camera(yaw_deg=10.0, pitch_deg=5.0, distance_mm=900.0, focal_px=1200.0, size=SIZE)

    def tearDown(self):
        self.td.cleanup()

    def _record(self, name: str, split: str) -> dict:
        photo = self.data.deepdarts() / "cropped_images" / "800" / "d1_x" / f"{name}.JPG"
        photo.parent.mkdir(parents=True, exist_ok=True)
        board_image(self.to_image, size=SIZE).save(photo, "JPEG", quality=90)
        four = project(self.to_image, deepdarts_mm())
        clicked = dict(zip(ORDER, four, strict=True))
        calibration = []
        for point in CALIBRATION_POINTS:
            if point.name in clicked:
                (x, y), source = clicked[point.name], SOURCE
            else:
                (x, y), source = project(self.to_image, [point.mm])[0], PROJECTED
            calibration.append({"name": point.name, "x": float(x), "y": float(y), "source": source})
        entry = project(self.to_image, [(30.0, 40.0)])[0]
        return {"split": split, "photo": photo.relative_to(self.data.root).as_posix(), "calibration": calibration,
                "entries": [{"x": float(entry[0]), "y": float(entry[1]), "inferred": False}]}

    def _write(self, *records) -> None:
        path = self.data.deepdarts() / RECORDS
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    def test_never_serves_deepdarts_test_split(self):
        self._write(self._record("a", "train"), self._record("b", "test"), self._record("c", "val"))
        self.assertEqual([s.photo.stem for s in deepdarts_samples(self.data, "train")], ["a"])
        self.assertEqual([s.photo.stem for s in deepdarts_samples(self.data, "val")], ["c"])
        with self.assertRaises(RefusedRecord):
            deepdarts_samples(self.data, "test")
        self.assertEqual([s.photo.stem for s in deepdarts_reading_samples(self.data, "test")], ["b"])

    def test_moves_deepdarts_four_to_the_crossing_centres_and_weights_the_projected(self):
        self._write(self._record("a", "train"))
        [sample] = deepdarts_samples(self.data, "train")
        by_channel = {channel: (x, y, w) for channel, x, y, w in sample.calibration}
        for index, point in enumerate(CALIBRATION_POINTS):
            x, y, weight = by_channel[index]
            np.testing.assert_allclose((x, y), project(self.to_image, [point.mm])[0], atol=1e-6)
            self.assertEqual(weight, 1.0 if point.name in ORDER else PROJECTED_WEIGHT)

    def test_a_point_lands_on_its_heatmap_peak_with_its_offset_in_its_own_kind(self):
        self._write(self._record("a", "train"))
        [sample] = deepdarts_samples(self.data, "train")
        image, heatmaps, _, calibration_offsets, calibration_mask, entry_offsets, entry_mask = \
            KeypointDataset([sample], 512)[0]
        self.assertEqual(tuple(image.shape), (3, 512, 512))
        scale = 512 / SIZE[0] / STRIDE
        for channel, x, y, _ in sample.calibration[:3]:
            cx, cy = x * scale, y * scale
            iy, ix = np.unravel_index(int(heatmaps[channel].argmax()), heatmaps[channel].shape)
            self.assertEqual((ix, iy), (int(cx), int(cy)))
            self.assertEqual(float(heatmaps[channel, iy, ix]), 1.0)
            np.testing.assert_allclose(calibration_offsets[:, iy, ix].numpy(), (cx - ix, cy - iy), atol=1e-5)
            self.assertEqual(float(calibration_mask[iy, ix]), 1.0)
        [(x, y)] = sample.entries
        cx, cy = x * scale, y * scale
        ix, iy = int(cx), int(cy)
        self.assertEqual(float(heatmaps[ENTRY_CHANNEL, iy, ix]), 1.0)
        np.testing.assert_allclose(entry_offsets[:, iy, ix].numpy(), (cx - ix, cy - iy), atol=1e-5)
        self.assertEqual(float(entry_mask.sum()), 1.0)
        self.assertEqual(float(entry_mask[iy, ix]), 1.0)

    def test_an_entry_point_in_a_crossings_cell_leaves_the_crossings_offset(self):
        photo = self.data.root / "cell.jpg"
        board_image(self.to_image, size=SIZE).save(photo, "JPEG", quality=90)
        sample = Sample(photo, ((0, 401.0, 403.0, 1.0),), ((403.0, 401.0),))
        _, _, _, calibration_offsets, calibration_mask, entry_offsets, entry_mask = KeypointDataset([sample], 800)[0]
        cell = 400 // STRIDE
        np.testing.assert_allclose(calibration_offsets[:, cell, cell].numpy(), (0.25, 0.75))
        np.testing.assert_allclose(entry_offsets[:, cell, cell].numpy(), (0.75, 0.25))
        self.assertEqual(float(calibration_mask[cell, cell]), 1.0)
        self.assertEqual(float(entry_mask[cell, cell]), 1.0)


class OwnerFenceTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.to_image = camera()
        self.records = []

    def tearDown(self):
        self.td.cleanup()

    def _photo(self, session: str, name: str, colour=(70, 70, 70)) -> Path:
        image = board_image(self.to_image)
        image.putpixel((0, 0), colour)
        return self.td.write_photo(session, name, image)

    def _record(self, session: str, visit: int = 1, angle: int = 1, colour=(70, 70, 70)) -> None:
        name = f"{session}-v{visit:02d}-p{angle}"
        photo = self._photo(session, name, colour)
        pixels = project(self.to_image, [p.mm for p in CALIBRATION_POINTS])
        entry = project(self.to_image, [(30.0, 40.0), (-50.0, 20.0)])
        self.records.append({
            "source": "owner", "capture_session": session, "visit": visit, "angle": angle,
            "photo": photo.relative_to(self.data.root).as_posix(), "photo_sha256": file_sha256(photo),
            "calibration": [{"name": p.name, "x": float(x), "y": float(y), "source": "hand"}
                            for p, (x, y) in zip(CALIBRATION_POINTS, pixels, strict=True)],
            "entries": [{"x": float(entry[0][0]), "y": float(entry[0][1]), "inferred": False},
                        {"x": float(entry[1][0]), "y": float(entry[1][1]), "inferred": True}],
        })
        path = self.data.build() / OWNER_RECORDS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in self.records), encoding="utf-8")

    def test_validation_sessions_never_reach_training_and_are_the_whole_validation_split(self):
        for session in ("s01", "s09", "s14", "s16"):
            self._record(session)
        nobody = HeldOutSet({}, {})
        self.assertEqual({s.capture_session for s in owner_samples(self.data, nobody, TRAIN)}, {"s01", "s16"})
        self.assertEqual({s.capture_session for s in owner_samples(self.data, nobody, VALIDATION)}, {"s09", "s14"})
        with self.assertRaises(DartsMlError):
            owner_samples(self.data, nobody, "held-out")

    def test_an_inferred_entry_point_is_not_a_training_target(self):
        self._record("s01")
        [sample] = owner_samples(self.data, HeldOutSet({}, {}), TRAIN)
        self.assertEqual(len(sample.entries), 1)

    def test_a_held_out_capture_session_is_refused_by_name(self):
        self._record("s01")
        self._record("s04")
        held = HeldOutSet({"s04": FrozenSession("sheet", "review")}, {"s04-v01-p1": FrozenPhoto("photo", "label")})
        for split in (TRAIN, VALIDATION):
            with self.subTest(split=split), self.assertRaisesRegex(RefusedRecord, "s04-v01-p1"):
                owner_samples(self.data, held, split)

    def test_a_held_out_photo_under_another_name_is_refused_by_its_hash(self):
        self._record("s01", colour=(1, 2, 3))
        held_photo = self._photo("s04", "s04-v01-p1", colour=(1, 2, 3))
        held = HeldOutSet({"s04": FrozenSession("sheet", "review")},
                          {"s04-v01-p1": FrozenPhoto(file_sha256(held_photo), "label")})
        with self.assertRaisesRegex(RefusedRecord, "bytes"):
            owner_samples(self.data, held, TRAIN)


class ModelTest(unittest.TestCase):
    def test_output_shape_and_a_finite_loss(self):
        torch.manual_seed(0)
        output = KeypointNet().eval()(torch.zeros(1, 3, 256, 256))
        self.assertEqual(tuple(output.shape), (1, OUTPUTS, 256 // STRIDE, 256 // STRIDE))
        cells = 256 // STRIDE
        heatmaps = torch.zeros(1, HEATMAPS, cells, cells)
        heatmaps[0, 0, 5, 5] = 1.0
        mask = torch.zeros(1, cells, cells)
        mask[0, 5, 5] = 1.0
        offsets = torch.zeros(1, 2, cells, cells)
        terms = loss_terms(output, heatmaps, torch.ones(1, HEATMAPS), offsets, mask, offsets, mask)
        self.assertTrue(all(torch.isfinite(t) for t in terms))


class _Stub(torch.utils.data.Dataset):
    def __len__(self):
        return 20

    def __getitem__(self, index):
        return torch.zeros(1)


class ProbeBoundsTest(unittest.TestCase):
    def _probe(self, steps: int):
        with mock.patch("darts_ml.train.deepdarts_samples", return_value=[None] * 20), \
             mock.patch("darts_ml.train.KeypointDataset", return_value=_Stub()), \
             mock.patch("darts_ml.train.KeypointNet", side_effect=AssertionError("trained past the bounds")):
            return probe(None, "cpu", steps=steps, size=64, batch=4, workers=0)

    def test_refuses_steps_inside_the_warmup(self):
        with self.assertRaisesRegex(DartsMlError, "warm-up"):
            self._probe(WARMUP)

    def test_refuses_more_steps_than_one_epoch_of_batches(self):
        with self.assertRaisesRegex(DartsMlError, "one epoch, 5 batches"):
            self._probe(WARMUP + 1)

    def test_size_off_the_stride_and_negative_workers_are_refused_by_the_parser(self):
        for argv in (["--size", "500"], ["--size", "0"], ["--workers", "-1"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit) as exit_:
                    main(["train", "--probe", *argv])
                self.assertEqual(exit_.exception.code, 2)
                self.assertIn(argv[0], error.getvalue())


class RunTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        records = TrainingDataTest._record
        holder = TrainingDataTest()
        holder.data, holder.to_image = self.data, camera(yaw_deg=10.0, pitch_deg=5.0, distance_mm=900.0,
                                                          focal_px=1200.0, size=SIZE)
        lines = [records(holder, name, split) for name, split in (("a", "train"), ("b", "train"), ("c", "val"))]
        (self.data.deepdarts() / RECORDS).write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")

    def tearDown(self):
        self.td.cleanup()

    def test_a_run_writes_its_folder_once_and_never_overwrites_it(self):
        config = RunConfig("smoke", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0)
        today = dt.date(2026, 11, 17)
        with contextlib.redirect_stderr(io.StringIO()):
            folder = train(self.data, config, today)
        self.assertEqual(folder, self.data.runs() / "2026-11-17-smoke")
        for name in ("config.json", "losses.jsonl", "epochs.jsonl", "best.pt", "last.pt"):
            self.assertTrue((folder / name).exists(), name)
        [epoch] = [json.loads(line) for line in (folder / "epochs.jsonl").read_text().splitlines()]
        self.assertEqual(epoch["figures"]["found"][1], 1)
        self.assertEqual(json.loads((folder / "config.json").read_text())["validation_photos"], 1)
        with self.assertRaisesRegex(DartsMlError, "never overwritten"):
            train(self.data, config, today)

    def test_a_run_name_is_a_plain_slug(self):
        with self.assertRaisesRegex(DartsMlError, "--name"):
            train(self.data, RunConfig("../escape", device="cpu"), dt.date(2026, 11, 17))


class ProbeFileTest(unittest.TestCase):
    def test_names_carry_steps_speed_and_time_and_never_overwrite(self):
        td = TemporaryData()
        self.addCleanup(td.cleanup)
        result = Probe("cuda", "gpu", 512, 16, 50, 1.0, 1.0, 10, [1.0], bf16=True)
        path = probe_path(td.data, result, dt.datetime(2026, 11, 17, 20, 18, 5))
        self.assertEqual(path.name, "gpu-512-16-50steps-bf16-20261117-201805.json")
        save(result, path)
        with self.assertRaises(FileExistsError):
            save(result, path)


class DeviceTest(unittest.TestCase):
    def test_gpu_refused_when_pytorch_sees_none(self):
        with mock.patch("torch.cuda.is_available", return_value=False):
            with self.assertRaises(DartsMlError):
                resolve_device("gpu")
            self.assertEqual(resolve_device("auto")[0], "cpu")

    def test_auto_takes_a_visible_gpu_whatever_its_maker(self):
        with mock.patch("torch.cuda.is_available", return_value=True), \
             mock.patch("torch.cuda.get_device_name", return_value="AMD Radeon 8050S Graphics"), \
             mock.patch("torch.version.hip", "7.14"):
            device, hardware = resolve_device("auto")
        self.assertEqual(device, "cuda")
        self.assertIn("ROCm 7.14", hardware)
        self.assertEqual(resolve_device("cpu")[0], "cpu")


if __name__ == "__main__":
    unittest.main()
