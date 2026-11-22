package app.dartsscorer.ui.visit

import androidx.compose.ui.geometry.Offset
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
}
