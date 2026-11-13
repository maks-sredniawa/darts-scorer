import datetime as dt
import tomllib
import unittest

import numpy as np
from PIL import Image

from darts_ml.ingest import IngestError, ingest, jpegtran_command, metadata_markers, read_shot
from synthetic import SIZE, TemporaryData, as_stored, board_image, camera, jpeg_with_exif

START = dt.datetime(2026, 11, 14, 19, 0, 0)


def upright_photo(seed: int) -> Image.Image:
    image = board_image(camera(yaw_deg=10.0 * seed))
    pixels = np.asarray(image).copy()
    pixels[200:260, 300:420] = np.random.default_rng(seed).integers(0, 255, (60, 120, 3))
    return Image.fromarray(pixels)


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryData()
        self.data = self.td.data
        self.inbox = self.data.inbox("s01")
        self.inbox.mkdir(parents=True)

    def tearDown(self):
        self.td.cleanup()

    def put(self, file_name: str, image: Image.Image, orientation: int, seconds: int) -> None:
        stored = as_stored(image, orientation)
        jpeg_with_exif(stored, self.inbox / file_name, orientation=orientation, taken=START + dt.timedelta(seconds=seconds))

    def test_photos_come_out_upright_with_no_metadata_and_not_re_encoded(self):
        self.td.write_sheet("s01", [["T20", "T20", "S1"]])
        uprights = [upright_photo(seed) for seed in range(3)]
        self.put("IMG_9.jpg", uprights[0], 6, 0)
        self.put("IMG_8.jpg", uprights[1], 3, 10)
        self.put("IMG_7.jpg", uprights[2], 8, 20)
        names = ingest(self.data, "s01")
        self.assertEqual([str(n) for n in names], ["s01-v01-p1", "s01-v01-p2", "s01-v01-p3"])
        for name, upright, source in zip(names, uprights, ("IMG_9.jpg", "IMG_8.jpg", "IMG_7.jpg"), strict=True):
            out = self.data.photo("s01", str(name))
            raw = out.read_bytes()
            with Image.open(out) as photo, Image.open(self.inbox / source) as original:
                self.assertEqual(photo.size, SIZE)
                self.assertEqual(len(photo.getexif()), 0)
                self.assertEqual(sorted(map(sorted, photo.quantization.values())), sorted(map(sorted, original.quantization.values())))
                difference = np.abs(np.asarray(photo.convert("RGB"), dtype=int) - np.asarray(upright, dtype=int))
            self.assertEqual(metadata_markers(out), [])
            for leaked in (b"Exif", b"TestPhone", b"TestMake"):
                self.assertNotIn(leaked, raw)
            self.assertLess(difference.mean(), 3.0, "the Photo is not the one taken, upright")
            self.assertLess(difference[:10, :20].mean(), 40, "the corner marker is not top-left")

    def test_pixels_match_a_lossless_turn(self):
        self.td.write_sheet("s01", [["T20", "T20", "S1"]])
        upright = upright_photo(4)
        turns = {"a.jpg": (1, None), "b.jpg": (3, Image.Transpose.ROTATE_180), "c.jpg": (6, Image.Transpose.ROTATE_270)}
        for seconds, (file_name, (orientation, _)) in enumerate(turns.items()):
            self.put(file_name, upright, orientation, seconds)
        ingest(self.data, "s01")
        for angle, (file_name, (_, undo)) in enumerate(turns.items(), start=1):
            with Image.open(self.inbox / file_name) as stored:
                decoded = stored.convert("RGB")
            expected = np.asarray(decoded if undo is None else decoded.transpose(undo), dtype=int)
            with Image.open(self.data.photo("s01", f"s01-v01-p{angle}")) as photo:
                got = np.asarray(photo.convert("RGB"), dtype=int)
            difference = np.abs(got - expected)
            self.assertLessEqual(difference.max(), 4, f"p{angle} was decoded and encoded again")
            self.assertLess((difference > 1).mean(), 0.005, f"p{angle} was decoded and encoded again")

    def test_capture_details_are_copied_into_the_sheet(self):
        sheet = self.td.write_sheet("s01", [["T20", "T20", "S1"]])
        for seconds in range(3):
            self.put(f"{seconds}.jpg", upright_photo(seconds), 1, seconds)
        ingest(self.data, "s01")
        recorded = tomllib.loads(sheet.read_text())["ingest"]["photos"]
        self.assertEqual(recorded["s01-v01-p2"]["camera"], "TestMake TestPhone")
        self.assertEqual(recorded["s01-v01-p2"]["taken"], START + dt.timedelta(seconds=1))

    def test_a_visit_with_two_photos_stops_the_ingest(self):
        self.td.write_sheet("s01", [["T20", "T20", "S1"], ["S5", "S5", "out"]])
        for seconds in range(5):
            self.put(f"IMG_{seconds}.jpg", upright_photo(seconds), 1, seconds)
        with self.assertRaises(IngestError) as caught:
            ingest(self.data, "s01")
        message = str(caught.exception)
        self.assertIn("6 Photos", message)
        self.assertIn("holds 5", message)
        for seconds in range(5):
            self.assertIn(f"IMG_{seconds}.jpg", message)
        self.assertFalse(self.data.photos("s01").exists())

    def test_a_file_that_is_not_a_jpeg_is_refused(self):
        self.td.write_sheet("s01", [["T20", "T20", "S1"]])
        for seconds in range(2):
            self.put(f"{seconds}.jpg", upright_photo(seconds), 1, seconds)
        upright_photo(3).save(self.inbox / "heif-really.jpg", "PNG")
        with self.assertRaises(IngestError) as caught:
            ingest(self.data, "s01")
        self.assertIn("heif-really.jpg is not a JPEG", str(caught.exception))

    def test_every_turn_trims_and_an_upright_photo_is_only_stripped(self):
        self.put("odd.jpg", Image.new("RGB", (650, 490), (90, 90, 90)), 6, 0)
        shot = read_shot(self.inbox / "odd.jpg")
        for orientation in range(2, 9):
            command = jpegtran_command(shot.__class__(shot.path, shot.taken, orientation, ""), self.inbox / "x.jpg")
            self.assertIn("-trim", command)
            self.assertEqual(command[1:3], ["-copy", "none"])
        upright = jpegtran_command(shot.__class__(shot.path, shot.taken, 1, ""), self.inbox / "x.jpg")
        self.assertNotIn("-trim", upright)
        self.assertNotIn("-rotate", upright)

    def test_a_partial_edge_block_is_trimmed_not_re_encoded(self):
        self.td.write_sheet("s01", [["T20", "T20", "S1"]])
        for seconds, orientation in enumerate((6, 3, 8)):
            self.put(f"{seconds}.jpg", Image.new("RGB", (650, 490), (90, 90, 90)), orientation, seconds)
        ingest(self.data, "s01")
        for angle in (1, 2, 3):
            with Image.open(self.data.photo("s01", f"s01-v01-p{angle}")) as photo:
                width, height = photo.size
            self.assertTrue(650 - 16 < width <= 650 and 490 - 16 < height <= 490, photo.size)
            self.assertNotEqual((width, height), (650, 490))


if __name__ == "__main__":
    unittest.main()
