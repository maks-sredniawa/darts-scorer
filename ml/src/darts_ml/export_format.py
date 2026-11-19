from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from . import DartsMlError
from .heldout import file_sha256


class Format(StrEnum):
    ONNX = "onnx"
    LITERT = "litert"

    @property
    def suffix(self) -> str:
        return ".onnx" if self is Format.ONNX else ".tflite"


def exported_path(folder: Path, weights: str, format_: Format) -> Path:
    return folder / f"{weights}{format_.suffix}"


def check_record(path: Path, weights_path: Path) -> None:
    record = path.with_name(path.name + ".json")
    if not path.exists() or not record.exists():
        raise DartsMlError(f"no exported model at {path}; `darts-ml export` writes one")
    if not weights_path.exists():
        raise DartsMlError(f"no weights at {weights_path}")
    if json.loads(record.read_text(encoding="utf-8"))["weights_sha256"] != file_sha256(weights_path):
        raise DartsMlError(f"{weights_path} has changed since {path.name} was exported from it; export it again")
