from __future__ import annotations

import time

_SLEPT_SECONDS = 1.0


def seconds_asleep() -> float:
    awake = time.clock_gettime(time.CLOCK_MONOTONIC)
    return time.clock_gettime(time.CLOCK_BOOTTIME) - awake


def explain_failed_search(error: BaseException, asleep: float) -> str | None:
    if "miopenStatusUnknownError" not in str(error) or asleep < _SLEPT_SECONDS:
        return None
    return (f"MIOpen's kernel search failed, and this computer has slept for {asleep / 3600:.1f} h since it booted. "
            "After a suspend the GPU's timer reads zero, so MIOpen rejects every kernel it tries for a shape it has "
            "not run before; shapes already in its database still run. Restart the computer and run this again "
            "before it sleeps (ml/README.md, Training).")
