package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size

/**
 * How far the Photo is zoomed into its box: a point at `base` in the unzoomed box is drawn at
 * `base * zoom + pan`. Every change keeps the Photo filling its box.
 */
data class PhotoZoom(
    val zoom: Float = 1f,
    val pan: Offset = Offset.Zero,
) {
    fun toScreen(base: Offset): Offset = base * zoom + pan

    fun toBase(screen: Offset): Offset = (screen - pan) / zoom

    /** Scaled by [factor] about [centroid], which stays under the fingers. */
    fun zoomedAbout(
        centroid: Offset,
        factor: Float,
        box: Size,
    ): PhotoZoom {
        val next = (zoom * factor).coerceIn(MIN_ZOOM, MAX_ZOOM)
        return PhotoZoom(next, centroid - (centroid - pan) * (next / zoom)).clampedTo(box)
    }

    fun panned(
        delta: Offset,
        box: Size,
    ): PhotoZoom = copy(pan = pan + delta).clampedTo(box)

    /** Double-tap: 1× to [DOUBLE_TAP_ZOOM] about [at], or any zoom back to 1×. */
    fun toggled(
        at: Offset,
        box: Size,
    ): PhotoZoom = if (zoom > MIN_ZOOM) PhotoZoom() else zoomedAbout(at, DOUBLE_TAP_ZOOM / zoom, box)

    fun clampedTo(box: Size): PhotoZoom =
        copy(
            pan =
                Offset(
                    pan.x.coerceIn(box.width * (1 - zoom), 0f),
                    pan.y.coerceIn(box.height * (1 - zoom), 0f),
                ),
        )

    companion object {
        const val MIN_ZOOM = 1f
        const val MAX_ZOOM = 4f
        const val DOUBLE_TAP_ZOOM = 2.5f
    }
}
