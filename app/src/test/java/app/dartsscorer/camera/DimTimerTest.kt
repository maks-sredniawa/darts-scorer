package app.dartsscorer.camera

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class DimTimerTest {
    @Test
    fun `nothing dims before the first capture`() {
        assertNull(DimTimer().dimsAt())
        assertNull(DimTimer().touched(5_000).dimsAt())
    }

    @Test
    fun `a capture while unpaired does not arm it`() =
        assertNull(DimTimer().captured(paired = false, now = 1_000).dimsAt())

    @Test
    fun `30 s after a paired capture it dims`() =
        assertEquals(31_000L, DimTimer().captured(paired = true, now = 1_000).dimsAt())

    @Test
    fun `a touch restarts the 30 s`() {
        val armed = DimTimer().captured(paired = true, now = 1_000)
        assertEquals(50_000L, armed.touched(20_000).dimsAt())
    }

    @Test
    fun `the paste field in use holds it off, and leaving it restarts the 30 s`() {
        val typing = DimTimer().captured(paired = true, now = 1_000).input(active = true, now = 2_000)
        assertNull(typing.dimsAt())
        assertNull(typing.touched(100_000).dimsAt())
        assertEquals(130_000L, typing.input(active = false, now = 100_000).dimsAt())
    }

    @Test
    fun `the status line always moves to another row and stays on the grid`() {
        val random = Random(7)
        var slot = DimSlot.Start
        repeat(1_000) {
            val next = slot.next(random)
            assertNotEquals(slot.row, next.row)
            assertTrue(next.row in 0 until DimSlot.ROWS && next.column in 0 until DimSlot.COLUMNS)
            slot = next
        }
    }

    @Test
    fun `slot biases span the safe area`() {
        assertEquals(-1f, DimSlot(0, 0).verticalBias)
        assertEquals(1f, DimSlot(DimSlot.ROWS - 1, DimSlot.COLUMNS - 1).verticalBias)
        assertEquals(-1f, DimSlot(0, 0).horizontalBias)
        assertEquals(1f, DimSlot(0, DimSlot.COLUMNS - 1).horizontalBias)
    }
}

class CameraLensTest {
    @Test
    fun `a main lens is not an ultra-wide`() {
        // About 75 degrees: a typical 1x camera, 4.7 mm over a 7.2 mm wide sensor.
        assertFalse(isUltraWide(focalLengthMm = 4.7f, sensorWidthMm = 7.2f))
    }

    @Test
    fun `a 120 degree lens is an ultra-wide`() = assertTrue(isUltraWide(focalLengthMm = 2.2f, sensorWidthMm = 7.6f))
}
