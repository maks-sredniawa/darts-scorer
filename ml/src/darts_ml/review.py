from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from .capture_sessions import load_sheet
from .labelme import label_path, open_window
from .manifest import PhotoRecord, Review, ReviewManifest
from .paths import DataDir, Round


def label_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviews_needed(held_out: bool) -> int:
    return 2 if held_out else 1


def matching_days(record: PhotoRecord, sha256: str) -> set[dt.date]:
    return {review.day for review in record.reviews if review.sha256 == sha256}


def is_reviewed(record: PhotoRecord, label: Path, held_out: bool) -> bool:
    return len(matching_days(record, label_sha256(label))) >= reviews_needed(held_out)


def review_problem(record: PhotoRecord, label: Path, held_out: bool) -> str | None:
    days = matching_days(record, label_sha256(label))
    if len(days) >= reviews_needed(held_out):
        return None
    if not record.reviews:
        return "not reviewed"
    if not days:
        return "edited after its last review; review it again"
    return (
        "a held-out Photo needs two reviews on different days that both match its label; "
        f"{len(days)} matches, so review it again on a later day"
    )


def review(
    data: DataDir,
    name: str,
    round_: Round = Round.A,
    window=open_window,
    ask=input,
    say=print,
    today: dt.date | None = None,
) -> int:
    today = today or dt.date.today()
    sheet = load_sheet(data.sheet(name))
    labels = data.labels(name, round_)
    manifest = ReviewManifest.load(labels)
    zoom = 300 if sheet.held_out else 200
    say(
        f"At {zoom}% zoom or more, drag every crossing that is not on its centre and delete every "
        "covered one. Accept, move or delete each suggested Entry point."
    )
    recorded = 0
    for photo in map(str, sheet.photo_names()):
        target = label_path(labels, photo)
        if not target.exists():
            say(f"{photo}: not labelled yet; skipped")
            continue
        record = manifest.get(photo)
        if is_reviewed(record, target, sheet.held_out):
            continue
        if today in matching_days(record, label_sha256(target)):
            say(f"{photo}: reviewed today already; its next review is on a later day")
            continue
        seconds = window(data.photo(name, photo), labels)
        record = manifest.record(photo)
        record.review_seconds += seconds
        answer = ask(f"{photo}: was every crossing looked at, at {zoom}%? [y/N/q] ").strip().lower()
        if answer == "y":
            record.reviews.append(Review(today, label_sha256(target)))
            recorded += 1
        manifest.save()
        if answer == "q":
            break
    return recorded
