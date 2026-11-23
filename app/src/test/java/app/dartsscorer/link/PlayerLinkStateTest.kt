package app.dartsscorer.link

import app.dartsscorer.camera.PhoneRole
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * *Pair again* only from the paired camera's own word over a completed, pinned handshake; anything
 * else that fails is *Camera not found*. Fails toward a reset or a stranger unpairing the player.
 */
class PlayerLinkStateTest {
    private val quiet = PlayerLink.NOT_FOUND_MILLIS / 2
    private val silent = PlayerLink.NOT_FOUND_MILLIS + 1

    @Test
    fun `only the camera's not-paired frame reads as refused`() {
        assertEquals(Answer.REFUSED, answerOf(Frame.NotPaired))
        assertEquals(Answer.GREETED, answerOf(Frame.Hello(PhoneRole.MOUNTED_CAMERA, "0.3.0")))
        assertEquals(Answer.OUTDATED, answerOf(Frame.ForeignHello(LINK_VERSION + 1)))
    }

    @Test
    fun `no frame, from a TLS failure or a reset before it, is unreachable`() {
        assertEquals(Answer.UNREACHABLE, answerOf(null))
    }

    @Test
    fun `any other first frame is unreachable, never refused`() {
        listOf(Frame.Ping, Frame.Pong, Frame.Capture(1), Frame.Error(1, CaptureError.FAILED)).forEach {
            assertEquals(Answer.UNREACHABLE, answerOf(it))
        }
    }

    @Test
    fun `an unreachable camera never brings pair again`() {
        PlayerLinkState.entries.forEach { state ->
            listOf(0L, quiet, silent).forEach { silentFor ->
                val next = state.after(Answer.UNREACHABLE, silentFor)
                if (state != PlayerLinkState.PAIR_AGAIN) assertNotEquals("$state", PlayerLinkState.PAIR_AGAIN, next)
            }
        }
    }

    @Test
    fun `a refusal is pair again`() {
        PlayerLinkState.entries.forEach { assertEquals(PlayerLinkState.PAIR_AGAIN, it.after(Answer.REFUSED, 0)) }
    }

    @Test
    fun `camera not found replaces a stale pair again once the camera has been silent long enough`() {
        assertEquals(PlayerLinkState.PAIR_AGAIN, PlayerLinkState.PAIR_AGAIN.after(Answer.UNREACHABLE, quiet))
        assertEquals(PlayerLinkState.NOT_FOUND, PlayerLinkState.PAIR_AGAIN.after(Answer.UNREACHABLE, silent))
        assertEquals(PlayerLinkState.NOT_FOUND, PlayerLinkState.LOOKING.after(Answer.UNREACHABLE, silent))
    }

    @Test
    fun `a link that came up and dropped looks again`() {
        assertEquals(PlayerLinkState.LOOKING, PlayerLinkState.CONNECTED.after(Answer.GREETED, 0))
    }
}
