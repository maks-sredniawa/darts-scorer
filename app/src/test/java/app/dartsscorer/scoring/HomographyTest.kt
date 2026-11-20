package app.dartsscorer.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import kotlin.math.cos
import kotlin.math.sin

class HomographyTest {
    private val photoToBoard =
        Homography(doubleArrayOf(0.61, -0.08, -230.0, 0.05, -0.57, 190.0, 0.00021, -0.00009, 1.0))
    private val boardToPhoto = photoToBoard.inverse()
    private val crossings = Board.CALIBRATION_POINTS.map { it.mm }

    @Test
    fun aFitOnExactPointsReturnsThemToABillionthOfAMillimetre() {
        val pixels = crossings.map { boardToPhoto.project(it) }
        val fitted = checkNotNull(Homography.fit(pixels, crossings))
        pixels.forEachIndexed { i, pixel ->
            val back = fitted.project(pixel)
            assertEquals(crossings[i].x, back.x, 1e-9)
            assertEquals(crossings[i].y, back.y, 1e-9)
        }
    }

    @Test
    fun ransacKeepsTheSeventyPercentThatAgree() {
        val moved = crossings.indices.filter { it % 10 < 3 }.toSet()
        val calibration =
            crossings.indices.associateWith { i ->
                val mm = crossings[i]
                boardToPhoto.project(if (i in moved) Point(mm.x + 50.0, mm.y) else mm)
            }
        val (toBoard, inliers) = checkNotNull(Decoding.ransac(calibration))
        assertEquals(crossings.indices.filter { it !in moved }, inliers)
        crossings.forEachIndexed { i, mm ->
            val back = toBoard.project(boardToPhoto.project(mm))
            assertEquals(mm.x, back.x, 1e-6)
            assertEquals(mm.y, back.y, 1e-6)
        }
    }

    @Test
    fun fewerThanEightInliersIsNoBoard() {
        val calibration = (0 until 7).associateWith { boardToPhoto.project(crossings[it * 11]) }
        assertNull(Decoding.ransac(calibration))
        val exact = (0 until 7).map { it * 11 }.toSet()
        val scattered =
            crossings.indices.associateWith { i ->
                val mm = crossings[i]
                val away = 40.0 + 13.0 * (i % 7)
                boardToPhoto.project(
                    if (i in
                        exact
                    ) {
                        mm
                    } else {
                        Point(mm.x + away * cos(i * 2.3), mm.y + away * sin(i * 2.3))
                    },
                )
            }
        assertNull(Decoding.ransac(scattered))
    }

    @Test
    fun degeneratePointsAreNotAFit() {
        val line = (0 until 6).map { Point(it.toDouble(), 2.0 * it) }
        assertNull(Homography.fit(line, line))
        assertNull(Homography.fourPoint(line.take(4), line.take(4)))
    }
}
