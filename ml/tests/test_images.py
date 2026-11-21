import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

from darts_ml.images import as_srgb, display_p3, open_srgb, to_display_p3
from synthetic import board_image, camera


class OpenSrgbTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.scene = board_image(camera(yaw_deg=15.0))

    def tearDown(self):
        self.folder.cleanup()

    def test_a_profile_free_jpeg_is_read_as_its_own_pixels(self):
        path = self.root / "plain.jpg"
        self.scene.save(path, quality=90)
        with Image.open(path) as image:
            self.assertNotIn("icc_profile", image.info)
            expected = image.convert("RGB").tobytes()
        self.assertEqual(open_srgb(path).tobytes(), expected)

    def test_a_display_p3_jpeg_is_read_as_littlecms_converts_it_to_srgb(self):
        path = self.root / "p3.jpg"
        p3 = to_display_p3(self.scene)
        p3.save(path, quality=95, icc_profile=p3.info["icc_profile"])
        with Image.open(path) as image:
            raw = image.convert("RGB")
            expected = ImageCms.profileToProfile(
                raw, ImageCms.ImageCmsProfile(io.BytesIO(image.info["icc_profile"])),
                ImageCms.createProfile("sRGB"), renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC, outputMode="RGB")
        read = open_srgb(path)
        self.assertEqual(read.tobytes(), expected.tobytes())
        self.assertGreater(np.abs(np.asarray(raw, int) - np.asarray(read, int)).max(), 10, "the profile was ignored")
        back = np.abs(np.asarray(read, int) - np.asarray(self.scene, int))
        self.assertLess(back.mean(), 2.0, "the scene did not survive a P3 round trip")

    def test_display_p3_holds_the_known_values(self):
        profile = ImageCms.ImageCmsProfile(io.BytesIO(display_p3()))
        self.assertEqual(ImageCms.getProfileDescription(profile).strip(), "Display P3 Gamut with sRGB Transfer")
        self.assertEqual(to_display_p3(Image.new("RGB", (2, 2), (255, 0, 0))).getpixel((0, 0)), (234, 51, 35))
        self.assertEqual(to_display_p3(Image.new("RGB", (2, 2), (128, 128, 128))).getpixel((0, 0)), (128, 128, 128))

    def test_an_embedded_srgb_profile_changes_no_pixel(self):
        pixels = Image.fromarray(np.random.default_rng(3).integers(0, 256, (32, 32, 3), dtype=np.uint8))
        pixels.info["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.assertEqual(as_srgb(pixels).tobytes(), pixels.tobytes())

    def test_an_unreadable_profile_is_read_as_srgb_with_a_warning(self):
        pixels = Image.new("RGB", (2, 2), (1, 2, 3))
        pixels.info["icc_profile"] = b"not a profile"
        with self.assertWarnsRegex(UserWarning, "unreadable colour profile"):
            self.assertEqual(as_srgb(pixels).tobytes(), Image.new("RGB", (2, 2), (1, 2, 3)).tobytes())

    def test_a_grey_photo_comes_back_rgb(self):
        self.assertEqual(as_srgb(Image.new("L", (3, 3), 77)).getpixel((1, 1)), (77, 77, 77))


if __name__ == "__main__":
    unittest.main()
