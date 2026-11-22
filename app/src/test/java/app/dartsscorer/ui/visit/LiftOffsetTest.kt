package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
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
    fun aRingLiftedPastAnEdgeWaitsInsideIt() {
        val bounds = Rect(30f, 30f, 370f, 370f)
        assertEquals(Offset(200f, 30f), keptInside(Offset(200f, -150f), bounds))
        assertEquals(Offset(30f, 370f), keptInside(Offset(-5f, 900f), bounds))
        assertEquals(Offset(120f, 80f), keptInside(Offset(120f, 80f), bounds))
    }

    @Test
    fun theInsetNeverHidesTheBoardsRim() {
        val box = Rect(0f, 0f, 400f, 400f)
        assertEquals(Rect(30f, 30f, 370f, 370f), insideRim(box, Rect(40f, 40f, 360f, 360f), 30f))
        assertEquals(Rect(30f, 10f, 370f, 400f), insideRim(box, Rect(40f, 10f, 360f, 410f), 30f))
    }
}
