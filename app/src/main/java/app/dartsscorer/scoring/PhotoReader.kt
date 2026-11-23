package app.dartsscorer.scoring

/** One pass of the model: a size×size normalised input in, both heads out. */
interface KeypointModel {
    val inputSize: Int

    fun run(input: FloatArray): Heads
}

/** A Dart's Entry point in Photo pixels, and the Score it lands on through the Board found. */
data class FoundDart(
    val x: Double,
    val y: Double,
    val confidence: Double,
    val score: Score,
) {
    val unsure: Boolean get() = confidence < Decoding.CONFIDENT
}

/**
 * What one Photo gave: [toBoard] maps Photo pixels to Board millimetres, null when no Board was found;
 * [calibration] holds the inlier Calibration points by name, in Photo pixels.
 */
data class Located(
    val toBoard: Homography?,
    val calibration: Map<String, Point> = emptyMap(),
    val darts: List<FoundDart> = emptyList(),
) {
    val found: Boolean get() = toBoard != null
}

/**
 * `ml/`'s `locate` for one Photo: letterboxed and read once to find the Board, re-framed on it and
 * read again for the Darts (phase-1.md §0). The class the Visit screen calls, and the one the parity
 * test holds to Python.
 */
class PhotoReader(
    private val model: KeypointModel,
) {
    fun read(photo: RgbImage): Located {
        val size = model.inputSize
        val first = Warp.letterbox(photo.width, photo.height, size)
        val board = located(first, model.run(Warp.input(photo, first, size))).toBoard ?: return Located(null)
        val second = Warp.framing(board.inverse(), size)
        return located(second, model.run(Warp.input(photo, second, size)))
    }

    companion object {
        /** Python's `_board` then `refiltered`, for heads read through [matrix] (Photo → input pixels). */
        fun located(
            matrix: Homography,
            heads: Heads,
        ): Located {
            val decoded = Decoding.decode(heads)
            val back = matrix.inverse()
            val calibration = decoded.calibration.toSortedMap().mapValues { (_, peak) -> back.project(peak.x, peak.y) }
            val (toBoard, inliers) = Decoding.ransac(calibration) ?: return Located(null)
            val entries = decoded.entries.map { back.project(it.x, it.y) }
            val boardMm = entries.map { toBoard.project(it) }
            val keep = Decoding.keptEntries(boardMm, decoded.entries.map { it.confidence })
            return Located(
                toBoard,
                inliers.associate { Board.CALIBRATION_POINTS[it].name to calibration.getValue(it) },
                keep.map { i ->
                    val at = entries[i]
                    FoundDart(at.x, at.y, decoded.entries[i].confidence, Board.score(boardMm[i]))
                },
            )
        }
    }
}
