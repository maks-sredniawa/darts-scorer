from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

FILE_NAME = "review.toml"


@dataclass(frozen=True)
class Review:
    day: dt.date
    sha256: str


@dataclass
class PhotoRecord:
    label_seconds: float = 0.0
    review_seconds: float = 0.0
    hand_points: dict[str, tuple[float, float]] = field(default_factory=dict)
    reviews: list[Review] = field(default_factory=list)


@dataclass
class ReviewManifest:
    path: Path
    photos: dict[str, PhotoRecord]

    @classmethod
    def load(cls, labels: Path) -> ReviewManifest:
        path = labels / FILE_NAME
        if not path.exists():
            return cls(path, {})
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(path, {name: _record(entry) for name, entry in raw.get("photos", {}).items()})

    def record(self, photo: str) -> PhotoRecord:
        return self.photos.setdefault(photo, PhotoRecord())

    def get(self, photo: str) -> PhotoRecord:
        return self.photos.get(photo, PhotoRecord())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"photos": {name: _dump(record) for name, record in sorted(self.photos.items())}}
        temporary = self.path.with_suffix(".toml.tmp")
        temporary.write_text(tomli_w.dumps(payload), encoding="utf-8")
        temporary.replace(self.path)


def _record(entry: dict) -> PhotoRecord:
    return PhotoRecord(
        label_seconds=float(entry.get("label_seconds", 0.0)),
        review_seconds=float(entry.get("review_seconds", 0.0)),
        hand_points={k: (float(v[0]), float(v[1])) for k, v in entry.get("hand_points", {}).items()},
        reviews=[Review(r["date"], r["sha256"]) for r in entry.get("reviews", [])],
    )


def _dump(record: PhotoRecord) -> dict:
    return {
        "label_seconds": round(record.label_seconds, 1),
        "review_seconds": round(record.review_seconds, 1),
        "hand_points": {k: [v[0], v[1]] for k, v in record.hand_points.items()},
        "reviews": [{"date": r.day, "sha256": r.sha256} for r in record.reviews],
    }
