package app.dartsscorer.scoring

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.sin

/** ADR-0008's Board in millimetres: x to the right, y up, the bull at the origin. A port of `ml/`'s `board.py`. */
object Board {
    const val WIRE_MM = 1.5
    val SEGMENTS = intArrayOf(20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
    val SEGMENT_DEGREES = 360.0 / SEGMENTS.size

    val BULL_RING = Wire("bull", 6.35, 6.35 + WIRE_MM)
    val OUTER_BULL_RING = Wire("25", 15.9, 15.9 + WIRE_MM)
    val INNER_TREBLE = Wire("ti", 99.4 - 2 * WIRE_MM, 99.4 - WIRE_MM)
    val OUTER_TREBLE = Wire("to", 107.4 - WIRE_MM, 107.4)
    val INNER_DOUBLE = Wire("di", 162.0 - 2 * WIRE_MM, 162.0 - WIRE_MM)
    val OUTER_DOUBLE = Wire("do", 170.0 - WIRE_MM, 170.0)

    private val CALIBRATION_WIRES = listOf(OUTER_DOUBLE, INNER_DOUBLE, OUTER_TREBLE, INNER_TREBLE)

    /** The 80 crossings, in the order of the model's Calibration channels. */
    val CALIBRATION_POINTS: List<CalibrationPoint> =
        CALIBRATION_WIRES.flatMap { wire ->
            SEGMENTS.indices.map { i ->
                CalibrationPoint(
                    "${wire.name}-${SEGMENTS[i]}-${SEGMENTS[(i + 1) % SEGMENTS.size]}",
                    wire,
                    boundaryDegrees(i),
                )
            }
        }

    fun boundaryDegrees(index: Int): Double = (SEGMENT_DEGREES / 2 + SEGMENT_DEGREES * index).mod(360.0)

    fun point(
        radiusMm: Double,
        degrees: Double,
    ): Point {
        val radians = Math.toRadians(degrees)
        return Point(radiusMm * sin(radians), radiusMm * cos(radians))
    }

    fun segmentAt(
        xMm: Double,
        yMm: Double,
    ): Int {
        val degrees = Math.toDegrees(atan2(xMm, yMm)).mod(360.0)
        val shifted = (degrees + SEGMENT_DEGREES / 2).mod(360.0)
        return SEGMENTS[floor(shifted / SEGMENT_DEGREES).toInt() % SEGMENTS.size]
    }

    fun score(
        xMm: Double,
        yMm: Double,
    ): Score {
        val radius = hypot(xMm, yMm)
        return when {
            radius < BULL_RING.centreMm -> Score.BULL
            radius < OUTER_BULL_RING.centreMm -> Score.OUTER_BULL
            radius >= OUTER_DOUBLE.centreMm -> Score.MISS
            radius < INNER_TREBLE.centreMm -> Score(Ring.SINGLE, segmentAt(xMm, yMm))
            radius < OUTER_TREBLE.centreMm -> Score(Ring.TREBLE, segmentAt(xMm, yMm))
            radius < INNER_DOUBLE.centreMm -> Score(Ring.SINGLE, segmentAt(xMm, yMm))
            else -> Score(Ring.DOUBLE, segmentAt(xMm, yMm))
        }
    }

    fun score(mm: Point): Score = score(mm.x, mm.y)

    /**
     * The middle of [score]'s bed, where a Dart set by hand is drawn (phase-1.md §3); null for a Miss,
     * which has no bed. A single has two beds, and the one nearer [near] is taken, the outer one
     * without it. An outer bull keeps [near]'s direction.
     */
    fun bedCentre(
        score: Score,
        near: Point? = null,
    ): Point? {
        val nearRadius = near?.let { hypot(it.x, it.y) }
        return when (score.ring) {
            Ring.MISS -> null
            Ring.BULL -> Point(0.0, 0.0)
            Ring.OUTER_BULL -> {
                val degrees = near?.takeIf { nearRadius != 0.0 }?.let { Math.toDegrees(atan2(it.x, it.y)) } ?: 0.0
                point(between(BULL_RING, OUTER_BULL_RING), degrees)
            }
            Ring.TREBLE -> point(between(INNER_TREBLE, OUTER_TREBLE), segmentDegrees(score.number))
            Ring.DOUBLE -> point(between(INNER_DOUBLE, OUTER_DOUBLE), segmentDegrees(score.number))
            Ring.SINGLE -> {
                val inner = between(OUTER_BULL_RING, INNER_TREBLE)
                val outer = between(OUTER_TREBLE, INNER_DOUBLE)
                val radius =
                    if (nearRadius != null && abs(nearRadius - inner) < abs(nearRadius - outer)) inner else outer
                point(radius, segmentDegrees(score.number))
            }
        }
    }

    private fun between(
        inside: Wire,
        outside: Wire,
    ): Double = (inside.centreMm + outside.centreMm) / 2

    private fun segmentDegrees(number: Int): Double {
        val index = SEGMENTS.indexOf(number)
        require(index >= 0) { "no segment $number" }
        return SEGMENT_DEGREES * index
    }
}

data class Point(
    val x: Double,
    val y: Double,
)

data class Wire(
    val name: String,
    val innerMm: Double,
    val outerMm: Double,
) {
    val centreMm: Double get() = (innerMm + outerMm) / 2
}

data class CalibrationPoint(
    val name: String,
    val wire: Wire,
    val degrees: Double,
) {
    val mm: Point get() = Board.point(wire.centreMm, degrees)
}

enum class Ring(
    val token: String,
) {
    MISS("miss"),
    SINGLE("S"),
    DOUBLE("D"),
    TREBLE("T"),
    OUTER_BULL("25"),
    BULL("50"),
}

data class Score(
    val ring: Ring,
    val number: Int = 0,
) {
    val value: Int
        get() =
            when (ring) {
                Ring.SINGLE -> number
                Ring.DOUBLE -> 2 * number
                Ring.TREBLE -> 3 * number
                Ring.MISS -> 0
                Ring.OUTER_BULL -> 25
                Ring.BULL -> 50
            }

    /** `T20`, `25`, `miss`: the token `ml/` writes. */
    val token: String
        get() =
            when (ring) {
                Ring.SINGLE, Ring.DOUBLE, Ring.TREBLE -> "${ring.token}$number"
                else -> ring.token
            }

    companion object {
        val MISS = Score(Ring.MISS)
        val OUTER_BULL = Score(Ring.OUTER_BULL)
        val BULL = Score(Ring.BULL)
    }
}
