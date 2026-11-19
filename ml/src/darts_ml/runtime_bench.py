from __future__ import annotations

import hashlib
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from . import DartsMlError
from .export_format import Format

ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64", "x86")
DEVICE_DIR = "/data/local/tmp/darts-ml-runtime-bench"
HARNESS = Path(__file__).resolve().parent / "android" / "OrtBench.java"
_GOOGLE_MAVEN = "https://dl.google.com/android/maven2/com/google/ai/edge/litert"
_MAVEN_CENTRAL = "https://repo1.maven.org/maven2/com/microsoft/onnxruntime"
_LITERT_BINARIES = "https://storage.googleapis.com/litert/binaries"


@dataclass(frozen=True)
class Artifact:
    name: str
    url: str
    sha256: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[1]


@dataclass(frozen=True)
class Runtime:
    label: str
    aars: tuple[Artifact, ...]


RUNTIMES = {
    Format.LITERT: Runtime("LiteRT 2.3.2", (
        Artifact("litert-2.3.2", f"{_GOOGLE_MAVEN}/litert/2.3.2/litert-2.3.2.aar",
                 "4d1f26b47f89e501940cbfb6e165faf3e600a7213af02e9816d39a49614bf702"),
        Artifact("litert-api-2.3.2", f"{_GOOGLE_MAVEN}/litert-api/2.3.2/litert-api-2.3.2.aar",
                 "1b7bfa1e8ceba5fd1a8a90db4615cc95839848cc11816786e6052df02cd55919"),
    )),
    Format.ONNX: Runtime("ONNX Runtime 1.32.0", (
        Artifact("onnxruntime-android-1.32.0",
                 f"{_MAVEN_CENTRAL}/onnxruntime-android/1.32.0/onnxruntime-android-1.32.0.aar",
                 "8e8dbb412ed4939675a157702f0c1e3621b436a645af7f7244536ac20bfad628"),
    )),
}

