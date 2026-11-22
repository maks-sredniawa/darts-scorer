package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.Decoding
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score

/**
 * The keypad sheet's selection (phase-1.md §3). [ring] is the ring row's key, Single, Double or
 * Treble; [number] the segment picked. [dart] is the number of the Dart being changed, null for a new
 * one. [near] is where on the Board, in millimetres, the Dart was or the tap landed: it picks which
 * of a segment's two single beds a single goes to. [restorable] offers *Back to the app's reading*,
 * for a Dart that differs from what the model read.
 */
data class Keypad(
    val dart: Int?,
    val ring: Ring = Ring.SINGLE,
    val number: Int? = null,
    val bullOrMiss: Ring? = null,
    val near: Point? = null,
    val restorable: Boolean = false,
) {
    /** Null until a number, a Bull or Miss is picked. */
    val score: Score? get() = bullOrMiss?.let(::Score) ?: number?.let { Score(ring, it) }

    fun withRing(ring: Ring): Keypad {
        require(ring in RING_ROW)
        return if (bullOrMiss != null) copy(ring = ring, bullOrMiss = null, number = null) else copy(ring = ring)
    }

    fun withNumber(number: Int): Keypad = copy(number = number, bullOrMiss = null)

    fun withBullOrMiss(bullOrMiss: Ring): Keypad {
        require(bullOrMiss in BULLS_AND_MISS)
        return copy(ring = Ring.SINGLE, number = null, bullOrMiss = bullOrMiss)
    }

    companion object {
        val RING_ROW = listOf(Ring.SINGLE, Ring.DOUBLE, Ring.TREBLE)
        val BULLS_AND_MISS = listOf(Ring.OUTER_BULL, Ring.BULL, Ring.MISS)

        fun showing(
            dart: Int?,
            score: Score,
            near: Point?,
        ): Keypad =
            if (score.ring in RING_ROW) {
                Keypad(dart, ring = score.ring, number = score.number, near = near)
            } else {
                Keypad(dart, bullOrMiss = score.ring, near = near)
            }
    }
}

/** phase-1.md §3's corrections, on the Darts a result shows. */
object Correction {
    const val MOST_DARTS = Decoding.MOST_ENTRIES

    fun open(
        dart: ShownDart,
        toBoard: Homography?,
    ): Keypad =
        Keypad
            .showing(dart.number, dart.score, dart.at?.let { toBoard?.project(it) })
            .copy(restorable = dart.differsFromRead)

    /** The keypad for a new Dart where the Photo was tapped, the bed under the finger preselected. */
    fun openAt(
        photo: Point,
        toBoard: Homography,
    ): Keypad {
        val near = toBoard.project(photo)
        return Keypad.showing(null, Board.score(near), near)
    }

    fun canAdd(darts: List<ShownDart>): Boolean = darts.size < MOST_DARTS

    /** A tap on the Photo can place a Dart while there is room, or a filled Miss to take over. */
    fun canPlace(darts: List<ShownDart>): Boolean = canAdd(darts) || darts.any { it.filled }

    /** Up to three, each Dart the model did not find a Miss to check (phase-1.md §3, *Fewer than three found*). */
    fun withMisses(darts: List<ShownDart>): List<ShownDart> =
        (darts + freeNumbers(darts).map { ShownDart(it, null, Score.MISS, unsure = true, filled = true) })
            .sortedBy { it.number }

    /**
     * [keypad]'s Score committed: a new Dart takes the lowest free number, or a filled Miss's place when
     * none is free; a changed one moves to its
     * bed's centre, or stays where it was or was tapped when it is a Miss, and is drawn as a badge
     * alone; the same Score only confirms it. Either way it is no longer unsure. Unchanged when
     * nothing is picked.
     */
    fun commit(
        darts: List<ShownDart>,
        keypad: Keypad,
        toBoard: Homography?,
    ): List<ShownDart> {
        val score = keypad.score ?: return darts
        val place = if (score.ring == Ring.MISS) keypad.near else Board.bedCentre(score, keypad.near)
        val placed = toBoard?.let { board -> place?.let(board.inverse()::project) }
        val existing = darts.firstOrNull { it.number == keypad.dart }
        val committed =
            when {
                existing == null -> {
                    if (!canPlace(darts)) return darts
                    val number = freeNumbers(darts).firstOrNull() ?: darts.last { it.filled }.number
                    ShownDart(number, placed, score, corrected = true)
                }
                existing.score == score -> existing.copy(unsure = false, filled = false)
                else ->
                    existing.copy(
                        at = placed,
                        score = score,
                        unsure = false,
                        corrected = true,
                        moved = false,
                        filled = false,
                    )
            }
        return (darts.filter { it.number != committed.number } + committed).sortedBy { it.number }
    }

    /**
     * Dart [number]'s ring dragged to [at], in Photo pixels: its Score read from there, no longer
     * unsure. A drop [nearRead], on the model's point, restores the reading if it scores the same.
     */
    fun move(
        darts: List<ShownDart>,
        number: Int,
        at: Point,
        toBoard: Homography,
        nearRead: Boolean = false,
    ): List<ShownDart> {
        val dart = darts.firstOrNull { it.number == number } ?: return darts
        if (snapsBack(dart, at, toBoard, nearRead)) return backToReading(darts, number)
        val moved =
            dart.copy(
                at = at,
                score = Board.score(toBoard.project(at)),
                unsure = false,
                corrected = true,
                moved = true,
            )
        return darts.map { if (it.number == number) moved else it }
    }

    fun snapsBack(
        dart: ShownDart,
        at: Point,
        toBoard: Homography,
        nearRead: Boolean,
    ): Boolean = nearRead && dart.read?.score == Board.score(toBoard.project(at))

    fun backToReading(
        darts: List<ShownDart>,
        number: Int,
    ): List<ShownDart> = darts.map { if (it.number == number) it.asRead else it }

    fun remove(
        darts: List<ShownDart>,
        number: Int,
    ): List<ShownDart> = darts.filter { it.number != number }.renumbered()

    fun restore(
        darts: List<ShownDart>,
        dart: ShownDart,
    ): List<ShownDart> =
        if (!canAdd(darts)) {
            darts
        } else {
            (darts.map { if (it.number >= dart.number) it.copy(number = it.number + 1) else it } + dart).renumbered()
        }

    fun focusAfterRemoving(
        darts: List<ShownDart>,
        removed: Int,
    ): VisitFocus = darts.firstOrNull { it.number >= removed }?.let { VisitFocus.Chip(it.number) } ?: VisitFocus.AddDart

    /** With three shown *Add a Dart* is hidden, so focus returns to the Miss a tap would have taken. */
    fun focusAfterDismissing(darts: List<ShownDart>): VisitFocus {
        if (canAdd(darts)) return VisitFocus.AddDart
        return VisitFocus.Chip((darts.lastOrNull { it.filled } ?: darts.first()).number)
    }

    private fun List<ShownDart>.renumbered(): List<ShownDart> =
        sortedBy { it.number }.mapIndexed { i, dart -> dart.copy(number = i + 1) }

    private fun freeNumbers(darts: List<ShownDart>): List<Int> =
        (1..MOST_DARTS).filter { n ->
            darts.none {
                it.number ==
                    n
            }
        }
}

sealed interface VisitFocus {
    data class Chip(
        val number: Int,
    ) : VisitFocus

    data object AddDart : VisitFocus

    data object EnterScore : VisitFocus
}
