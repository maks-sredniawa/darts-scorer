package app.dartsscorer.scoring

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.sqrt

/** A decoded Photo as packed `0xRRGGBB` pixels, row by row; the alpha byte is ignored. */
class RgbImage(
    val width: Int,
    val height: Int,
    val pixels: IntArray,
) {
    init {
        require(width > 0 && height > 0 && pixels.size == width * height)
    }
}

/**
 * `ml/`'s `augment.letterbox`, `framing` and `warp`, and `training_data.normalise`. The warp follows
 * Pillow's arithmetic rather than Android's: its antialiased bilinear reduce in 22-bit fixed point,
 * then its perspective transform's bilinear sample truncated to a byte, so the model sees the input
 * Python fed it (phase-1.md §1).
 */
object Warp {
    const val CROP_FILL = 0.8
    private val MEAN = floatArrayOf(0.485f, 0.456f, 0.406f)
    private val STD = floatArrayOf(0.229f, 0.224f, 0.225f)
    private val RING = Board.CALIBRATION_POINTS.filter { it.wire == Board.OUTER_DOUBLE }.map { it.mm }

    fun letterbox(
        width: Int,
        height: Int,
        size: Int,
    ): Homography {
        val scale = size.toDouble() / maxOf(width, height)
        return affine(scale, (size - scale * width) / 2, (size - scale * height) / 2)
    }

    fun framing(
        boardToPhoto: Homography,
        size: Int,
        fill: Double = CROP_FILL,
    ): Homography {
        val ring = RING.map(boardToPhoto::project)
        val lowX = ring.minOf { it.x }
        val highX = ring.maxOf { it.x }
        val lowY = ring.minOf { it.y }
        val highY = ring.maxOf { it.y }
        val scale = fill * size / maxOf(highX - lowX, highY - lowY)
        val centreX = (lowX + highX) / 2
        val centreY = (lowY + highY) / 2
        return affine(scale, size / 2.0 + 0.0 - scale * centreX, size / 2.0 + 0.0 - scale * centreY)
    }

    private fun affine(
        scale: Double,
        dx: Double,
        dy: Double,
    ) = Homography(doubleArrayOf(scale, 0.0, dx, 0.0, scale, dy, 0.0, 0.0, 1.0))

    /** The model's input: [photo] mapped by [matrix] into size×size, normalised, channel-major. */
    fun input(
        photo: RgbImage,
        matrix: Homography,
        size: Int,
    ): FloatArray {
        var source = photo
        var toInput = matrix
        val shrink = shrink(matrix, photo.width, photo.height)
        if (shrink < 1) {
            val reducedWidth = maxOf(1, Math.rint(photo.width * shrink).toInt())
            val reducedHeight = maxOf(1, Math.rint(photo.height * shrink).toInt())
            val scale =
                Homography(
                    doubleArrayOf(
                        reducedWidth.toDouble() / photo.width,
                        0.0,
                        0.0,
                        0.0,
                        reducedHeight.toDouble() / photo.height,
                        0.0,
                        0.0,
                        0.0,
                        1.0,
                    ),
                )
            source = resize(photo, reducedWidth, reducedHeight)
            toInput = matrix * scale.inverse()
        }
        return transform(source, toInput.inverse().scaledToUnitCorner(), size)
    }

    internal fun shrink(
        matrix: Homography,
        width: Int,
        height: Int,
    ): Double {
        val cx = width / 2.0
        val cy = height / 2.0
        val near = matrix.project(cx, cy)
        val right = matrix.project(cx + 1, cy)
        val down = matrix.project(cx, cy + 1)
        val a = right.x - near.x
        val b = down.x - near.x
        val c = right.y - near.y
        val d = down.y - near.y
        return sqrt(abs(a * d - b * c))
    }

    private const val PRECISION_BITS = 32 - 8 - 2

    private class Taps(
        val first: IntArray,
        val count: IntArray,
        val weights: IntArray,
        val size: Int,
    )

    /** Pillow's `precompute_coeffs` for its bilinear filter, then `normalize_coeffs_8bpc`. */
    private fun taps(
        inSize: Int,
        outSize: Int,
    ): Taps {
        val scale = inSize.toDouble() / outSize
        val filterScale = maxOf(scale, 1.0)
        val support = 1.0 * filterScale
        val size = ceil(support).toInt() * 2 + 1
        val first = IntArray(outSize)
        val count = IntArray(outSize)
        val weights = IntArray(outSize * size)
        val raw = DoubleArray(size)
        for (xx in 0 until outSize) {
            val centre = 0.0 + (xx + 0.5) * scale
            val ss = 1.0 / filterScale
            val xmin = maxOf((centre - support + 0.5).toInt(), 0)
            val xmax = minOf((centre + support + 0.5).toInt(), inSize) - xmin
            var total = 0.0
            for (x in 0 until xmax) {
                val t = abs((x + xmin - centre + 0.5) * ss)
                val w = if (t < 1.0) 1.0 - t else 0.0
                raw[x] = w
                total += w
            }
            for (x in 0 until xmax) {
                val w = if (total != 0.0) raw[x] / total else raw[x]
                weights[xx * size + x] =
                    if (w <
                        0
                    ) {
                        (-0.5 + w * (1 shl PRECISION_BITS)).toInt()
                    } else {
                        (0.5 + w * (1 shl PRECISION_BITS)).toInt()
                    }
            }
            first[xx] = xmin
            count[xx] = xmax
        }
        return Taps(first, count, weights, size)
    }

