package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Point
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

/**
 * A Dart as the screen shows it. [number] counts from the top of the Photo, never throw order, and
 * stays with the Dart through corrections. [at] is its marker in Photo pixels, null where the Dart has
 * no place: a Miss added with no tap, or a Visit entered by hand. A [corrected] Dart's Score is the
 * player's, so it is drawn as a badge alone: at its bed's centre, or for a Miss where it was or was
 * tapped.
 */
data class ShownDart(
    val number: Int,
    val at: Point?,
    val score: Score,
    val unsure: Boolean = false,
    val corrected: Boolean = false,
)

val List<ShownDart>.total: Int get() = sumOf { it.score.value }

/** Where the Visit tab is in a Visit's life (phase-1.md §4). */
sealed interface VisitPhase {
    data object Empty : VisitPhase

    data object Reading : VisitPhase

    data class NoBoard(
        val photo: File,
        val width: Int,
        val height: Int,
    ) : VisitPhase

    /** A Visit with Darts to show and correct: read from the Photo, or entered by hand. */
    sealed interface Shown : VisitPhase {
        val photo: File
        val width: Int
        val height: Int
        val darts: List<ShownDart>
    }

    /** [toBoard] maps the Photo's pixels to Board millimetres. */
    data class Scored(
        override val photo: File,
        override val width: Int,
        override val height: Int,
        val crop: Crop,
        val toBoard: Homography,
        override val darts: List<ShownDart>,
    ) : Shown

    /** No Board was found and the Score was entered on the keypad (D6): the whole Photo, no markers. */
    data class Entered(
        override val photo: File,
        override val width: Int,
        override val height: Int,
        override val darts: List<ShownDart>,
    ) : Shown
}

fun VisitPhase.Shown.withDarts(darts: List<ShownDart>): VisitPhase.Shown =
    when (this) {
        is VisitPhase.Scored -> copy(darts = darts)
        is VisitPhase.Entered -> copy(darts = darts)
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
            .mapIndexed { i, dart -> ShownDart(i + 1, Point(dart.x, dart.y), dart.score, dart.unsure) }
    return VisitPhase.Scored(photo, reading.width, reading.height, crop, toBoard, darts)
}
