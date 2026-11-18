import contextlib
import io
import unittest
from unittest import mock

from darts_ml import cli
from darts_ml.kernel_search import explain_failed_search, seconds_asleep

FAILED = RuntimeError("miopenStatusUnknownError")


class KernelSearchTest(unittest.TestCase):
    def test_a_failed_search_after_a_sleep_is_explained(self):
        explained = explain_failed_search(FAILED, 33127.0)
        self.assertIn("slept for 9.2 h", explained)
        self.assertIn("Restart", explained)

    def test_a_boot_that_never_slept_is_left_to_the_traceback(self):
        self.assertIsNone(explain_failed_search(FAILED, 0.0))

    def test_any_other_error_is_left_to_the_traceback(self):
        self.assertIsNone(explain_failed_search(RuntimeError("CUDA out of memory"), 33127.0))

    def test_the_clocks_never_run_backwards(self):
        self.assertGreaterEqual(seconds_asleep(), 0.0)


class CliTest(unittest.TestCase):
    def run_failing(self, error: Exception, asleep: float):
        stderr = io.StringIO()
        with mock.patch.object(cli, "_paths", side_effect=error), \
             mock.patch.object(cli, "seconds_asleep", return_value=asleep), \
             contextlib.redirect_stderr(stderr):
            return cli.main(["paths"]), stderr.getvalue()

    def test_the_step_ends_with_the_explanation_instead_of_a_traceback(self):
        code, said = self.run_failing(FAILED, 33127.0)
        self.assertEqual(code, 2)
        self.assertIn("darts-ml paths: MIOpen's kernel search failed", said)

    def test_other_runtime_errors_still_raise(self):
        with self.assertRaisesRegex(RuntimeError, "out of memory"):
            self.run_failing(RuntimeError("CUDA out of memory"), 33127.0)
        with self.assertRaisesRegex(RuntimeError, "miopenStatusUnknownError"):
            self.run_failing(FAILED, 0.0)
