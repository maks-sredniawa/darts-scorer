package app.dartsscorer.camera

import kotlin.math.atan

/**
 * Wider than this across, a lens is an ultra-wide, whose bend the Board's homography cannot take
 * (ADR-0009, decision 7). Main lenses run about 65–80°; a 16 mm-equivalent ultra-wide is about 97°.
 */
const val ULTRA_WIDE_DEGREES = 90.0

fun horizontalFieldOfView(
    focalLengthMm: Float,
    sensorWidthMm: Float,
): Double = Math.toDegrees(2 * atan(sensorWidthMm / (2.0 * focalLengthMm)))

/**
 * Which of the back cameras, in CameraX's order, the Mounted camera uses: the first that is not an
 * ultra-wide. A phone's only back camera is its main one whatever it reports, so it is never refused;
 * an emulator's virtual scene reports 104°. A camera whose field of view is unknown is not refused.
 */
fun chooseBackCamera(fieldsOfView: List<Double?>): Int? {
    if (fieldsOfView.size == 1) return 0
    return fieldsOfView.indexOfFirst { it == null || it <= ULTRA_WIDE_DEGREES }.takeIf { it >= 0 }
}
