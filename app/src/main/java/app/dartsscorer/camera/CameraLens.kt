package app.dartsscorer.camera

import kotlin.math.atan

/** Wider than this, a lens is an ultra-wide, whose bend the Board's homography cannot take (ADR-0009, decision 7). */
const val ULTRA_WIDE_DEGREES = 100.0

fun horizontalFieldOfView(
    focalLengthMm: Float,
    sensorWidthMm: Float,
): Double = Math.toDegrees(2 * atan(sensorWidthMm / (2.0 * focalLengthMm)))

fun isUltraWide(
    focalLengthMm: Float,
    sensorWidthMm: Float,
): Boolean = horizontalFieldOfView(focalLengthMm, sensorWidthMm) > ULTRA_WIDE_DEGREES