# Google publishes no 2.3.2 build of the tool; 2.3.1 is the newest versioned one beside the AAR.
BENCHMARK_MODEL = {
    "x86_64": Artifact("benchmark_model-2.3.1-android_x86_64", f"{_LITERT_BINARIES}/2.3.1/android_x86_64/benchmark_model",
                       "83ba46fef17dd46f1e594989066fe1989b0f8c2dc77f0fc316c86821e4bc2942"),
    "arm64-v8a": Artifact("benchmark_model-2.3.1-android_arm64", f"{_LITERT_BINARIES}/2.3.1/android_arm64/benchmark_model",
                          "a2b7f496ac3c18c25265821572f74810fde24e19efe9e91e4f0373825844eb11"),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(artifact: Artifact, cache: Path) -> Path:
    target = cache / artifact.name / artifact.filename
    if target.exists() and file_sha256(target) == artifact.sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    print(f"downloading {artifact.url} ...", file=sys.stderr, flush=True)
    try:
        with urllib.request.urlopen(artifact.url, timeout=60) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
    except (urllib.error.URLError, TimeoutError) as error:
        partial.unlink(missing_ok=True)
        raise DartsMlError(f"could not download {artifact.url}: {error}") from error
    found = file_sha256(partial)
    if found != artifact.sha256:
        partial.unlink()
        raise DartsMlError(f"{artifact.url} has SHA-256 {found}, not the pinned {artifact.sha256}; "
                           "a pinned version never changes, so find out why before moving the pin")
    partial.replace(target)
    return target


@dataclass(frozen=True)
class NativeLibrary:
    abi: str
    name: str
    size: int
    deflated: int


def native_libraries(aar: Path) -> list[NativeLibrary]:
    found = []
    with zipfile.ZipFile(aar) as archive:
        for entry in archive.infolist():
            parts = entry.filename.split("/")
            if len(parts) == 3 and parts[0] == "jni" and parts[1] in ABIS and parts[2].endswith(".so"):
                found.append(NativeLibrary(parts[1], parts[2], entry.file_size, _deflated(archive.read(entry))))
    return found


def _deflated(data: bytes) -> int:
    packer = zlib.compressobj(6, zlib.DEFLATED, -15)
    return len(packer.compress(data) + packer.flush())


def size_lines(libraries: Mapping[str, list[NativeLibrary]]) -> list[str]:
    lines = [f"{'runtime':<20} {'ABI':<12} {'uncompressed':>13} {'deflated':>10}  libraries"]
    for label, found in libraries.items():
        for abi in ABIS:
            shipped = [lib for lib in found if lib.abi == abi]
            if not shipped:
                lines.append(f"{label:<20} {abi:<12} {'not shipped':>13}")
                continue
            size, deflated = sum(lib.size for lib in shipped), sum(lib.deflated for lib in shipped)
            names = ", ".join(f"{lib.name} {_mib(lib.size)}" for lib in shipped)
            lines.append(f"{label:<20} {abi:<12} {_mib(size):>13} {_mib(deflated):>10}  {names}")
    return lines


def _mib(size: int) -> str:
    return f"{size / 2**20:.2f} MiB"


@dataclass(frozen=True)
class Timing:
    runs: int
    mean_ms: float
    median_ms: float
    p95_ms: float


def timing(samples_us: list[float]) -> Timing:
    if not samples_us:
        raise DartsMlError("the benchmark reported no timed runs")
    ordered = sorted(samples_us)
    nearest = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return Timing(len(ordered), statistics.fmean(ordered) / 1000, statistics.median(ordered) / 1000, nearest / 1000)


_LITERT_COUNT = re.compile(r"count=(\d+) .*?avg=([\d.]+) .*?median=([\d.]+) p95=([\d.]+)")
_XNNPACK = re.compile(r"Replacing (\d+) out of (\d+) node\(s\) with delegate \((\w+)\) node, yielding (\d+) partitions")


def parse_benchmark_model(output: str) -> Timing:
    found = _LITERT_COUNT.findall(output)
    if not found:
        raise DartsMlError("benchmark_model printed no timings:\n" + output[-2000:])
    runs, mean, median, p95 = found[-1]
    return Timing(int(runs), float(mean) / 1000, float(median) / 1000, float(p95) / 1000)


def delegation(output: str) -> str:
    found = _XNNPACK.search(output)
    if found is None:
        return "no delegate: every operation on LiteRT's built-in kernels"
    done, total, delegate, partitions = found.groups()
    return f"{done} of {total} operations in {delegate}, {partitions} partitions"


def parse_ort_bench(output: str) -> Timing:
    return timing([float(v) for v in re.findall(r"^run_us=(\d+)\s*$", output, re.MULTILINE)])


def attached_devices(adb_output: str) -> list[str]:
    serials = []
    for line in adb_output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "device":
            serials.append(fields[0])
    return serials


def choose_device(listed: list[str], environ: Mapping[str, str] = os.environ) -> str | None:
    named = environ.get("ANDROID_SERIAL")
    if named:
        if named not in listed:
            raise DartsMlError(f"ANDROID_SERIAL names {named}, which adb does not list as a ready device")
        return named
    if len(listed) > 1:
        raise DartsMlError(f"{len(listed)} devices attached ({', '.join(listed)}); name one with ANDROID_SERIAL")
    return listed[0] if listed else None


@dataclass(frozen=True)
class Reading:
    runtime: str
    threads: int
    timing: Timing
    note: str = ""


class Device:
    def __init__(self, serial: str, run: Callable = subprocess.run) -> None:
        self.serial = serial
        self._run = run

    def adb(self, *args: str) -> str:
        done = self._run(["adb", "-s", self.serial, *args], capture_output=True, text=True)
        if done.returncode != 0:
            raise DartsMlError(f"adb {' '.join(args)} failed:\n{done.stdout}{done.stderr}")
        return done.stdout + done.stderr

    def shell(self, command: str) -> str:
        return self.adb("shell", command)

    def prop(self, name: str) -> str:
        return self.shell(f"getprop {name}").strip()

    def push(self, source: Path, target: str) -> None:
        self.adb("push", str(source), target)

    def description(self) -> list[str]:
        cpu = cpuinfo(self.shell("cat /proc/cpuinfo"))
        lines = [f"device {self.serial}: {self.prop('ro.product.model')}, Android {self.prop('ro.build.version.release')} "
                 f"(API {self.prop('ro.build.version.sdk')}), ABI {self.prop('ro.product.cpu.abi')}",
                 f"  build {self.prop('ro.build.fingerprint')}",
                 f"  CPU {cpu.model}, {self.shell('nproc').strip()} cores, SIMD {' '.join(cpu.simd) or 'none listed'}"]
        if self.serial.startswith("emulator-"):
            lines.append(f"  host CPU {host_cpu()} (an x86_64 emulator runs on it, through the emulator's virtual CPU)")
        return lines


_SIMD = ("avx", "avx2", "fma", "f16c", "avx512f", "asimd", "asimddp", "sve", "i8mm")


@dataclass(frozen=True)
class Cpu:
    model: str
    simd: tuple[str, ...]


def cpuinfo(text: str) -> Cpu:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), value.strip())
    flags = set((fields.get("flags") or fields.get("Features") or "").split())
    return Cpu(fields.get("model name") or fields.get("Hardware") or "unnamed", tuple(f for f in _SIMD if f in flags))


