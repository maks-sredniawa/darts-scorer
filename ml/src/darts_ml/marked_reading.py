"""The owner's marked Visits, pulled by `pull-marked`, read as the real test set: never trained or chosen on."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .board import Score, score
from .evaluate import Share
from .homography import project
from .locate import Located, matched_pairs
from .repeatability import Spread

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


def marked_visits(captures: Path) -> tuple[list[MarkedVisit], list[tuple[str, str]]]:
    visits, skipped = [], []
    for path in sorted(captures.glob("*/*.json")):
        try:
            visits.append(_visit(path))
        except (KeyError, TypeError, ValueError) as error:
            skipped.append((path.name, f"not a marked Visit record ({error})"))
        except FileNotFoundError as error:
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


def read_marked(visits: list[MarkedVisit], located: list[Located]) -> MarkedReading:
    tally = Counter()
    placed, accepted = [], []
    for visit, guess in zip(visits, located, strict=True):
        truth = Counter(visit.truth)
        app = Counter(visit.app_read)
        tally["darts"] += len(visit.truth)
        tally["app found"] += visit.app_found
        tally["app exact"] += app == truth
        tally["app right"] += sum((app & truth).values())
        if not guess.found:
            tally["placed unmatched"] += len(visit.placed)
            tally["accepted unmatched"] += len(visit.accepted)
            continue
        guess_mm = project(guess.to_board, [(e.x, e.y) for e in guess.entries]) if guess.entries else np.empty((0, 2))
        given = Counter(score(*mm) for mm in guess_mm)
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
