package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.Score
import app.dartsscorer.scoring.Warp
import java.io.File

/** A rectangle of the Photo, in its pixels. */
data class Crop(
    val left: Double,
    val top: Double,
    val right: Double,
    val bottom: Double,
) {
    val width: Double get() = right - left
    val height: Double get() = bottom - top
}

/** A Dart as the screen shows it: [number] counts from the top of the Photo, never throw order. */
data class ShownDart(
    val number: Int,
    val x: Double,
    val y: Double,
    val score: Score,
    val unsure: Boolean,
)

/** Where the Visit tab is in a Visit's life (phase-1.md §4). */
sealed interface VisitPhase {
    data object Empty : VisitPhase

    data object Reading : VisitPhase

    data class NoBoard(
        val photo: File,
        val width: Int,
        val height: Int,
    ) : VisitPhase

    data class Scored(
        val photo: File,
        val width: Int,
        val height: Int,
        val crop: Crop,
        val darts: List<ShownDart>,
    ) : VisitPhase {
        val total: Int get() = darts.sumOf { it.score.value }
    }
}

private val RIM = (0 until 72).map { Board.point(Board.OUTER_DOUBLE.outerMm, it * 5.0) }

fun phaseOf(
    photo: File,
    reading: PhotoReading,
): VisitPhase {
    val toBoard = reading.located.toBoard ?: return VisitPhase.NoBoard(photo, reading.width, reading.height)
    // The window the second pass read the Darts in, so the crop shows what the model saw.
    val toPhoto = toBoard.inverse()
    val rim = RIM.map(toPhoto::project)
    val centreX = (rim.minOf { it.x } + rim.maxOf { it.x }) / 2
    val centreY = (rim.minOf { it.y } + rim.maxOf { it.y }) / 2
    val half =
        maxOf(rim.maxOf { it.x } - rim.minOf { it.x }, rim.maxOf { it.y } - rim.minOf { it.y }) / Warp.CROP_FILL / 2
    val crop =
        Crop(
            left = (centreX - half).coerceAtLeast(0.0),
            top = (centreY - half).coerceAtLeast(0.0),
            right = (centreX + half).coerceAtMost(reading.width.toDouble()),
            bottom = (centreY + half).coerceAtMost(reading.height.toDouble()),
        )
    val darts =
        reading.located.darts
            .sortedWith(compareBy({ it.y }, { it.x }))
            .mapIndexed { i, dart -> ShownDart(i + 1, dart.x, dart.y, dart.score, dart.unsure) }
    return VisitPhase.Scored(photo, reading.width, reading.height, crop, darts)
}
