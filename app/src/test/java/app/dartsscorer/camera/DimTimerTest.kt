package app.dartsscorer.camera

import org.junit.Assert.assertEquals
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
    private val main = horizontalFieldOfView(focalLengthMm = 4.7f, sensorWidthMm = 7.2f)
    private val ultraWide = horizontalFieldOfView(focalLengthMm = 2.2f, sensorWidthMm = 7.6f)

    @Test
    fun `field of view from focal length and sensor width`() {
        assertEquals(75.0, main, 1.0)
        assertEquals(120.0, ultraWide, 1.0)
    }

    @Test
    fun `an ultra-wide listed first is passed over for the main lens`() =
        assertEquals(1, chooseBackCamera(listOf(ultraWide, main)))

    @Test
    fun `the main lens listed first is used`() = assertEquals(0, chooseBackCamera(listOf(main, ultraWide)))

    @Test
    fun `a phone's only back camera is used whatever it reports`() = assertEquals(0, chooseBackCamera(listOf(104.0)))

    @Test
    fun `several back cameras that are all ultra-wide are refused`() =
        assertNull(chooseBackCamera(listOf(ultraWide, 110.0)))

    @Test
    fun `a camera that reports no field of view is not refused`() =
        assertEquals(1, chooseBackCamera(listOf(ultraWide, null)))

    @Test
    fun `no back camera at all is refused`() = assertNull(chooseBackCamera(emptyList()))
}
