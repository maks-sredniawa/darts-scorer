"""The mark: the board's alternating segments split by the treble wire round a holed bull, the single definition of this app's identity.

See `art/README.md` for why it is the single source and where it came from.

Coordinates are in arbitrary units around an origin at the mark's centre, angles in degrees clockwise
from twelve o'clock; callers fit them to their own canvas with `fit()`. y grows downward, as it does
in both SVG and PIL.
"""

import math
import re
from dataclasses import dataclass

GROUND = (0x2A, 0x2A, 0x28)
MARK_INK = (0xEF, 0xC0, 0x5D)


@dataclass(frozen=True)
class Subpath:
    """One closed contour, as cubic path data.

    `d` is always wound CLOCKWISE on screen (positive shoelace area with y downward). A hole is
    stored the same way and reversed at read time by `nodes()`, so it is subtracted by the non-zero
    fill rule that both SVG and VectorDrawable use by default. That is what makes the hole a real
    hole rather than a shape painted in the background colour — and it is why it survives the
    monochrome layer, where Android tints everything one flat colour and a painted hole would vanish.
    """

    d: str
    hole: bool = False


def _at(r, a):
    t = math.radians(a)
    return r * math.sin(t), -r * math.cos(t)


def _arc(r, a0, a1):
    """One cubic for an arc of at most 90°, from a0 to a1; returns its three trailing points."""
    k = 4 / 3 * math.tan(math.radians(a1 - a0) / 4) * r
    (x0, y0), (x3, y3) = _at(r, a0), _at(r, a1)
    t0, t1 = math.radians(a0), math.radians(a1)
    c1 = (x0 + k * math.cos(t0), y0 + k * math.sin(t0))
    c2 = (x3 - k * math.cos(t1), y3 - k * math.sin(t1))
    return c1, c2, (x3, y3)


def _line(p, q):
    return p, q, q


def _d(start, segments):
    f = lambda p: f"{p[0]:.2f},{p[1]:.2f}"
    return f"M{f(start)}" + "".join("C" + " ".join(f(p) for p in seg) for seg in segments) + "Z"


def sector(r0, r1, a0, a1):
    return _d(
        _at(r1, a0),
        [_arc(r1, a0, a1), _line(_at(r1, a1), _at(r0, a1)), _arc(r0, a1, a0), _line(_at(r0, a0), _at(r1, a0))],
    )


def circle(r):
    return _d(_at(r, 0), [_arc(r, a, a + 90) for a in (0, 90, 180, 270)])


SEGMENT = 22.5
TREBLE_GAP = (56, 65)

PARTS = (
    *(
        Subpath(sector(r0, r1, a - SEGMENT / 2, a + SEGMENT / 2))
        for a in range(0, 360, 45)
        for r0, r1 in ((27, TREBLE_GAP[0]), (TREBLE_GAP[1], 100))
    ),
    Subpath(circle(17)),
    Subpath(circle(7.5), hole=True),
)

_NUM = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?")


def _points(d):
    """Path data -> the flat control-point list: 1 start point plus 3 per cubic segment."""
    pts = []
    for chunk in re.finditer(r"[MC]([^MCZz]*)", d):
        nums = [float(v) for v in _NUM.findall(chunk.group(1))]
        pts += list(zip(nums[0::2], nums[1::2]))
    return pts


def nodes(e, tf=lambda p: p):
    """Control points, caller-transformed, wound for fill or hole."""
    pts = _points(e.d)
    if e.hole:
        pts.reverse()
    return [tf(p) for p in pts]


def path_data(e, tf=lambda p: p, precision=2):
    """SVG/VectorDrawable path data for one subpath."""
    n = nodes(e, tf)

    def f(p):
        return f"{round(p[0], precision):g},{round(p[1], precision):g}"

    out = [f"M{f(n[0])}"]
    for i in range(1, len(n), 3):
        out.append("C" + " ".join(f(n[i + j]) for j in range(3)))
    return "".join(out) + "Z"


def outline(e, tf=lambda p: p, steps=32):
    """The same subpath flattened to a polygon, for renderers that can't draw curves."""
    n = nodes(e, tf)
    pts = []
    for i in range(1, len(n), 3):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = n[i - 1], n[i], n[i + 1], n[i + 2]
        for s in range(steps):
            t = s / steps
            u = 1 - t
            pts.append((
                u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
                u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3,
            ))
    return pts


def bounds(parts=PARTS):
    """Bounding box of the silhouette. Holes are ignored — a hole cannot extend the mark."""
    xs, ys = [], []
    for e in parts:
        if e.hole:
            continue
        for x, y in outline(e):
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def fit(canvas, art_size, parts=PARTS):
    """A transform placing the mark centred on a square canvas at a given longest-side size.

    Returns a function mapping mark coordinates to canvas coordinates.
    """
    x0, y0, x1, y1 = bounds(parts)
    scale = art_size / max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return lambda p: (canvas / 2 + (p[0] - cx) * scale, canvas / 2 + (p[1] - cy) * scale)
