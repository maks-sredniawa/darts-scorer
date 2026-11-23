"""The owner's marked Visits, pulled by `pull-marked`, read as the real test set: never trained or chosen on."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from .board import Ring, Score, score
from .evaluate import Share
from .homography import project
from .locate import Located, matched_pairs
from .mounted import claimed
from .paths import DataDir
from .repeatability import Spread

_EXIF_ORIENTATION = 0x0112

NOTE = ("READ-ONCE: the owner's marked Visits are the real test set. Read a run here after it is chosen; never "
        "choose a run, a threshold or a setting on these figures, or they stop measuring anything.")


@dataclass(frozen=True)
class MarkedVisit:
    name: str
    photo: Path
    truth: tuple[Score, ...]
    placed: tuple[tuple[float, float], ...]
    accepted: tuple[tuple[float, float], ...]
    app_found: bool
    app_read: tuple[Score, ...]


def marked_visits(data: DataDir) -> tuple[list[MarkedVisit], list[tuple[str, str]]]:
    owners = claimed(data)
    visits, skipped = [], []
    for path in sorted(data.phone_captures().glob("*/*.json")):
        owner = owners.get(path.relative_to(data.root).as_posix())
        if owner:
            skipped.append((path.name, f"built into Capture session {owner}"))
            continue
        try:
            visits.append(_visit(path))
        except (KeyError, TypeError, ValueError) as error:
            skipped.append((path.name, f"not a marked Visit record ({error})"))
        except (FileNotFoundError, _Unusable) as error:
            skipped.append((path.name, str(error)))
    return visits, skipped


def _visit(path: Path) -> MarkedVisit:
    record = json.loads(path.read_text(encoding="utf-8"))
    name = record["photo"]
    if Path(name).name != name or not name.endswith(".jpg"):
        raise ValueError(f"photo {name!r} is not a plain .jpg name")
    photo = path.parent / name
    if not photo.is_file():
        raise FileNotFoundError(f"its Photo {name} is missing")
    _check_pixels(photo, (int(record["width"]), int(record["height"])))
    placed, accepted = [], []
    for dart in record["darts"]:
        if dart["at"] is None:
            continue
        point = (float(dart["at"]["x"]), float(dart["at"]["y"]))
        if dart["moved"]:
            placed.append(point)
        elif not dart["corrected"]:
            accepted.append(point)
    read = [d["read"] for d in record["darts"] if d["read"]] + [r["read"] for r in record["removed"]]
    return MarkedVisit(path.stem, photo, tuple(Score.parse(d["score"]) for d in record["darts"]), tuple(placed),
                       tuple(accepted), bool(record["boardFound"]), tuple(Score.parse(r["score"]) for r in read))


class _Unusable(Exception):
    pass


def _check_pixels(photo: Path, recorded: tuple[int, int]) -> None:
    """The Darts' points were kept in the record's width×height, on the Photo's pixels as stored."""
    try:
        with Image.open(photo) as image:
            size, orientation = image.size, image.getexif().get(_EXIF_ORIENTATION, 1)
    except (OSError, UnidentifiedImageError) as error:
        raise _Unusable(f"its Photo {photo.name} cannot be read ({error})") from error
    if size != recorded:
        raise _Unusable(f"its Photo {photo.name} is {size[0]}×{size[1]}, the record says {recorded[0]}×{recorded[1]}")
    if orientation != 1:
        raise _Unusable(f"its Photo {photo.name} carries EXIF orientation {orientation}, and the Darts' points are "
                        f"on the unrotated pixels")


@dataclass(frozen=True)
class MarkedReading:
    found: Share
    exact: Share
    darts_right: Share
    placed: Spread | None
    placed_unmatched: int
    accepted: Spread | None
    accepted_unmatched: int
    app_found: Share
    app_exact: Share
    app_darts_right: Share

    def lines(self) -> list[str]:
        def spread(s: Spread | None, unmatched: int) -> str:
            found = "none matched" if s is None else f"median {s.median_mm:.2f} mm, 95th {s.p95_mm:.2f} mm, {s.count} Darts"
            return f"{found}; {unmatched} with no Entry point left to match"

        return [
            f"Board found {self.found}",
            f"Visits scored exactly right {self.exact}; Darts right {self.darts_right}",
            f"Entry point from the owner's, where the owner moved the Dart: {spread(self.placed, self.placed_unmatched)}",
            f"Entry point from the owner's, where the owner kept the app's: {spread(self.accepted, self.accepted_unmatched)}",
            f"The app's own reading, as kept on the phone: Board found {self.app_found}; exactly right "
            f"{self.app_exact}; Darts right {self.app_darts_right}",
        ]


VISIT_DARTS = 3


def three_darts(scores) -> Counter:
    """A Visit's Scores made up to three with Misses, as the app makes up a reading (phase-1.md §3)."""
    darts = Counter(scores)
    darts[Score(Ring.MISS)] += max(0, VISIT_DARTS - sum(darts.values()))
    return +darts


def read_marked(visits: list[MarkedVisit], located: list[Located]) -> MarkedReading:
    tally = Counter()
    placed, accepted = [], []
    for visit, guess in zip(visits, located, strict=True):
        truth = three_darts(visit.truth)
        app = three_darts(visit.app_read)
        tally["darts"] += sum(truth.values())
        tally["app found"] += visit.app_found
        tally["app exact"] += app == truth
        tally["app right"] += sum((app & truth).values())
        if not guess.found:
            tally["placed unmatched"] += len(visit.placed)
            tally["accepted unmatched"] += len(visit.accepted)
            continue
        guess_mm = project(guess.to_board, [(e.x, e.y) for e in guess.entries]) if guess.entries else np.empty((0, 2))
        given = three_darts(score(*mm) for mm in guess_mm)
        tally["found"] += 1
        tally["exact"] += given == truth
        tally["right"] += sum((given & truth).values())
        owner = list(visit.placed) + list(visit.accepted)
        owner_mm = project(guess.to_board, owner) if owner else np.empty((0, 2))
        pairs = matched_pairs(owner_mm, guess_mm, within=math.inf)
        errors = {i: distance for i, _, distance in pairs}
        for i in range(len(owner)):
            is_placed = i < len(visit.placed)
            if i in errors:
                (placed if is_placed else accepted).append(errors[i])
            else:
                tally["placed unmatched" if is_placed else "accepted unmatched"] += 1
    visits_total = len(visits)
    return MarkedReading(
        found=Share(tally["found"], visits_total),
        exact=Share(tally["exact"], visits_total),
        darts_right=Share(tally["right"], tally["darts"]),
        placed=Spread.of(placed),
        placed_unmatched=tally["placed unmatched"],
        accepted=Spread.of(accepted),
        accepted_unmatched=tally["accepted unmatched"],
        app_found=Share(tally["app found"], visits_total),
        app_exact=Share(tally["app exact"], visits_total),
        app_darts_right=Share(tally["app right"], tally["darts"]),
    )
