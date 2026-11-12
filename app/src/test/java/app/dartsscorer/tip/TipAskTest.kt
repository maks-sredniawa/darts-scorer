package app.dartsscorer.tip

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class TipAskTest {
    private val installedAt = Instant.parse("2026-09-01T08:00:00Z")
    private val monthLater = installedAt + TIP_ASK_AFTER

    private fun due(
        asked: Boolean = false,
        visits: Int = TIP_ASK_AFTER_VISITS,
        now: Instant = monthLater,
    ) = tipAskDue(asked, visits, installedAt, now)

    @Test
    fun `due once installed a month with enough Visits scored`() {
        assertTrue(due())
    }

    @Test
    fun `not due a millisecond short of the month`() {
        assertFalse(due(visits = 1_000, now = monthLater.minusMillis(1)))
    }

    @Test
    fun `not due one Visit short`() {
        assertFalse(due(visits = TIP_ASK_AFTER_VISITS - 1, now = monthLater.plus(TIP_ASK_AFTER)))
    }

    @Test
    fun `never due before a Visit is scored`() {
        assertFalse(due(visits = 0, now = monthLater.plus(TIP_ASK_AFTER)))
    }

    @Test
    fun `never again once answered`() {
        assertFalse(due(asked = true, visits = 1_000, now = monthLater.plus(TIP_ASK_AFTER)))
    }
}
