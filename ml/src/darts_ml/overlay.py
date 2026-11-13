from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .board import CALIBRATION_POINTS, OUTER_BULL_RING, OUTER_DOUBLE, SEGMENTS, WIRES, board_point, boundary_degrees, score
from .capture_sessions import load_sheet
from .homography import invert, project
from .labelme import label_path, read_label
from .paths import DataDir, Round
from .prefill import image_to_board

RING = (255, 210, 0)
CROSSING = (0, 220, 255)
CLICKED = (255, 255, 255)
ENTRY_COLOUR = (255, 0, 200)
NUMBER_RADIUS_MM = 190.0


def overlay(data: DataDir, name: str, round_: Round = Round.A) -> list[str]:
    sheet = load_sheet(data.sheet(name))
    labels = data.labels(name, round_)
    target = data.overlays(name, round_)
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for photo in map(str, sheet.photo_names()):
        path = label_path(labels, photo)
        if not path.exists():
            continue
        label = read_label(path)
        if len(label.calibration) < 4:
            continue
        with Image.open(data.photo(name, photo)) as image:
            rendered = render(image.convert("RGB"), label)
        rendered.save(target / f"{photo}.jpg", quality=85)
        written.append(photo)
    return written


def render(image: Image.Image, label) -> Image.Image:
    to_board = image_to_board(label.calibration)
    to_image = invert(to_board)
    draw = ImageDraw.Draw(image)
    width = max(1, round(min(image.size) / 600))
    font = ImageFont.load_default(size=max(12, 8 * width))

    def pixels(points_mm):
        return [tuple(p) for p in project(to_image, points_mm)]

    for wire in WIRES:
        circle = [board_point(wire.centre_mm, d) for d in np.linspace(0, 360, 361)]
        draw.line(pixels(circle), fill=RING, width=width)
    for index in range(len(SEGMENTS)):
        degrees = boundary_degrees(index)
        ends = [board_point(OUTER_BULL_RING.centre_mm, degrees), board_point(OUTER_DOUBLE.centre_mm, degrees)]
        draw.line(pixels(ends), fill=RING, width=width)
    for index, number in enumerate(SEGMENTS):
        x, y = pixels([board_point(NUMBER_RADIUS_MM, index * 360 / len(SEGMENTS))])[0]
        draw.text((x, y), str(number), fill=RING, font=font, anchor="mm")
    radius = 3 * width
    for (x, y) in pixels([p.mm for p in CALIBRATION_POINTS]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=CROSSING, width=width)
    for (x, y) in label.calibration.values():
        draw.ellipse((x - width, y - width, x + width, y + width), fill=CLICKED)
    for entry in label.entries:
        x, y = entry.xy
        mm = project(to_board, [entry.xy])[0]
        draw.ellipse((x - 2 * radius, y - 2 * radius, x + 2 * radius, y + 2 * radius), outline=ENTRY_COLOUR, width=width)
        text = score(*mm).token + (" inferred" if entry.inferred else "")
        draw.text((x + 3 * radius, y), text, fill=ENTRY_COLOUR, font=font, anchor="lm")
    return image

