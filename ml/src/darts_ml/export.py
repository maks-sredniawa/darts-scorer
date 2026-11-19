from __future__ import annotations

import importlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from . import DartsMlError
from .board import score
from .export_format import Format
from .heldout import file_sha256
from .homography import project
from .locate import Located, matched_pairs
from .model import Heads

PARITY_MM = 0.05
_ONNX_DOMAINS = ("", "ai.onnx")


@dataclass(frozen=True)
class Exported:
    path: Path
    size_bytes: int
    operations: dict[str, int]

    @property
    def outside(self) -> list[str]:
        """Operations the converter left outside the runtime's own set: an ONNX node in another domain, a LiteRT
        custom op (Flex included) or a StableHLO op it did not lower."""
        return sorted(o for o in self.operations if "::" in o or o.startswith(("CUSTOM", "STABLEHLO_")))


class _Raw(torch.nn.Module):
    """The model with its Heads as a plain tuple: neither converter can name a NamedTuple's outputs."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return tuple(self.model(image))


def exported_path(folder: Path, weights: str, format_: Format) -> Path:
    return folder / f"{weights}{format_.suffix}"


def export(model: torch.nn.Module, size: int, format_: Format, path: Path) -> Exported:
    raw = _Raw(model.cpu().eval()).eval()
    example = (torch.zeros(1, 3, size, size),)
    path.parent.mkdir(parents=True, exist_ok=True)
    if format_ is Format.ONNX:
        _require("onnxscript", "export")
        torch.onnx.export(raw, example, str(path), input_names=["image"], output_names=["board", "entry"],
                          dynamo=True, external_data=False, verbose=False)
    else:
        litert_torch = _require("litert_torch", "litert")
        litert_torch.convert(raw, example).export(str(path))
    return Exported(path, path.stat().st_size, dict(sorted(_operations(format_, path).items())))


def write_record(exported: Exported, run: str, weights: str, weights_sha256: str, size: int) -> Path:
    record = exported.path.with_name(exported.path.name + ".json")
    record.write_text(json.dumps({"run": run, "weights": weights, "weights_sha256": weights_sha256,
                                  "size": size, "bytes": exported.size_bytes, "operations": exported.operations},
                                 indent=1), encoding="utf-8")
    return record


def check_record(path: Path, weights_path: Path) -> None:
    record = path.with_name(path.name + ".json")
    if not path.exists() or not record.exists():
        raise DartsMlError(f"no exported model at {path}; `darts-ml export` writes one")
    if not weights_path.exists():
        raise DartsMlError(f"no weights at {weights_path}")
    if json.loads(record.read_text(encoding="utf-8"))["weights_sha256"] != file_sha256(weights_path):
        raise DartsMlError(f"{weights_path} has changed since {path.name} was exported from it; export it again")


def _require(module: str, extra: str):
    try:
        return importlib.import_module(module)
    except ImportError as error:
        if extra == "litert":
            raise DartsMlError(
                f"{module} is not installed: the `litert` extra conflicts with both `cpu` and `rocm`, so give it a venv "
                "of its own, `UV_PROJECT_ENVIRONMENT=~/.venvs/darts-ml-litert uv sync --locked --directory ml "
                "--extra litert --extra export`, and run with the same variable") from error
        raise DartsMlError(f"{module} is not installed: sync with --extra {extra}") from error


def _operations(format_: Format, path: Path) -> Counter:
    if format_ is Format.ONNX:
        onnx = _require("onnx", "export")
        graph = onnx.load(str(path)).graph
        return Counter(n.op_type if n.domain in _ONNX_DOMAINS else f"{n.domain}::{n.op_type}" for n in graph.node)
    schema = _require("ai_edge_litert.schema_py_generated", "export")
    model = schema.Model.GetRootAs(path.read_bytes(), 0)
    builtin = {code: name for name, code in vars(schema.BuiltinOperator).items() if not name.startswith("_")}
    names = []
    for i in range(model.OperatorCodesLength()):
        code = model.OperatorCodes(i)
        number = max(code.BuiltinCode(), code.DeprecatedBuiltinCode())
        names.append(f"CUSTOM {code.CustomCode().decode()}" if number == schema.BuiltinOperator.CUSTOM else builtin[number])
    return Counter(names[graph.Operators(j).OpcodeIndex()]
                   for graph in (model.Subgraphs(s) for s in range(model.SubgraphsLength()))
                   for j in range(graph.OperatorsLength()))


class Runtime(torch.nn.Module):
    """An exported model behind the module `locate` drives, run one Photo at a time as the app runs it."""

    def __init__(self, run: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]) -> None:
        super().__init__()
        self.run = run

    def forward(self, images: torch.Tensor) -> Heads:
        heads = [self.run(image[None].numpy()) for image in images]
        return Heads(*(torch.from_numpy(np.concatenate(part)) for part in zip(*heads, strict=True)))


def runtime(format_: Format, path: Path, threads: int | None = None) -> Runtime:
    if format_ is Format.ONNX:
        ort = _require("onnxruntime", "export")
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads or 0
        session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        return Runtime(lambda image: tuple(session.run(["board", "entry"], {"image": image})))
    interpreter_module = _require("ai_edge_litert.interpreter", "export")
    interpreter = interpreter_module.Interpreter(model_path=str(path), num_threads=threads)
    runner = interpreter.get_signature_runner()
    (name,) = runner.get_input_details()

    def run(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        out = runner(**{name: image})
        return tuple(out[k] for k in sorted(out))
    return Runtime(run)


@dataclass(frozen=True)
class Distances:
    values: tuple[float, ...]

    def line(self, kind: str) -> str:
        if not self.values:
            return f"{kind}: none compared"
        v = np.asarray(self.values)
        return (f"{kind}: {len(v)} compared, median {np.median(v):.5f} mm, 95th {np.percentile(v, 95):.5f} mm, "
                f"max {v.max():.5f} mm; {self.over} over {PARITY_MM:g} mm")

    @property
    def over(self) -> int:
        return sum(v > PARITY_MM for v in self.values)


@dataclass(frozen=True)
class Parity:
    photos: int
    calibration: Distances
    entries: Distances
    unmatched: int
    boards_differ: int
    visits_differ: int

    @property
    def same(self) -> bool:
        return not (self.calibration.over or self.entries.over or self.unmatched or self.boards_differ
                    or self.visits_differ)

    def lines(self) -> list[str]:
        return [self.calibration.line("Calibration points"), self.entries.line("Entry points"),
                f"points only one runtime kept {self.unmatched}; Board found by only one {self.boards_differ}; "
                f"Visits scored differently {self.visits_differ} of {self.photos} Photos"]


def parity(reference: list[Located], exported: list[Located]) -> Parity:
    """Distances in Board millimetres, each Photo's points both taken through PyTorch's homography, so a point
    that moved is not hidden by a homography that moved with it."""
    calibration, entries = [], []
    unmatched = boards = visits = 0
    for ours, theirs in zip(reference, exported, strict=True):
        visits += _visit(ours) != _visit(theirs)
        if ours.found != theirs.found:
            boards += 1
            continue
        if not ours.found:
            continue
        both = sorted(set(ours.calibration) & set(theirs.calibration))
        unmatched += len(set(ours.calibration) ^ set(theirs.calibration))
        calibration += _moved(ours.to_board, [ours.calibration[n] for n in both], [theirs.calibration[n] for n in both])
        a = _mm(ours.to_board, ours.entries)
        b = _mm(ours.to_board, theirs.entries)
        pairs = matched_pairs(a, b)
        entries += [d for _, _, d in pairs]
        unmatched += len(a) + len(b) - 2 * len(pairs)
    return Parity(len(reference), Distances(tuple(calibration)), Distances(tuple(entries)), unmatched, boards, visits)


def _moved(to_board: np.ndarray, first: list, second: list) -> list[float]:
    if not first:
        return []
    return list(np.linalg.norm(project(to_board, first) - project(to_board, second), axis=1))


def _mm(to_board: np.ndarray, entries) -> np.ndarray:
    return project(to_board, [(e.x, e.y) for e in entries]) if entries else np.empty((0, 2))


def _visit(located: Located) -> Counter:
    return Counter(score(*mm) for mm in _mm(located.to_board, located.entries)) if located.found else Counter()
