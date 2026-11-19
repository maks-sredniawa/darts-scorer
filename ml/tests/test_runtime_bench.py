import contextlib
import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from darts_ml import DartsMlError
from darts_ml.runtime_bench import (Artifact, attached_devices, choose_device, cpuinfo, delegation, fetch,
                                    native_libraries, parse_benchmark_model, parse_ort_bench, size_lines, timing)

LITERT_OUTPUT = """\
INFO: Created TensorFlow Lite XNNPACK delegate for CPU.
VERBOSE: Replacing 139 out of 142 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 7 partitions for subgraph 0 (main).
INFO: Running benchmark for at least 3 iterations and at least 0.5 seconds but terminate if exceeding 150 seconds.
INFO: count=4 first=155218 curr=68797 min=68797 max=232158 avg=135736 std=64333 p5=68797 median=155218 p95=232158

INFO: Running benchmark for at least 10 iterations and at least 0 seconds but terminate if exceeding 150 seconds.
INFO: count=10 first=64581 curr=78667 min=56642 max=129675 avg=92940.5 std=22954 p5=56642 median=92985 p95=129675
"""


class TimingTest(unittest.TestCase):
    def test_benchmark_model_reads_the_timed_runs_not_the_warm_up(self):
        reading = parse_benchmark_model(LITERT_OUTPUT)
        self.assertEqual(reading.runs, 10)
        self.assertAlmostEqual(reading.mean_ms, 92.9405)
        self.assertAlmostEqual(reading.median_ms, 92.985)
        self.assertAlmostEqual(reading.p95_ms, 129.675)

    def test_benchmark_model_without_timings_is_refused(self):
        with self.assertRaises(DartsMlError):
            parse_benchmark_model("ERROR: could not load the model\n")

    def test_the_delegate_and_its_share_are_named(self):
        self.assertEqual(delegation(LITERT_OUTPUT), "139 of 142 operations in TfLiteXNNPackDelegate, 7 partitions")
        self.assertIn("no delegate", delegation("INFO: count=1 avg=1 median=1 p95=1\n"))

    def test_the_harness_output_skips_initialisation_and_warm_up(self):
        output = "init_us=41094\nwarmup_us=93336\n" + "".join(f"run_us={ms * 1000}\n" for ms in range(1, 21))
        reading = parse_ort_bench(output)
        self.assertEqual(reading.runs, 20)
        self.assertAlmostEqual(reading.mean_ms, 10.5)
        self.assertAlmostEqual(reading.median_ms, 10.5)
        self.assertAlmostEqual(reading.p95_ms, 19.0)

    def test_p95_is_the_nearest_rank(self):
        self.assertAlmostEqual(timing([1000.0] * 99 + [50_000.0]).p95_ms, 1.0)
        self.assertAlmostEqual(timing([1000.0] * 94 + [50_000.0] * 6).p95_ms, 50.0)

    def test_no_timed_runs_is_refused(self):
        with self.assertRaises(DartsMlError):
            parse_ort_bench("init_us=1\nwarmup_us=2\n")


class DeviceTest(unittest.TestCase):
    ADB = "List of devices attached\nemulator-5554\tdevice\nemulator-5610\tdevice\n0123abc\tunauthorized\n\n"

    def test_only_ready_devices_are_listed(self):
        self.assertEqual(attached_devices(self.ADB), ["emulator-5554", "emulator-5610"])

    def test_android_serial_names_the_device(self):
        self.assertEqual(choose_device(["emulator-5554", "emulator-5610"], {"ANDROID_SERIAL": "emulator-5610"}),
                         "emulator-5610")

    def test_two_devices_and_no_serial_is_refused(self):
        with self.assertRaises(DartsMlError) as caught:
            choose_device(["emulator-5554", "emulator-5610"], {})
        self.assertIn("ANDROID_SERIAL", str(caught.exception))

    def test_a_serial_adb_does_not_list_is_refused(self):
        with self.assertRaises(DartsMlError):
            choose_device(["emulator-5554"], {"ANDROID_SERIAL": "0123abc"})

    def test_one_device_or_none(self):
        self.assertEqual(choose_device(["emulator-5554"], {}), "emulator-5554")
        self.assertIsNone(choose_device([], {}))

    def test_cpuinfo_names_the_cpu_and_its_vector_units(self):
        x86 = cpuinfo("processor\t: 0\nmodel name\t: Android virtual processor\nflags\t\t: fpu sse avx f16c\n"
                      "processor\t: 1\nmodel name\t: other\n")
        self.assertEqual((x86.model, x86.simd), ("Android virtual processor", ("avx", "f16c")))
        arm = cpuinfo("processor\t: 0\nFeatures\t: fp asimd asimddp i8mm\n\nHardware\t: Qualcomm\n")
        self.assertEqual((arm.model, arm.simd), ("Qualcomm", ("asimd", "asimddp", "i8mm")))


class SizeTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _aar(self, entries: dict[str, bytes]) -> Path:
        path = self.folder / "runtime.aar"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return path

    def test_only_native_libraries_under_a_known_abi_are_read(self):
        aar = self._aar({"jni/arm64-v8a/libone.so": b"\0" * 4096, "jni/x86_64/libone.so": os.urandom(2048),
                         "jni/mips/libone.so": b"x", "jni/x86_64/notes.txt": b"x", "classes.jar": b"x",
                         "headers/onnxruntime_c_api.h": b"x"})
        found = {(lib.abi, lib.name): lib for lib in native_libraries(aar)}
        self.assertEqual(set(found), {("arm64-v8a", "libone.so"), ("x86_64", "libone.so")})
        self.assertEqual(found["arm64-v8a", "libone.so"].size, 4096)
        self.assertLess(found["arm64-v8a", "libone.so"].deflated, 100)
        self.assertGreater(found["x86_64", "libone.so"].deflated, 2000)

    def test_each_abi_is_summed_and_a_missing_one_is_named(self):
        aar = self._aar({"jni/arm64-v8a/liba.so": b"\0" * 2**20, "jni/arm64-v8a/libb.so": b"\0" * 2**20})
        lines = size_lines({"Runtime 1.0": native_libraries(aar)})
        arm = next(line for line in lines if "arm64-v8a" in line)
        self.assertIn("2.00 MiB", arm)
        self.assertIn("liba.so 1.00 MiB, libb.so 1.00 MiB", arm)
        self.assertTrue(any("x86 " in line and "not shipped" in line for line in lines))


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = self.folder / "source" / "runtime-1.0.aar"
        self.source.parent.mkdir()
        self.source.write_bytes(b"pinned bytes")
        self.cache = self.folder / "cache"

    def _artifact(self, sha256: str) -> Artifact:
        return Artifact("runtime-1.0", self.source.as_uri(), sha256)

    def test_a_download_matching_its_pin_is_cached(self):
        pinned = hashlib.sha256(b"pinned bytes").hexdigest()
        with contextlib.redirect_stderr(io.StringIO()):
            path = fetch(self._artifact(pinned), self.cache)
        self.assertEqual(path, self.cache / "runtime-1.0" / "runtime-1.0.aar")
        self.source.unlink()
        self.assertEqual(fetch(self._artifact(pinned), self.cache), path)

    def test_a_download_that_differs_from_its_pin_is_refused_and_not_kept(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(DartsMlError) as caught:
            fetch(self._artifact("0" * 64), self.cache)
        self.assertIn("not the pinned", str(caught.exception))
        self.assertEqual(list((self.cache / "runtime-1.0").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
