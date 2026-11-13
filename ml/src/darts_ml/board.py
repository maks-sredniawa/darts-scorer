"""ADR-0008's Board in millimetres: x to the right, y up, the bull at the origin."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

WIRE_MM = 1.5
SEGMENTS = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
SEGMENT_DEGREES = 360 / len(SEGMENTS)


@dataclass(frozen=True)
class Wire:
    name: str
    inner_mm: float
    outer_mm: float

    @property
    def centre_mm(self) -> float:
        return (self.inner_mm + self.outer_mm) / 2


BULL_RING = Wire("bull", 6.35, 6.35 + WIRE_MM)
OUTER_BULL_RING = Wire("25", 15.9, 15.9 + WIRE_MM)
INNER_TREBLE = Wire("ti", 99.4 - 2 * WIRE_MM, 99.4 - WIRE_MM)
OUTER_TREBLE = Wire("to", 107.4 - WIRE_MM, 107.4)
INNER_DOUBLE = Wire("di", 162.0 - 2 * WIRE_MM, 162.0 - WIRE_MM)
OUTER_DOUBLE = Wire("do", 170.0 - WIRE_MM, 170.0)

WIRES = (BULL_RING, OUTER_BULL_RING, INNER_TREBLE, OUTER_TREBLE, INNER_DOUBLE, OUTER_DOUBLE)
CALIBRATION_WIRES = (OUTER_DOUBLE, INNER_DOUBLE, OUTER_TREBLE, INNER_TREBLE)
TREBLE_WIRES = (INNER_TREBLE, OUTER_TREBLE)
DOUBLE_WIRES = (INNER_DOUBLE, OUTER_DOUBLE)
RADIAL_WIRE_MM = (OUTER_BULL_RING.centre_mm, OUTER_DOUBLE.centre_mm)
WIRE_MARGIN_MM = 2.0


def boundary_degrees(index: int) -> float:
    return (SEGMENT_DEGREES / 2 + SEGMENT_DEGREES * index) % 360


def board_point(radius_mm: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return radius_mm * math.sin(radians), radius_mm * math.cos(radians)


@dataclass(frozen=True)
class CalibrationPoint:
    name: str
    wire: Wire
    degrees: float

    @property
    def mm(self) -> tuple[float, float]:
        return board_point(self.wire.centre_mm, self.degrees)


CALIBRATION_POINTS = tuple(
    CalibrationPoint(
        f"{wire.name}-{SEGMENTS[i]}-{SEGMENTS[(i + 1) % len(SEGMENTS)]}",
        wire,
        boundary_degrees(i),
    )
    for wire in CALIBRATION_WIRES
    for i in range(len(SEGMENTS))
)
CALIBRATION_BY_NAME = {point.name: point for point in CALIBRATION_POINTS}
HAND_POINTS = ("do-5-20", "do-17-3", "do-8-11", "do-13-6")


class Ring(Enum):
    MISS = "miss"
    SINGLE = "S"
    DOUBLE = "D"
    TREBLE = "T"
    OUTER_BULL = "25"
    BULL = "50"


_MULTIPLIER = {Ring.SINGLE: 1, Ring.DOUBLE: 2, Ring.TREBLE: 3}
_FIXED = {Ring.MISS: 0, Ring.OUTER_BULL: 25, Ring.BULL: 50}


@dataclass(frozen=True)
class Score:
    ring: Ring
    number: int = 0

    @property
    def value(self) -> int:
        if self.ring in _MULTIPLIER:
            return _MULTIPLIER[self.ring] * self.number
        return _FIXED[self.ring]

    @property
    def token(self) -> str:
        if self.ring in _MULTIPLIER:
            return f"{self.ring.value}{self.number}"
        return self.ring.value

    def __str__(self) -> str:
        return self.token

    @classmethod
    def parse(cls, token: str) -> Score:
        for ring in (Ring.MISS, Ring.OUTER_BULL, Ring.BULL):
            if token == ring.value:
                return cls(ring)
        ring = next((r for r in _MULTIPLIER if token[:1] == r.value), None)
        if ring is None or not token[1:].isdigit() or int(token[1:]) not in SEGMENTS:
            raise ValueError(f"not a Score: {token!r}; write S1-S20, D1-D20, T1-T20, 25, 50 or miss")
        return cls(ring, int(token[1:]))


def segment_at(x_mm: float, y_mm: float) -> int:
    degrees = math.degrees(math.atan2(x_mm, y_mm)) % 360
    shifted = (degrees + SEGMENT_DEGREES / 2) % 360
    return SEGMENTS[int(shifted // SEGMENT_DEGREES) % len(SEGMENTS)]


def score(x_mm: float, y_mm: float) -> Score:
    radius = math.hypot(x_mm, y_mm)
    if radius < BULL_RING.centre_mm:
        return Score(Ring.BULL)
    if radius < OUTER_BULL_RING.centre_mm:
        return Score(Ring.OUTER_BULL)
    if radius >= OUTER_DOUBLE.centre_mm:
        return Score(Ring.MISS)
    number = segment_at(x_mm, y_mm)
    if radius < INNER_TREBLE.centre_mm:
        return Score(Ring.SINGLE, number)
    if radius < OUTER_TREBLE.centre_mm:
        return Score(Ring.TREBLE, number)
    if radius < INNER_DOUBLE.centre_mm:
        return Score(Ring.SINGLE, number)
    return Score(Ring.DOUBLE, number)


def wire_distance_mm(x_mm: float, y_mm: float) -> float:
    radius = math.hypot(x_mm, y_mm)
    to_ring = min(abs(radius - wire.centre_mm) for wire in WIRES)
    to_radial = min(_to_radial_wire(x_mm, y_mm, boundary_degrees(i)) for i in range(len(SEGMENTS)))
    return min(to_ring, to_radial)


def _to_radial_wire(x_mm: float, y_mm: float, degrees: float) -> float:
    ux, uy = board_point(1.0, degrees)
    along = min(max(x_mm * ux + y_mm * uy, RADIAL_WIRE_MM[0]), RADIAL_WIRE_MM[1])
    return math.hypot(x_mm - along * ux, y_mm - along * uy)
