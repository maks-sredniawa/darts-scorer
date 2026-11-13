from __future__ import annotations

import json
from dataclasses import dataclass, field

from .capture_sessions import OUT, PhotoName, Sheet, load_sheet
from .heldout import HeldOutSet, file_sha256
from .labelme import Label, label_path, read_label
from .manifest import ReviewManifest
from .paths import DataDir
from .review import is_reviewed

OWNER = "owner"
RECORDS = "records.jsonl"


@dataclass
class Built:
    records: int = 0
    refused: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def build(data: DataDir, held: HeldOutSet) -> Built:
    built = Built()
    lines = []
    for path in sorted(data.sheets().glob("*.toml")):
        sheet = load_sheet(path)
        labels = data.labels(sheet.capture_session)
        manifest = ReviewManifest.load(labels)
        for photo in sheet.photo_names():
            name = str(photo)
            photo_file = data.photo(sheet.capture_session, name)
            label_file = label_path(labels, name)
            photo_sha = file_sha256(photo_file) if photo_file.exists() else None
            label_sha = file_sha256(label_file) if label_file.exists() else None
            reason = held.refusal(photo, sheet.held_out, photo_sha, label_sha)
            if reason:
                built.refused.append((name, reason))
            elif photo_sha is None or label_sha is None:
                built.skipped.append((name, "no Photo" if photo_sha is None else "no label"))
            elif not is_reviewed(manifest.get(name), label_file, sheet.held_out):
                built.skipped.append((name, "not reviewed"))
            else:
                record = _record(data, sheet, photo, photo_sha, read_label(label_file), manifest)
                lines.append(json.dumps(record, sort_keys=True))
    target = data.build() / RECORDS
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    temporary.replace(target)
    built.records = len(lines)
    return built


def _record(data: DataDir, sheet: Sheet, photo: PhotoName, sha: str, label: Label, manifest: ReviewManifest) -> dict:
    hand = manifest.get(str(photo)).hand_points
    return {
        "source": OWNER,
        "capture_session": sheet.capture_session,
        "visit": photo.visit,
        "angle": photo.angle,
        "photo": data.photo(sheet.capture_session, str(photo)).relative_to(data.root).as_posix(),
        "photo_sha256": sha,
        "width": label.width,
        "height": label.height,
        "calibration": [
            {"name": name, "x": x, "y": y, "source": "hand" if name in hand or not hand else "checked"}
            for name, (x, y) in label.calibration.items()
        ],
        "entries": [{"x": s.x, "y": s.y, "inferred": s.inferred} for s in label.entries],
        "scores": [str(dart.score) if dart.score else OUT for dart in sheet.visit(photo.visit).darts],
    }
