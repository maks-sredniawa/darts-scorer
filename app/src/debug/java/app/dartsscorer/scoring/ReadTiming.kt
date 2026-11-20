package app.dartsscorer.scoring

import android.util.Log

/** The timing line R2 and R4 read from `logcat` (phase-1.md Readings). */
fun logReadTime(
    millis: Long,
    threads: Int,
) {
    Log.i("PhotoReader", "both passes: $millis ms at $threads threads")
}