def host_cpu() -> str:
    try:
        cpu = cpuinfo(Path("/proc/cpuinfo").read_text(encoding="utf-8"))
    except OSError:
        return platform.processor() or platform.machine()
    return f"{cpu.model}, {os.cpu_count()} threads, SIMD {' '.join(cpu.simd)}"


def harness_dex(cache: Path, ort_aar: Path) -> Path:
    source_sha = file_sha256(HARNESS)[:12]
    folder = cache / f"ort-bench-{RUNTIMES[Format.ONNX].aars[0].name}-{source_sha}"
    dex = folder / "classes.dex"
    if dex.exists():
        return dex
    javac, d8 = shutil.which("javac"), _d8()
    if javac is None:
        raise DartsMlError("javac is not on PATH; the ONNX Runtime harness is compiled with it")
    folder.mkdir(parents=True, exist_ok=True)
    classes = folder / "classes.jar"
    with zipfile.ZipFile(ort_aar) as archive:
        classes.write_bytes(archive.read("classes.jar"))
    run_tool([javac, "--release", "11", "-cp", str(classes), "-d", str(folder), str(HARNESS)])
    run_tool([str(d8), "--min-api", "26", "--output", str(folder), str(folder / "OrtBench.class"), str(classes)])
    return dex


def run_tool(command: list[str]) -> str:
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise DartsMlError(f"{Path(command[0]).name} exited {done.returncode}:\n{done.stdout}{done.stderr}")
    return done.stdout


def _d8() -> Path:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    tools = sorted(Path(sdk, "build-tools").glob("*/d8"), key=lambda p: [int(x) for x in re.findall(r"\d+", p.parent.name)]) if sdk else []
    if not tools:
        raise DartsMlError("no build-tools/*/d8 under ANDROID_HOME; the ONNX Runtime harness is dexed with it")
    return tools[-1]


