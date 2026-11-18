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
from darts_ml.model import (BOARD_STRIDE, CALIBRATION_CHANNELS, ENTRY_POINT, ENTRY_STRIDE, PRIOR_LOGIT, KeypointNet,
                            entry_stride_of, load_matching)
from darts_ml.heldout import FrozenPhoto, FrozenSession, HeldOutSet, file_sha256
from darts_ml.records import RECORDS as OWNER_RECORDS
from darts_ml.train import (RING_WEIGHT, WARMUP, Probe, RunConfig, load_weights, loss_terms, probe, probe_path,
                            resolve_device, save, train)
from darts_ml.training_data import (
    PROJECTED_WEIGHT,
    RING_INNER_MM,
    RING_OUTER_MM,
    TRAIN,
    VALIDATION,
    KeypointDataset,
    RefusedRecord,
    Sample,
    deepdarts_reading_samples,
    deepdarts_samples,
    owner_samples,
    targets,
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
        image, made = KeypointDataset([sample], 512)[0]
        self.assertEqual(tuple(image.shape), (3, 512, 512))
        self.assertEqual(tuple(made.board_heat.shape), (CALIBRATION_CHANNELS, 128, 128))
        self.assertEqual(tuple(made.entry_heat.shape), (256, 256))
        scale = 512 / SIZE[0] / BOARD_STRIDE
        for channel, x, y, _ in sample.calibration[:3]:
            cx, cy = x * scale, y * scale
            iy, ix = np.unravel_index(int(made.board_heat[channel].argmax()), made.board_heat[channel].shape)
            self.assertEqual((ix, iy), (int(cx), int(cy)))
            self.assertEqual(float(made.board_heat[channel, iy, ix]), 1.0)
            np.testing.assert_allclose(made.board_offsets[:, iy, ix].numpy(), (cx - ix, cy - iy), atol=1e-5)
            self.assertEqual(float(made.board_mask[iy, ix]), 1.0)
        [(x, y)] = sample.entries
        cx, cy = x * 512 / SIZE[0] / ENTRY_STRIDE, y * 512 / SIZE[1] / ENTRY_STRIDE
        ix, iy = int(cx), int(cy)
        self.assertEqual(float(made.entry_heat[iy, ix]), 1.0)
        self.assertAlmostEqual(float(made.entry_heat[iy, ix + 1]), float(np.exp(-0.5)), places=6)
        np.testing.assert_allclose(made.entry_offsets[:, iy, ix].numpy(), (cx - ix, cy - iy), atol=1e-5)
        self.assertEqual(float(made.entry_mask.sum()), 1.0)
        self.assertEqual(float(made.entry_mask[iy, ix]), 1.0)

    def test_an_entry_point_in_a_crossings_cell_leaves_the_crossings_offset(self):
        photo = self.data.root / "cell.jpg"
        board_image(self.to_image, size=SIZE).save(photo, "JPEG", quality=90)
        sample = Sample(photo, ((0, 401.0, 403.0, 1.0),), ((403.0, 401.0),))
        _, made = KeypointDataset([sample], 800, entry_stride=BOARD_STRIDE)[0]
        cell = 400 // BOARD_STRIDE
        np.testing.assert_allclose(made.board_offsets[:, cell, cell].numpy(), (0.25, 0.75))
        np.testing.assert_allclose(made.entry_offsets[:, cell, cell].numpy(), (0.75, 0.25))
        self.assertEqual(float(made.board_mask[cell, cell]), 1.0)
        self.assertEqual(float(made.entry_mask[cell, cell]), 1.0)


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


def _random_state(model: KeypointNet, seed: int) -> dict:
    generator = torch.Generator().manual_seed(seed)
    state = {}
    for name, value in model.state_dict().items():
        if name.endswith("running_var"):
            value = torch.rand(value.shape, generator=generator) + 0.5
        elif value.is_floating_point():
            value = torch.randn(value.shape, generator=generator) * 0.1
        state[name] = value
    return state


class ModelTest(unittest.TestCase):
    def test_the_board_head_at_stride_four_and_the_entry_head_at_its_own(self):
        torch.manual_seed(0)
        for stride in (ENTRY_STRIDE, BOARD_STRIDE):
            model = KeypointNet(stride).eval()
            for size in (512, 640):
                with self.subTest(stride=stride, size=size), torch.no_grad():
                    heads = model(torch.zeros(1, 3, size, size))
                    self.assertEqual(tuple(heads.board.shape), (1, CALIBRATION_CHANNELS + 2, size // 4, size // 4))
                    self.assertEqual(tuple(heads.entry.shape), (1, 3, size // stride, size // stride))
                    self.assertEqual(entry_stride_of(heads), stride)

    def test_the_entry_heatmap_starts_at_the_prior(self):
        self.assertAlmostEqual(KeypointNet().entry_out.bias[0].item(), PRIOR_LOGIT, places=6)

    def test_a_finite_loss_and_the_ring_raises_only_the_entry_negatives(self):
        torch.manual_seed(0)
        size = 256
        with torch.no_grad():
            heads = KeypointNet().eval()(torch.zeros(2, 3, size, size))
        made = targets([(0, 41.0, 41.0, 1.0), (ENTRY_POINT, 100.0, 100.0, 1.0)], size,
                       to_board=np.diag([0.5, 0.5, 1.0]))
        batch = type(made)(*(torch.from_numpy(np.stack([a, a])) for a in made))
        plain = loss_terms(heads, batch, ring_weight=0.0)
        ringed = loss_terms(heads, batch, ring_weight=RING_WEIGHT)
        self.assertTrue(all(torch.isfinite(t) for t in plain + ringed))
        self.assertGreater(float(ringed[0]), float(plain[0]))
        self.assertEqual(float(ringed[1]), float(plain[1]))
        board_only = loss_terms(heads, batch, entries=False, ring_weight=RING_WEIGHT)
        self.assertEqual([float(t) for t in board_only],
                         [float(t) for t in loss_terms(heads, batch, entries=False, ring_weight=0.0)])

    def test_a_stride_four_runs_weights_start_a_stride_two_model_with_the_same_board(self):
        old = KeypointNet(BOARD_STRIDE)
        old.load_state_dict(_random_state(old, 1))
        new = KeypointNet(ENTRY_STRIDE)
        fresh = load_matching(new, old.state_dict())
        self.assertTrue(fresh)
        self.assertTrue(all(name.startswith("entry_") for name in fresh), fresh)
        self.assertEqual(set(fresh), {k for k in new.state_dict() if k.startswith("entry_")})
        image = torch.rand(1, 3, 128, 128, generator=torch.Generator().manual_seed(2))
        with torch.no_grad():
            torch.testing.assert_close(new.eval()(image).board, old.eval()(image).board)

    def test_loading_a_run_builds_the_layout_its_weights_were_saved_in(self):
        td = TemporaryData()
        self.addCleanup(td.cleanup)
        for stride in (BOARD_STRIDE, ENTRY_STRIDE):
            path = td.data.root / f"{stride}.pt"
            torch.save({"model": KeypointNet(stride).state_dict(), "epoch": 1}, path)
            self.assertEqual(load_weights(path, "cpu").entry_stride, stride)


class RingTest(unittest.TestCase):
    """At 2 input pixels to the Board millimetre and stride 2, a cell is 1 mm of Board."""

    SIZE = 256
    TO_BOARD = np.diag([0.5, 0.5, 1.0])

    def _ring(self, entries_mm):
        points = [(ENTRY_POINT, 2 * x, 2 * y, 1.0) for x, y in entries_mm]
        return targets(points, self.SIZE, ENTRY_STRIDE, self.TO_BOARD).ring

    def test_the_ring_spans_inner_to_outer_millimetres(self):
        ring = self._ring([(60.0, 60.0)])
        ys, xs = np.nonzero(ring)
        mm = np.hypot(xs + 0.5 - 60.0, ys + 0.5 - 60.0)
        self.assertGreaterEqual(mm.min(), RING_INNER_MM)
        self.assertLessEqual(mm.max(), RING_OUTER_MM)
        self.assertEqual(float(ring[60, 60 + 10]), 1.0)
        self.assertEqual(float(ring[60, 60 + int(RING_OUTER_MM) + 2]), 0.0)

    def test_the_ring_leaves_out_every_positive_and_a_close_neighbours_tip(self):
        made = targets([(ENTRY_POINT, 120.0, 120.0, 1.0), (ENTRY_POINT, 132.0, 120.0, 1.0)], self.SIZE, ENTRY_STRIDE,
                       self.TO_BOARD)
        self.assertEqual(float((made.ring * made.entry_mask).sum()), 0.0)
        self.assertEqual(float(made.ring[made.entry_heat > np.exp(-2)].sum()), 0.0)
        neighbour = np.hypot(*np.mgrid[0:128, 0:128][::-1] + 0.5 - np.array([66.0, 60.0])[:, None, None])
        self.assertEqual(float(made.ring[neighbour < RING_INNER_MM].sum()), 0.0)
        self.assertEqual(float(made.ring[60, 60 - 10]), 1.0)

    def test_no_ring_without_the_boards_homography(self):
        points = [(ENTRY_POINT, 120.0, 120.0, 1.0)]
        self.assertEqual(float(targets(points, self.SIZE, ENTRY_STRIDE).ring.sum()), 0.0)


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
        for argv in (["--size", "500"], ["--size", "0"], ["--workers", "-1"], ["--entry-stride", "3"],
                     ["--ring-weight", "-1"]):
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

    def test_a_run_starts_from_a_stride_four_run_and_records_its_entry_settings(self):
        earlier = self.data.runs() / "2026-11-18-darts-512"
        earlier.mkdir(parents=True)
        torch.save({"model": KeypointNet(BOARD_STRIDE).state_dict(), "epoch": 1}, earlier / "best.pt")
        config = RunConfig("s2", device="cpu", epochs=1, size=64, batch=2, warmup_steps=1, workers=0,
                           init=earlier.name)
        log = io.StringIO()
        folder = train(self.data, config, dt.date(2026, 11, 19), log)
        self.assertIn("entry_out.weight", log.getvalue())
        self.assertNotIn("backbone", log.getvalue())
        recorded = json.loads((folder / "config.json").read_text())
        self.assertEqual((recorded["entry_stride"], recorded["ring_weight"]), (ENTRY_STRIDE, RING_WEIGHT))
        self.assertEqual((recorded["ring_inner_mm"], recorded["ring_outer_mm"]), (RING_INNER_MM, RING_OUTER_MM))
        self.assertEqual(load_weights(folder / "best.pt", "cpu").entry_stride, ENTRY_STRIDE)

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