    private fun clip8(sum: Int): Int = (sum shr PRECISION_BITS).coerceIn(0, 255)

    /** Pillow's `Image.resize(..., BILINEAR, reducing_gap=None)`: horizontal pass, then vertical. */
    internal fun resize(
        photo: RgbImage,
        width: Int,
        height: Int,
    ): RgbImage {
        var image = photo
        if (width != image.width) {
            val taps = taps(image.width, width)
            val out = IntArray(width * image.height)
            for (y in 0 until image.height) {
                val row = y * image.width
                for (xx in 0 until width) {
                    out[y * width + xx] =
                        sample(taps, xx) { i -> image.pixels[row + i] }
                }
            }
            image = RgbImage(width, image.height, out)
        }
        if (height != image.height) {
            val taps = taps(image.height, height)
            val out = IntArray(image.width * height)
            for (yy in 0 until height) {
                for (x in 0 until image.width) {
                    out[yy * image.width + x] = sample(taps, yy) { i -> image.pixels[i * image.width + x] }
                }
            }
            image = RgbImage(image.width, height, out)
        }
        return image
    }

    private inline fun sample(
        taps: Taps,
        index: Int,
        pixel: (Int) -> Int,
    ): Int {
        val start = taps.first[index]
        val base = index * taps.size
        var r = 1 shl (PRECISION_BITS - 1)
        var g = r
        var b = r
        for (i in 0 until taps.count[index]) {
            val p = pixel(start + i)
            val k = taps.weights[base + i]
            r += ((p shr 16) and 0xFF) * k
            g += ((p shr 8) and 0xFF) * k
            b += (p and 0xFF) * k
        }
        return (clip8(r) shl 16) or (clip8(g) shl 8) or clip8(b)
    }

    /**
     * Pillow's `Image.transform(PERSPECTIVE, BILINEAR)` into size×size, with [inputToPhoto] mapping an
     * output pixel's centre back into [photo]; a sample outside the Photo is black, as Pillow fills it.
     */
    private fun transform(
        photo: RgbImage,
        inputToPhoto: Homography,
        size: Int,
    ): FloatArray {
        val a = inputToPhoto.values
        val plane = size * size
        val out = FloatArray(3 * plane)
        val channel = IntArray(3)
        for (yo in 0 until size) {
            for (xo in 0 until size) {
                val xi = xo + 0.5
                val yi = yo + 0.5
                val w = a[6] * xi + a[7] * yi + 1
                val x = (a[0] * xi + a[1] * yi + a[2]) / w
                val y = (a[3] * xi + a[4] * yi + a[5]) / w
                bilinear(photo, x, y, channel)
                val at = yo * size + xo
                for (c in 0..2) out[c * plane + at] = (channel[c].toFloat() / 255f - MEAN[c]) / STD[c]
            }
        }
        return out
    }

    private fun bilinear(
        photo: RgbImage,
        xIn: Double,
        yIn: Double,
        into: IntArray,
    ) {
        if (!(xIn >= 0.0 && xIn < photo.width && yIn >= 0.0 && yIn < photo.height)) {
            into.fill(0)
            return
        }
        val x = xIn - 0.5
        val y = yIn - 0.5
        val xFloor = floor(x).toInt()
        val yFloor = floor(y).toInt()
        val dx = x - xFloor
        val dy = y - yFloor
        val x0 = xFloor.coerceIn(0, photo.width - 1)
        val x1 = (xFloor + 1).coerceIn(0, photo.width - 1)
        val row0 = yFloor.coerceIn(0, photo.height - 1) * photo.width
        val hasRow1 = yFloor + 1 in 0 until photo.height
        val row1 = (yFloor + 1) * photo.width
        for (c in 0..2) {
            val shift = 16 - 8 * c
            val a0 = (photo.pixels[row0 + x0] shr shift) and 0xFF
            val b0 = (photo.pixels[row0 + x1] shr shift) and 0xFF
            val v1 = a0 + (b0 - a0) * dx
            val v2 =
                if (hasRow1) {
                    val a1 = (photo.pixels[row1 + x0] shr shift) and 0xFF
                    val b1 = (photo.pixels[row1 + x1] shr shift) and 0xFF
                    a1 + (b1 - a1) * dx
                } else {
                    v1
                }
            into[c] = (v1 + (v2 - v1) * dy).toInt()
        }
    }
}
