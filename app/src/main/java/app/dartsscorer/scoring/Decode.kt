package app.dartsscorer.scoring

import kotlin.math.ceil
import kotlin.math.exp
import kotlin.math.hypot
import kotlin.math.ln

/** One head's logits without the batch axis, channel-major as the model writes them. */
class Tensor3(
    val channels: Int,
    val height: Int,
    val width: Int,
    val data: FloatArray,
) {
    init {
        require(data.size == channels * height * width)
    }

    operator fun get(
        channel: Int,
        y: Int,
        x: Int,
    ): Float = data[(channel * height + y) * width + x]
}

/** The Calibration heatmaps then their two offsets; the Entry heatmap then its two offsets. */
class Heads(
    val board: Tensor3,
    val entry: Tensor3,
) {
    val entryStride: Int get() = Decoding.BOARD_STRIDE * board.width / entry.width
}

data class Peak(
    val x: Double,
    val y: Double,
    val confidence: Double,
) {
    val unsure: Boolean get() = confidence < Decoding.CONFIDENT
}

data class Decoded(
    val calibration: Map<Int, Peak>,
    val entries: List<Peak>,
)

/** A port of `ml/`'s `decode.py`, its constants included. */
object Decoding {
    const val BOARD_STRIDE = 4
    const val THRESHOLD = 0.25
    const val ENTRY_THRESHOLD = 0.25
    const val MOST_ENTRIES = 3
    const val CONFIDENT = 0.5
    const val RANSAC_MM = 3.0
    const val MIN_INLIERS = 8
    const val RANSAC_ROUNDS = 500
    val CALIBRATION_CHANNELS = Board.CALIBRATION_POINTS.size
    private val BOARD_MM = Board.CALIBRATION_POINTS.map { it.mm }

    fun decode(
        heads: Heads,
        threshold: Double = THRESHOLD,
        entryThreshold: Double = ENTRY_THRESHOLD,
    ): Decoded {
        val board = heads.board
        val plane = board.height * board.width
        val calibration = LinkedHashMap<Int, Peak>()
        for (channel in 0 until CALIBRATION_CHANNELS) {
            val start = channel * plane
            var bestLogit = Float.NEGATIVE_INFINITY
            for (i in 0 until plane) bestLogit = maxOf(bestLogit, board.data[start + i])
            val confidence = sigmoid(bestLogit)
            val best = firstWithSigmoid(board.data, start, plane, bestLogit, confidence)
            if (confidence >= threshold) {
                calibration[channel] =
                    peak(best % board.width, best / board.width, confidence, board, CALIBRATION_CHANNELS, BOARD_STRIDE)
            }
        }
        return Decoded(calibration, entries(heads, entryThreshold))
    }

    private fun entries(
        heads: Heads,
        floor: Double,
    ): List<Peak> {
        val entry = heads.entry
        val rows = entry.height
        val columns = entry.width
        val heat = DoubleArray(rows * columns) { sigmoid(entry.data[it]) }
        val found = mutableListOf<Peak>()
        for (y in 0 until rows) {
            for (x in 0 until columns) {
                val value = heat[y * columns + x]
                if (value < floor) continue
                var highest = true
                for (dy in -1..1) {
                    for (dx in -1..1) {
                        val ny = y + dy
                        val nx = x + dx
                        if (ny in 0 until rows &&
                            nx in 0 until columns &&
                            heat[ny * columns + nx] > value
                        ) {
                            highest = false
                        }
                    }
                }
                if (highest) found += peak(x, y, value, entry, 1, heads.entryStride)
            }
        }
        return found
    }

    private fun sigmoid(logit: Float): Double = 1 / (1 + exp(-logit.toDouble()))

    /**
     * numpy's argmax runs on the float64 sigmoid, where distinct large logits round to the same value
     * and the first of them wins; below [SATURATING_LOGIT] only equal logits tie, so only those are
     * checked.
     */
    private fun firstWithSigmoid(
        data: FloatArray,
        start: Int,
        length: Int,
        highest: Float,
        confidence: Double,
    ): Int {
        val lowest = minOf(highest, SATURATING_LOGIT)
        for (i in 0 until length) {
            val logit = data[start + i]
            if (logit >= lowest && sigmoid(logit) == confidence) return i
        }
        return 0
    }

    private const val SATURATING_LOGIT = 15f

    private fun peak(
        x: Int,
        y: Int,
        confidence: Double,
        head: Tensor3,
        offsets: Int,
        stride: Int,
    ) = Peak(
        (x + head[offsets, y, x].toDouble()) * stride,
        (y + head[offsets + 1, y, x].toDouble()) * stride,
        confidence,
    )

    /** The indices of the Entry points kept: the most confident first, at most [MOST_ENTRIES], in their original order. */
    fun keptEntries(confidences: List<Double>): List<Int> =
        confidences.indices
            .sortedByDescending { confidences[it] }
            .takeWhile { confidences[it] >= ENTRY_THRESHOLD }
            .take(MOST_ENTRIES)
            .sorted()

    /** Python's `ransac`: the photo-to-Board homography and the channels it kept, or null for no Board. */
    fun ransac(calibration: Map<Int, Point>): Pair<Homography, List<Int>>? {
        val channels = calibration.keys.sorted()
        if (channels.size < MIN_INLIERS) return null
        val pixels = channels.map { calibration.getValue(it) }
        val board = channels.map { BOARD_MM[it] }
        val random = NumpyRandom()
        var best = BooleanArray(channels.size)
        var bestCount = 0
        var needed = RANSAC_ROUNDS
        var rounds = 0
        while (rounds < minOf(needed, RANSAC_ROUNDS)) {
            rounds += 1
            val pick = random.choice(channels.size, 4)
            val h = Homography.fourPoint(pick.map { pixels[it] }, pick.map { board[it] }) ?: continue
            val inliers = inliers(h, pixels, board)
            val count = inliers.count { it }
            if (count > bestCount) {
                best = inliers
                bestCount = count
                val share = count.toDouble() / channels.size
                needed = if (share >= 1) 1 else ceil(ln(1e-3) / ln(1 - Math.pow(share, 4.0))).toInt()
            }
        }
        if (bestCount < MIN_INLIERS) return null
        val first = fitOn(best, pixels, board) ?: return null
        val inliers = inliers(first, pixels, board)
        if (inliers.count { it } < MIN_INLIERS) return null
        val toBoard = fitOn(inliers, pixels, board) ?: return null
        return toBoard to channels.filterIndexed { i, _ -> inliers[i] }
    }

    private fun fitOn(
        kept: BooleanArray,
        pixels: List<Point>,
        board: List<Point>,
    ): Homography? = Homography.fit(pixels.filterIndexed { i, _ -> kept[i] }, board.filterIndexed { i, _ -> kept[i] })

    private fun inliers(
        h: Homography,
        pixels: List<Point>,
        board: List<Point>,
    ) = BooleanArray(pixels.size) {
        val mapped = h.project(pixels[it])
        hypot(mapped.x - board[it].x, mapped.y - board[it].y) < RANSAC_MM
    }
}
