"""Photos read as sRGB whatever colour profile they carry, as the app reads them (docs/phase-1.md §1, 2026-11-21)."""

from __future__ import annotations

import functools
import io
import struct
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
_INTENT = ImageCms.Intent.RELATIVE_COLORIMETRIC
_D50 = (0.9642, 1.0, 0.8249)
_D65 = (0.3127, 0.3290)
_P3_PRIMARIES = ((0.680, 0.320), (0.265, 0.690), (0.150, 0.060))
_SRGB_CURVE = (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045)
_BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])


def open_srgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return as_srgb(image)


def as_srgb(image: Image.Image) -> Image.Image:
    """The image as RGB, converted to sRGB when it carries an RGB profile, as Android's decoder does before the
    pixels reach `getPixels`; a profile-free image, or one whose profile cannot be read, is only converted to RGB."""
    rgb = image.convert("RGB")
    icc = image.info.get("icc_profile")
    try:
        transform = _to_srgb(icc) if icc else None
    except (OSError, ImageCms.PyCMSError) as error:
        warnings.warn(f"unreadable colour profile, read as sRGB as Android's decoder does: {error}", stacklevel=2)
        transform = None
    return rgb if transform is None else ImageCms.applyTransform(rgb, transform)


@functools.lru_cache(maxsize=8)
def _to_srgb(icc: bytes) -> ImageCms.ImageCmsTransform | None:
    """None for a profile that is not RGB, or whose conversion moves no colour by more than a level: an embedded
    sRGB profile, such as the one Android writes into every JPEG, which LittleCMS rounds one level off in places."""
    source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
    if source.profile.xcolor_space != "RGB ":
        return None
    transform = ImageCms.buildTransform(source, _SRGB, "RGB", "RGB", _INTENT)
    levels = np.linspace(0, 255, 18).round().astype(np.uint8)
    probe = Image.fromarray(np.stack(np.meshgrid(levels, levels, levels), axis=-1).reshape(18, -1, 3))
    moved = np.abs(np.asarray(ImageCms.applyTransform(probe, transform), int) - np.asarray(probe, int)).max()
    return None if moved <= 1 else transform


def to_display_p3(image: Image.Image) -> Image.Image:
    """An sRGB image's scene in Display P3's numbers, tagged with `display_p3()` when saved with its `icc_profile`."""
    profile = ImageCms.ImageCmsProfile(io.BytesIO(display_p3()))
    converted = ImageCms.profileToProfile(image.convert("RGB"), _SRGB, profile, renderingIntent=_INTENT,
                                          outputMode="RGB")
    converted.info["icc_profile"] = display_p3()
    return converted


@functools.cache
def display_p3() -> bytes:
    """An ICC v4 matrix/TRC profile of Display P3 with the sRGB transfer, the one Android's encoder embeds in a
    Display P3 JPEG ("Display P3 Gamut with sRGB Transfer")."""
    columns = _p3_to_xyz_d50().T
    curve = b"para" + bytes(4) + struct.pack(">HH", 3, 0) + b"".join(map(_s15f16, _SRGB_CURVE))
    tags = [(b"desc", _mluc("Display P3 Gamut with sRGB Transfer")), (b"cprt", _mluc("No copyright, use freely")),
            (b"wtpt", _xyz(_D50)), (b"rXYZ", _xyz(columns[0])), (b"gXYZ", _xyz(columns[1])),
            (b"bXYZ", _xyz(columns[2])), (b"rTRC", curve), (b"gTRC", curve), (b"bTRC", curve)]
    table, data, offset = [], b"", 128 + 4 + 12 * len(tags)
    stored: dict[bytes, int] = {}
    for signature, body in tags:
        if body not in stored:
            stored[body] = offset + len(data)
            data += body + bytes(-len(body) % 4)
        table.append(struct.pack(">4sII", signature, stored[body], len(body)))
    size = offset + len(data)
    header = (struct.pack(">I4sI4s4s4s", size, b"", 0x04300000, b"mntr", b"RGB ", b"XYZ ") + bytes(12) + b"acsp"
              + bytes(4) + struct.pack(">I", 0) + bytes(16) + struct.pack(">I", 0) + b"".join(map(_s15f16, _D50))
              + bytes(4) + bytes(16) + bytes(28))
    return header + struct.pack(">I", len(tags)) + b"".join(table) + data


def _p3_to_xyz_d50() -> np.ndarray:
    def xyz(x: float, y: float) -> np.ndarray:
        return np.array([x / y, 1.0, (1 - x - y) / y])

    primaries = np.column_stack([xyz(*p) for p in _P3_PRIMARIES])
    white = xyz(*_D65)
    to_d65 = primaries * np.linalg.solve(primaries, white)
    cone = _BRADFORD @ white, _BRADFORD @ np.array(_D50)
    adapt = np.linalg.inv(_BRADFORD) @ np.diag(cone[1] / cone[0]) @ _BRADFORD
    return adapt @ to_d65


def _s15f16(value: float) -> bytes:
    return struct.pack(">i", round(value * 65536))


def _xyz(values) -> bytes:
    return b"XYZ " + bytes(4) + b"".join(_s15f16(v) for v in values)


def _mluc(text: str) -> bytes:
    encoded = text.encode("utf-16-be")
    return b"mluc" + bytes(4) + struct.pack(">II2s2sII", 1, 12, b"en", b"US", len(encoded), 28) + encoded
