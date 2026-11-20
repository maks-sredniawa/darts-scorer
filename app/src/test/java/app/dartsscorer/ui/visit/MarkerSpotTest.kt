package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MarkerSpotTest {
    private val canvas = Size(1000f, 1000f)
    private val badge = Size(60f, 40f)
    private val ringOuter = 30f
    private val reach = 60f

    private fun spot(at: Offset) = MarkerSpot(at, badgeBeside(at, badge, ringOuter, canvas))

    @Test
    fun `the badge sits up and to the right of its Dart, clear of the ring`() {
        val at = Offset(500f, 500f)
        val rect = badgeBeside(at, badge, ringOuter, canvas)
        assertEquals(badge, rect.size)
        assertTrue(rect.left > at.x && rect.bottom < at.y)
    }

    @Test
    fun `the badge flips to whichever side stays inside the crop`() {
        val rect = badgeBeside(Offset(990f, 10f), badge, ringOuter, canvas)
        assertTrue(rect.right < 990f && rect.top > 10f)
        assertTrue(Rect(Offset.Zero, canvas).contains(rect.topLeft))
    }

    @Test
    fun `a corrected Dart's badge is centred on it, kept inside the crop`() {
        assertEquals(Offset(500f, 500f), badgeOn(Offset(500f, 500f), badge, canvas).center)
        assertEquals(Rect(0f, 0f, 60f, 40f), badgeOn(Offset(5f, 5f), badge, canvas))
    }

    @Test
    fun `a tap on the far end of a badge opens its Dart though it is beyond the reach of the Dart`() {
        val dart = spot(Offset(500f, 500f))
        val farEnd = Offset(dart.badge.right - 1f, dart.badge.top + 1f)
        assertTrue((farEnd - dart.at).getDistance() > reach)
        assertEquals(0, listOf(dart).hitBy(farEnd, reach))
    }

    @Test
    fun `a tap near a Dart opens it, and one away from every marker opens none`() {
        val darts = listOf(spot(Offset(200f, 200f)), spot(Offset(700f, 700f)))
        assertEquals(1, darts.hitBy(Offset(690f, 710f), reach))
        assertNull(darts.hitBy(Offset(450f, 450f), reach))
    }

    @Test
    fun `the nearest Dart wins, and a tap inside a badge beats a nearby Dart`() {
        val first = spot(Offset(500f, 500f))
        val second = spot(Offset(540f, 500f))
        assertEquals(1, listOf(first, second).hitBy(Offset(535f, 505f), reach))
        val onFirstBadge = first.badge.center
        val third = MarkerSpot(onFirstBadge + Offset(0f, 30f), Rect(Offset(900f, 900f), badge))
        assertEquals(0, listOf(first, third).hitBy(onFirstBadge, reach))
    }
}
