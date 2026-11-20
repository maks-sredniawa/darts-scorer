package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import org.junit.Assert.assertEquals
import org.junit.Test

class PhotoZoomTest {
    private val box = Size(400f, 300f)

    private fun assertNear(
        expected: Offset,
        actual: Offset,
    ) {
        assertEquals(expected.x, actual.x, 0.001f)
        assertEquals(expected.y, actual.y, 0.001f)
    }

    @Test
    fun `screen and base invert each other`() {
        val zoom = PhotoZoom(2.5f, Offset(-120f, -80f))
        val base = Offset(173f, 42f)
        assertNear(base, zoom.toBase(zoom.toScreen(base)))
    }

    @Test
    fun `zooming keeps the point under the fingers where it was`() {
        val centroid = Offset(150f, 100f)
        val zoomed = PhotoZoom().zoomedAbout(centroid, 2f, box)
        assertEquals(2f, zoomed.zoom)
        assertNear(centroid, zoomed.toScreen(PhotoZoom().toBase(centroid)))
    }

    @Test
    fun `zoom stays between 1x and 4x`() {
        assertEquals(PhotoZoom.MAX_ZOOM, PhotoZoom(3f).zoomedAbout(Offset.Zero, 10f, box).zoom)
        assertEquals(PhotoZoom(), PhotoZoom(2f, Offset(-50f, -50f)).zoomedAbout(Offset(10f, 10f), 0.1f, box))
    }

    @Test
    fun `a pan stops where the Photo would leave its box`() {
        val zoom = PhotoZoom(2f, Offset(-10f, -290f))
        assertNear(Offset.Zero, zoom.panned(Offset(50f, 500f), box).pan)
        assertNear(Offset(-400f, -300f), zoom.panned(Offset(-1000f, -1000f), box).pan)
    }

    @Test
    fun `at 1x nothing pans`() {
        assertEquals(PhotoZoom(), PhotoZoom().panned(Offset(30f, -40f), box))
    }

    @Test
    fun `double-tap zooms to 2_5x about the tap, and a second one goes back to 1x`() {
        val tap = Offset(200f, 150f)
        val zoomed = PhotoZoom().toggled(tap, box)
        assertEquals(PhotoZoom.DOUBLE_TAP_ZOOM, zoomed.zoom)
        assertNear(tap, zoomed.toScreen(tap))
        assertEquals(PhotoZoom(), zoomed.toggled(tap, box))
    }

    @Test
    fun `zooming out at an edge pulls the Photo back to fill its box`() {
        val zoomed = PhotoZoom(2f, Offset(-400f, -300f)).zoomedAbout(Offset.Zero, 0.75f, box)
        assertEquals(1.5f, zoomed.zoom)
        assertNear(Offset(-200f, -150f), zoomed.pan)
    }
}
