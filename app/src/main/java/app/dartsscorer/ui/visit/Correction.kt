package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.Decoding
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score

/**
 * The keypad sheet's selection (phase-1.md §3). [ring] is the ring row's key, Single, Double or
 * Treble; [number] the segment picked; [other] a Bull or Miss picked instead of a number, which
 * leaves the ring row unselected. [dart] is the number of the Dart being changed, null for a new
 * one. [near] is where on the Board, in millimetres, the Dart was or the tap landed: it picks which
 * of a segment's two single beds a single goes to.
 */
data class Keypad(
    val dart: Int?,
    val ring: Ring = Ring.SINGLE,
    val number: Int? = null,
    val other: Ring? = null,
    val near: Point? = null,
) {
    /** Null until a number, a Bull or Miss is picked. */
    val score: Score? get() = other?.let(::Score) ?: number?.let { Score(ring, it) }

    fun withRing(ring: Ring): Keypad {
        require(ring in RING_ROW)
        return if (other != null) copy(ring = ring, other = null, number = null) else copy(ring = ring)
    }

    fun withNumber(number: Int): Keypad = copy(number = number, other = null)

    fun withOther(other: Ring): Keypad {
        require(other in OTHERS)
        return copy(ring = Ring.SINGLE, number = null, other = other)
    }

    companion object {
        val RING_ROW = listOf(Ring.SINGLE, Ring.DOUBLE, Ring.TREBLE)
        val OTHERS = listOf(Ring.OUTER_BULL, Ring.BULL, Ring.MISS)

        fun showing(
            dart: Int?,
            score: Score,
            near: Point?,
        ): Keypad =
            if (score.ring in RING_ROW) {
                Keypad(dart, ring = score.ring, number = score.number, near = near)
            } else {
                Keypad(dart, other = score.ring, near = near)
            }
    }
}

/** phase-1.md §3's corrections, on the Darts a result shows. */
object Correction {
    const val MOST_DARTS = Decoding.MOST_ENTRIES

    /** The keypad for an existing Dart, its Score preselected. */
    fun open(
        dart: ShownDart,
        toBoard: Homography?,
    ): Keypad = Keypad.showing(dart.number, dart.score, dart.at?.let { toBoard?.project(it) })

    /** The keypad for a new Dart where the Photo was tapped, the bed under the finger preselected. */
    fun openAt(
        photo: Point,
        toBoard: Homography,
    ): Keypad {
        val near = toBoard.project(photo)
        return Keypad.showing(null, Board.score(near), near)
    }

    fun canAdd(darts: List<ShownDart>): Boolean = darts.size < MOST_DARTS

    /**
     * [keypad]'s Score committed: a new Dart takes the lowest free number; a changed one moves to its
     * bed's centre and is drawn hollow; the same Score only confirms it. Either way it is no longer
     * unsure. Unchanged when nothing is picked yet.
     */
    fun commit(
        darts: List<ShownDart>,
        keypad: Keypad,
        toBoard: Homography?,
    ): List<ShownDart> {
        val score = keypad.score ?: return darts
        val placed = toBoard?.let { board -> Board.bedCentre(score, keypad.near)?.let(board.inverse()::project) }
        val existing = darts.firstOrNull { it.number == keypad.dart }
        val committed =
            when {
                existing == null -> {
                    if (!canAdd(darts)) return darts
                    ShownDart(freeNumber(darts), placed, score, corrected = true)
                }
                existing.score == score -> existing.copy(unsure = false)
                else -> existing.copy(at = placed, score = score, unsure = false, corrected = true)
            }
        return (darts.filter { it.number != committed.number } + committed).sortedBy { it.number }
    }

    fun remove(
        darts: List<ShownDart>,
        number: Int,
    ): List<ShownDart> = darts.filter { it.number != number }

    /** Puts a removed Dart back with its number, unless a new Dart has taken its place since. */
    fun restore(
        darts: List<ShownDart>,
        dart: ShownDart,
    ): List<ShownDart> =
        if (!canAdd(darts) || darts.any { it.number == dart.number }) darts else (darts + dart).sortedBy { it.number }

    /** Where focus goes after [removed] is gone: the next chip, else *Add a Dart*. */
    fun focusAfterRemoving(
        darts: List<ShownDart>,
        removed: Int,
    ): VisitFocus = darts.firstOrNull { it.number > removed }?.let { VisitFocus.Chip(it.number) } ?: VisitFocus.AddDart

    private fun freeNumber(darts: List<ShownDart>): Int = (1..MOST_DARTS).first { n -> darts.none { it.number == n } }
}

/** Where focus is moved once the keypad sheet has closed (phase-1.md §3, *Focus*). */
sealed interface VisitFocus {
    data class Chip(
        val number: Int,
    ) : VisitFocus

    data object AddDart : VisitFocus
}
