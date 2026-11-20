package app.dartsscorer.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BoardTest {
    @Test
    fun everyCaseScoresAsPythonScoresIt() {
        val rows =
            Fixtures
                .text("scores.tsv")
                .lines()
                .drop(1)
                .filter(String::isNotBlank)
        assertTrue("the table covers every segment, ring and wire", rows.size > 500)
        val wrong =
            rows.mapNotNull { row ->
                val (x, y, token) = row.split('\t')
                val got = Board.score(x.toDouble(), y.toDouble()).token
                if (got == token) null else "($x, $y): $got, Python $token"
            }
        assertEquals(emptyList<String>(), wrong)
    }

    @Test
    fun eightyCrossingsInTheModelsChannelOrder() {
        val points = Board.CALIBRATION_POINTS
        assertEquals(80, points.size)
        assertEquals("do-20-1", points.first().name)
        assertEquals("ti-5-20", points.last().name)
        assertEquals(169.25, points.first().mm.let { Math.hypot(it.x, it.y) }, 1e-9)
    }

    @Test
    fun valuesFollowTheRing() {
        assertEquals(60, Score(Ring.TREBLE, 20).value)
        assertEquals(32, Score(Ring.DOUBLE, 16).value)
        assertEquals(50, Score.BULL.value)
        assertEquals("25", Score.OUTER_BULL.token)
        assertEquals("miss", Score.MISS.token)
    }
}
