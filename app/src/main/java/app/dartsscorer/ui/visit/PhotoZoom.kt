package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.center

data class PhotoZoom(
    val zoom: Float = 1f,
    val pan: Offset = Offset.Zero,
) {
    fun toScreen(base: Offset): Offset = base * zoom + pan

    fun toBase(screen: Offset): Offset = (screen - pan) / zoom

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

    fun toggled(
        at: Offset,
        box: Size,
    ): PhotoZoom = if (zoom > MIN_ZOOM) PhotoZoom() else zoomedAbout(at, DOUBLE_TAP_ZOOM / zoom, box)

    fun zoomStepped(
        inward: Boolean,
        box: Size,
    ): PhotoZoom = zoomedAbout(box.center, if (inward) ZOOM_STEP else 1 / ZOOM_STEP, box)

    fun viewMoved(
        direction: Offset,
        box: Size,
    ): PhotoZoom = panned(Offset(-direction.x * box.width, -direction.y * box.height) * MOVE_STEP, box)

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
        const val ZOOM_STEP = 2f
        const val MOVE_STEP = 1 / 3f
    }
}
