package app.dartsscorer.camera

import kotlin.random.Random

/**
 * When the camera screen dims (ADR-0009, decision 10, as amended 2026-11-23): 30 s after the last
 * touch, but only once a capture has been taken while paired, so aiming a stand is never interrupted,
 * and never while the paste field is in use. Times are milliseconds on one monotonic clock.
 */
data class DimTimer(
    val armed: Boolean = false,
    val lastActivity: Long = 0,
    val inputActive: Boolean = false,
) {
    fun captured(
        paired: Boolean,
        now: Long,
    ): DimTimer = if (paired) copy(armed = true, lastActivity = now) else this

    fun touched(now: Long): DimTimer = copy(lastActivity = now)

    fun input(
        active: Boolean,
        now: Long,
    ): DimTimer = copy(inputActive = active, lastActivity = now)

    /** When the screen dims if nothing else happens, or null while it never will. */
    fun dimsAt(): Long? = if (armed && !inputActive) lastActivity + IDLE_MILLIS else null

    companion object {
        const val IDLE_MILLIS = 30_000L
        const val MOVE_MILLIS = 60_000L
    }
}

/**
 * Where the dimmed status line sits, on a grid of [ROWS] by [COLUMNS] inside the safe area. Rows are
 * far enough apart that a move to another row always clears the line's own height.
 */
data class DimSlot(
    val row: Int,
    val column: Int,
) {
    val horizontalBias: Float get() = column - (COLUMNS - 1) / 2f
    val verticalBias: Float get() = row * 2f / (ROWS - 1) - 1f

    /** Another slot, always on another row, so an OLED panel never holds the line in one place. */
    fun next(random: Random): DimSlot {
        val row = (row + 1 + random.nextInt(ROWS - 1)) % ROWS
        return DimSlot(row, random.nextInt(COLUMNS))
    }

    companion object {
        const val ROWS = 5
        const val COLUMNS = 3
        val Start = DimSlot(ROWS / 2, COLUMNS / 2)
    }
}
