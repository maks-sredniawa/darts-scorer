package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.hypot

class CorrectionTest {
    @Test
    fun `every bed's centre scores as that bed, from anywhere near it`() {
        val nears = listOf(null, Point(0.0, 0.0), Point(0.0, 50.0), Point(-120.0, 40.0), Point(0.0, 200.0))
        val scores =
            Board.SEGMENTS.flatMap { n -> listOf(Ring.SINGLE, Ring.DOUBLE, Ring.TREBLE).map { Score(it, n) } } +
                listOf(Score.OUTER_BULL, Score.BULL)
        scores.forEach { score ->
            nears.forEach { near ->
                assertEquals("$score near $near", score, Board.score(Board.bedCentre(score, near)!!))
            }
        }
    }

    @Test
    fun `a Miss has no bed`() {
        assertNull(Board.bedCentre(Score.MISS, Point(0.0, 200.0)))
    }

    @Test
    fun `a single goes to the single bed nearer the Dart, the outer one with nothing to go on`() {
        val inner = Board.bedCentre(Score(Ring.SINGLE, 20), Point(0.0, 40.0))!!
        val outer = Board.bedCentre(Score(Ring.SINGLE, 20), Point(0.0, 120.0))!!
        assertTrue(hypot(inner.x, inner.y) < Board.INNER_TREBLE.innerMm)
        assertTrue(hypot(outer.x, outer.y) > Board.OUTER_TREBLE.outerMm)
        assertEquals(outer, Board.bedCentre(Score(Ring.SINGLE, 20)))
    }

    @Test
    fun `the keypad shows a Score as a ring and a number, or a Bull or Miss alone`() {
        val treble = Keypad.showing(1, Score(Ring.TREBLE, 20), null)
        assertEquals(Score(Ring.TREBLE, 20), treble.score)
        assertEquals(Score(Ring.DOUBLE, 20), treble.withRing(Ring.DOUBLE).score)
        assertEquals(Score(Ring.TREBLE, 5), treble.withNumber(5).score)
        val bull = treble.withOther(Ring.BULL)
        assertEquals(Score.BULL, bull.score)
        assertNull("a ring after a Bull waits for a number", bull.withRing(Ring.TREBLE).score)
        assertEquals(Score(Ring.TREBLE, 19), bull.withRing(Ring.TREBLE).withNumber(19).score)
        assertEquals(Score(Ring.SINGLE, 7), bull.withNumber(7).score)
        assertEquals(Keypad(2, other = Ring.MISS), Keypad.showing(2, Score.MISS, null))
        assertNull(Keypad(dart = null).score)
    }

    @Test
    fun `a changed Dart moves to its bed's centre through the homography and is drawn hollow`() {
        val darts = listOf(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = true))
        val keypad = Correction.open(darts[0], BOARD).withRing(Ring.SINGLE).withNumber(1)
        val changed = Correction.commit(darts, keypad, BOARD).single()
        assertEquals(Score(Ring.SINGLE, 1), changed.score)
        assertEquals(Score(Ring.SINGLE, 1), Board.score(BOARD.project(changed.at!!)))
        assertTrue(changed.corrected)
        assertFalse(changed.unsure)
    }

    @Test
    fun `a Dart set to Miss loses its marker`() {
        val darts = listOf(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20)))
        val miss = Correction.commit(darts, Correction.open(darts[0], BOARD).withOther(Ring.MISS), BOARD).single()
        assertNull(miss.at)
        assertEquals(0, listOf(miss).total)
    }

    @Test
    fun `nothing picked commits nothing`() {
        val darts = listOf(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20)))
        assertEquals(darts, Correction.commit(darts, Keypad(dart = null), BOARD))
    }

    @Test
    fun `a new Dart takes the lowest free number, and no fourth is added`() {
        val darts =
            listOf(
                ShownDart(1, null, Score(Ring.SINGLE, 1)),
                ShownDart(3, null, Score(Ring.SINGLE, 3)),
            )
        val added = Correction.commit(darts, Keypad(dart = null).withNumber(20), null)
        assertEquals(listOf(1, 2, 3), added.map { it.number })
        assertEquals(24, added.total)
        assertFalse(Correction.canAdd(added))
        assertEquals(added, Correction.commit(added, Keypad(dart = null).withNumber(5), null))
    }

    @Test
    fun `a tap is read through the homography into the bed under it`() {
        val keypad = Correction.openAt(Point(400.0 + 2 * 12.0, 400.0), BOARD)
        assertEquals(Score.OUTER_BULL, keypad.score)
        assertEquals(Point(12.0, 0.0), keypad.near)
        assertEquals(Score.MISS, Correction.openAt(Point(400.0, 30.0), BOARD).score)
    }

    @Test
    fun `a removed Dart is restored in its place unless the Visit has moved on`() {
        val darts = listOf(ShownDart(1, null, Score.BULL), ShownDart(2, null, Score.MISS))
        val removed = Correction.remove(darts, 1)
        assertEquals(darts, Correction.restore(removed, darts[0]))
        assertEquals(VisitFocus.Chip(2), Correction.focusAfterRemoving(removed, 1))
        assertEquals(VisitFocus.AddDart, Correction.focusAfterRemoving(Correction.remove(darts, 2), 2))
        val refilled = Correction.commit(removed, Keypad(dart = null).withNumber(4), null)
        assertEquals(refilled, Correction.restore(refilled, darts[0]))
    }

    private companion object {
        /** Photo pixels to Board millimetres: the bull at (400, 400), 2 px a millimetre, y flipped. */
        val BOARD = Homography(doubleArrayOf(0.5, 0.0, -200.0, 0.0, -0.5, 200.0, 0.0, 0.0, 1.0))
    }
}
