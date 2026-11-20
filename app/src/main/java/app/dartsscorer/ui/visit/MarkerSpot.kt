package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import kotlin.math.sqrt

/** A Dart's marker on the screen: [at] is the Dart, [badge] its number's badge, keyline included. */
internal data class MarkerSpot(
    val at: Offset,
    val badge: Rect,
)

internal fun badgeBeside(
    at: Offset,
    badge: Size,
    ringOuter: Float,
    canvas: Size,
): Rect {
    val halfWidth = badge.width / 2
    val halfHeight = badge.height / 2
    val reach = (ringOuter + halfHeight) / sqrt(2f)
    val toCentre = reach + halfWidth - halfHeight
    val right = at.x + toCentre + halfWidth <= canvas.width
    val up = at.y - reach - halfHeight >= 0
    val beside =
        Offset(
            if (right) at.x + toCentre else at.x - toCentre,
            if (up) at.y - reach else at.y + reach,
        )
    return badgeOn(beside, badge, canvas)
}

internal fun badgeOn(
    centre: Offset,
    badge: Size,
    canvas: Size,
): Rect {
    val halfWidth = badge.width / 2
    val halfHeight = badge.height / 2
    val inside =
        Offset(
            centre.x.coerceAtMost(canvas.width - halfWidth).coerceAtLeast(halfWidth),
            centre.y.coerceAtMost(canvas.height - halfHeight).coerceAtLeast(halfHeight),
        )
    return Rect(inside - Offset(halfWidth, halfHeight), badge)
}

/** The index of the marker a [tap] opens: one whose badge it is inside or within [reach] of its Dart, the nearest winning. */
internal fun List<MarkerSpot>.hitBy(
    tap: Offset,
    reach: Float,
): Int? =
    withIndex()
        .mapNotNull { (index, spot) ->
            val distance = if (spot.badge.contains(tap)) 0f else (spot.at - tap).getDistance()
            (index to distance).takeIf { distance <= reach }
        }.minByOrNull { it.second }
        ?.first
