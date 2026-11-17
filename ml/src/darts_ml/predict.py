from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import DartsMlError
from .heldout import MANIFEST, file_sha256, verified
from .locate import Inference, Located, Speed, locate
from .paths import DataDir
from .train import load_weights, resolve_device

HELD_OUT = "held-out"


def write_predictions(path: Path, run: str, weights_sha256: str, located: dict[str, Located]) -> None:
    payload = {
        "run": run,
        "weights_sha256": weights_sha256,
        "photos": {
            name: {
                "calibration": {point: [x, y] for point, (x, y) in guess.calibration.items()},
                "entries": [{"x": e.x, "y": e.y, "low_confidence": e.low_confidence} for e in guess.entries],
            }
            for name, guess in sorted(located.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(payload, indent=1))


def predict(data: DataDir, run: str, weights: str = "best", device: str = "auto", manifest: Path = MANIFEST,
            out: Path | None = None, workers: int = 4, now: dt.datetime | None = None) -> Path:
    folder = data.runs() / run
    config_path = folder / "config.json"
    if not config_path.exists():
        raise DartsMlError(f"no run at {folder}; `darts-ml train` writes one")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    held = verified(data, manifest)
    names = held.photo_names()
    device, _ = resolve_device(device)
    speed = Speed(config["bf16"] and device == "cuda", config["channels_last"])
    weights_path = folder / f"{weights}.pt"
    model = load_weights(weights_path, device).to(memory_format=speed.memory)
    located = locate(Inference(model, device, config["size"], config["batch"], workers, speed),
                     [data.photo(n.capture_session, str(n)) for n in names])
    target = out or folder / f"predictions-{HELD_OUT}-{weights}-{(now or dt.datetime.now()):%Y%m%d-%H%M%S}.json"
    write_predictions(target, run, file_sha256(weights_path), dict(zip(map(str, names), located, strict=True)))
    return target
