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
        val bull = treble.withBullOrMiss(Ring.BULL)
        assertEquals(Score.BULL, bull.score)
        assertNull("a ring after a Bull waits for a number", bull.withRing(Ring.TREBLE).score)
        assertEquals(Score(Ring.TREBLE, 19), bull.withRing(Ring.TREBLE).withNumber(19).score)
        assertEquals(Score(Ring.SINGLE, 7), bull.withNumber(7).score)
        assertEquals(Keypad(2, bullOrMiss = Ring.MISS), Keypad.showing(2, Score.MISS, null))
        assertNull(Keypad(dart = null).score)
    }

    @Test
    fun `a changed Dart moves to its bed's centre through the homography and is drawn as a badge alone`() {
        val darts = listOf(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = true))
        val keypad = Correction.open(darts[0], BOARD).withRing(Ring.SINGLE).withNumber(1)
        val changed = Correction.commit(darts, keypad, BOARD).single()
        assertEquals(Score(Ring.SINGLE, 1), changed.score)
        assertEquals(Score(Ring.SINGLE, 1), Board.score(BOARD.project(changed.at!!)))
        assertTrue(changed.corrected)
        assertFalse(changed.unsure)
    }

    @Test
    fun `a Dart set to Miss stays where it was, drawn as a badge alone`() {
        val darts = listOf(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20)))
        val miss = Correction.commit(darts, Correction.open(darts[0], BOARD).withBullOrMiss(Ring.MISS), BOARD).single()
        assertNear(Point(400.0, 194.0), miss.at!!)
        assertTrue(miss.corrected)
        assertEquals(0, listOf(miss).total)
    }

    @Test
    fun `a Miss added by a tap sits at the tap, and one added with no tap has no marker`() {
        val tapped = Point(400.0, 30.0)
        val atTap = Correction.commit(emptyList(), Correction.openAt(tapped, BOARD).withBullOrMiss(Ring.MISS), BOARD)
        assertNear(tapped, atTap.single().at!!)
        assertTrue(atTap.single().corrected)
        val noTap = Correction.commit(emptyList(), Keypad(dart = null).withBullOrMiss(Ring.MISS), BOARD)
        assertNull(noTap.single().at)
    }

    private fun assertNear(
        expected: Point,
        actual: Point,
    ) = assertTrue("$actual is not $expected", hypot(expected.x - actual.x, expected.y - actual.y) < 1e-6)

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

    @Test
    fun `a dragged Dart scores where it was dropped and keeps the model's reading`() {
        val read = DartRead(Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = true)
        val darts = listOf(ShownDart(1, read.at, read.score, unsure = true, read = read))
        val dropped = Point(400.0 + 2 * 60.0, 400.0)
        val moved = Correction.move(darts, 1, dropped, BOARD).single()
        assertEquals(dropped, moved.at)
        assertEquals(Board.score(Point(60.0, 0.0)), moved.score)
        assertEquals(Score(Ring.SINGLE, 6), moved.score)
        assertFalse(moved.unsure)
        assertTrue(moved.corrected)
        assertTrue(moved.moved)
        assertEquals(read, moved.read)
    }

    @Test
    fun `a keypad change after a drag puts the Dart on its bed's centre and keeps the reading`() {
        val read = DartRead(Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = false)
        val moved =
            Correction.move(
                listOf(ShownDart(1, read.at, read.score, read = read)),
                1,
                Point(520.0, 400.0),
                BOARD,
            )
        val keyed = Correction.commit(moved, Correction.open(moved[0], BOARD).withNumber(11), BOARD).single()
        assertFalse(keyed.moved)
        assertTrue(keyed.corrected)
        assertEquals(read, keyed.read)
    }

    @Test
    fun `back to the app's reading restores it whole, after a drag or a keypad change`() {
        val read = DartRead(Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = true)
        val shown = ShownDart(1, read.at, read.score, unsure = true, read = read)
        val other = ShownDart(2, Point(10.0, 10.0), Score.MISS)
        val moved = Correction.move(listOf(shown, other), 1, Point(520.0, 400.0), BOARD)
        assertEquals(listOf(shown, other), Correction.backToReading(moved, 1))
        val keyed = Correction.commit(listOf(shown), Correction.open(shown, BOARD).withNumber(1), BOARD)
        assertEquals(listOf(shown), Correction.backToReading(keyed, 1))
        assertEquals(listOf(other), Correction.backToReading(listOf(other), 2))
    }

    @Test
    fun `the keypad offers the app's reading only for a Dart that differs from it`() {
        val read = DartRead(Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = false)
        val shown = ShownDart(1, read.at, read.score, read = read)
        assertFalse(Correction.open(shown, BOARD).restorable)
        val moved = Correction.move(listOf(shown), 1, Point(520.0, 400.0), BOARD).single()
        assertTrue(Correction.open(moved, BOARD).restorable)
        val keyed = Correction.commit(listOf(shown), Correction.open(shown, BOARD).withNumber(5), BOARD).single()
        assertTrue(Correction.open(keyed, BOARD).restorable)
        assertFalse(
            "a Dart added by hand has no reading",
            Correction.open(ShownDart(2, null, Score.BULL), BOARD).restorable,
        )
    }

    private companion object {
        /** Photo pixels to Board millimetres: the bull at (400, 400), 2 px a millimetre, y flipped. */
        val BOARD = Homography(doubleArrayOf(0.5, 0.0, -200.0, 0.0, -0.5, 200.0, 0.0, 0.0, 1.0))
    }
}