def bench(device: Device, cache: Path, aars: Mapping[Format, list[Path]], models: Mapping[Format, Path], size: int,
          threads: list[int], warmup: int, runs: int) -> tuple[list[Reading], list[str]]:
    abi = device.prop("ro.product.cpu.abi")
    readings, skipped = [], []
    device.shell(f"rm -rf {DEVICE_DIR} && mkdir -p {DEVICE_DIR}")
    try:
        if Format.LITERT in models:
            if abi in BENCHMARK_MODEL:
                readings += _bench_litert(device, fetch(BENCHMARK_MODEL[abi], cache), models[Format.LITERT], threads,
                                          warmup, runs)
            else:
                skipped.append(f"LiteRT: Google publishes no benchmark_model for {abi}")
        if Format.ONNX in models:
            ort_aar = aars[Format.ONNX][0]
            readings += _bench_ort(device, harness_dex(cache, ort_aar), ort_aar, abi, models[Format.ONNX], size,
                                   threads, warmup, runs)
    finally:
        device.shell(f"rm -rf {DEVICE_DIR}")
    return readings, skipped


def _bench_litert(device: Device, binary: Path, model: Path, threads: list[int], warmup: int, runs: int) -> list[Reading]:
    device.push(binary, f"{DEVICE_DIR}/benchmark_model")
    device.push(model, f"{DEVICE_DIR}/{model.name}")
    device.shell(f"chmod 755 {DEVICE_DIR}/benchmark_model")
    readings = []
    for count in threads:
        print(f"LiteRT, threads {count or 'default'}: {warmup} warm-up + {runs} timed runs ...", file=sys.stderr, flush=True)
        flags = f"--graph={DEVICE_DIR}/{model.name} --warmup_runs={warmup} --warmup_min_secs=0 --num_runs={runs} --min_secs=0"
        output = device.shell(f"{DEVICE_DIR}/benchmark_model {flags}" + (f" --num_threads={count}" if count else ""))
        readings.append(Reading(RUNTIMES[Format.LITERT].label, count, parse_benchmark_model(output), delegation(output)))
    return readings


def _bench_ort(device: Device, dex: Path, aar: Path, abi: str, model: Path, size: int, threads: list[int], warmup: int,
               runs: int) -> list[Reading]:
    with zipfile.ZipFile(aar) as archive:
        names = [n for n in archive.namelist() if n.startswith(f"jni/{abi}/") and n.endswith(".so")]
        if not names:
            raise DartsMlError(f"{aar.name} ships no libraries for {abi}")
        staging = dex.parent / abi
        staging.mkdir(exist_ok=True)
        for name in names:
            (staging / Path(name).name).write_bytes(archive.read(name))
            device.push(staging / Path(name).name, f"{DEVICE_DIR}/{Path(name).name}")
    device.push(dex, f"{DEVICE_DIR}/ortbench.dex")
    device.push(model, f"{DEVICE_DIR}/{model.name}")
    readings = []
    for count in threads:
        print(f"ONNX Runtime, threads {count or 'default'}: {warmup} warm-up + {runs} timed runs ...", file=sys.stderr,
              flush=True)
        output = device.shell(f"cd {DEVICE_DIR} && LD_LIBRARY_PATH={DEVICE_DIR} CLASSPATH={DEVICE_DIR}/ortbench.dex "
                              f"app_process -Djava.library.path={DEVICE_DIR} / OrtBench {DEVICE_DIR}/{model.name} "
                              f"{count} {size} {warmup} {runs}")
        readings.append(Reading(RUNTIMES[Format.ONNX].label, count, parse_ort_bench(output), "CPU execution provider"))
    return readings


def latency_lines(readings: list[Reading]) -> list[str]:
    lines = [f"{'runtime':<20} {'threads':>7} {'runs':>5} {'mean ms':>8} {'median ms':>10} {'p95 ms':>8} "
             f"{'2 passes, mean':>15} {'2 passes, median':>17}"]
    for r in readings:
        t = r.timing
        lines.append(f"{r.runtime:<20} {str(r.threads or 'default'):>7} {t.runs:>5} {t.mean_ms:>8.1f} {t.median_ms:>10.1f} "
                     f"{t.p95_ms:>8.1f} {2 * t.mean_ms:>15.1f} {2 * t.median_ms:>17.1f}")
    lines += [f"{r.runtime}, threads {r.threads or 'default'}: {r.note}" for r in readings if r.note]
    return lines
