from __future__ import annotations

from enum import StrEnum


class Format(StrEnum):
    ONNX = "onnx"
    LITERT = "litert"

    @property
    def suffix(self) -> str:
        return ".onnx" if self is Format.ONNX else ".tflite"
