package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import org.junit.Assert.assertEquals
import org.junit.Test

class LiftOffsetTest {
    private val grab = Offset(6f, 10f)
    private val lift = Offset(0f, -180f)

    @Test
    fun theRingStartsWhereItWasGrabbedAndRisesToTheLift() {
        assertEquals(grab, liftOffset(grab, lift, 0, 120))
        assertEquals(Offset(3f, -85f), liftOffset(grab, lift, 60, 120))
        assertEquals(lift, liftOffset(grab, lift, 120, 120))
        assertEquals(lift, liftOffset(grab, lift, 5_000, 120))
    }

    @Test
    fun withAnimationsOffTheRingIsLiftedAtOnce() {
        assertEquals(lift, liftOffset(grab, lift, 0, 0))
    }

    @Test
    fun aRingLiftedPastAnEdgeWaitsOneRadiusInsideIt() {
        val box = Size(400f, 400f)
        assertEquals(Offset(200f, 30f), keptInside(Offset(200f, -150f), box, 30f))
        assertEquals(Offset(30f, 370f), keptInside(Offset(-5f, 900f), box, 30f))
        assertEquals(Offset(370f, 200f), keptInside(Offset(399f, 200f), box, 30f))
        assertEquals(Offset(120f, 80f), keptInside(Offset(120f, 80f), box, 30f))
    }
}
