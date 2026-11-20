package app.dartsscorer.ui.visit

import android.content.res.Resources
import app.dartsscorer.R
import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score

internal fun Resources.shortName(score: Score): String =
    when (score.ring) {
        Ring.SINGLE -> getString(R.string.score_short_single, score.number)
        Ring.DOUBLE -> getString(R.string.score_short_double, score.number)
        Ring.TREBLE -> getString(R.string.score_short_treble, score.number)
        Ring.OUTER_BULL -> getString(R.string.score_short_outer_bull)
        Ring.BULL -> getString(R.string.score_short_bull)
        Ring.MISS -> getString(R.string.score_short_miss)
    }

internal fun Resources.spokenName(score: Score): String =
    when (score.ring) {
        Ring.SINGLE -> getString(R.string.score_single, score.number)
        Ring.DOUBLE -> getString(R.string.score_double, score.number)
        Ring.TREBLE -> getString(R.string.score_treble, score.number)
        Ring.OUTER_BULL -> getString(R.string.score_outer_bull)
        Ring.BULL -> getString(R.string.score_bull)
        Ring.MISS -> getString(R.string.score_miss)
    }

internal fun Resources.chipText(dart: ShownDart): String =
    getString(R.string.visit_chip, dart.number, shortName(dart.score), dart.score.value)

internal fun Resources.chipDescription(dart: ShownDart): String {
    val points = getQuantityString(R.plurals.visit_points, dart.score.value, dart.score.value)
    val description = if (dart.unsure) R.string.visit_chip_description_unsure else R.string.visit_chip_description
    return getString(description, chipText(dart), spokenName(dart.score), points)
}

/** What TalkBack reads for a result: the Score, the Darts, then which are unsure. */
internal fun Resources.summary(result: VisitPhase.Shown): String {
    val darts =
        if (result.darts.isEmpty()) {
            getString(R.string.visit_summary_no_darts)
        } else {
            val spoken = result.darts.joinToString(", ") { spokenName(it.score) }
            getQuantityString(R.plurals.visit_summary_darts, result.darts.size, result.darts.size, spoken)
        }
    val unsure = result.darts.filter { it.unsure }.map { getString(R.string.visit_summary_unsure, it.number) }
    return (listOf(getString(R.string.visit_summary_score, result.darts.total), darts) + unsure).joinToString(" ")
}
