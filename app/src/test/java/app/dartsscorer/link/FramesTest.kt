package app.dartsscorer.link

import app.dartsscorer.camera.PhoneRole
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.EOFException

/** `phase-G.md`, *Tests*: the frame reader's bound. Fails toward a peer crashing the app or exhausting its memory. */
class FramesTest {
    private fun bytesOf(vararg frames: Frame): ByteArray {
        val out = ByteArrayOutputStream()
        DataOutputStream(out).use { data -> frames.forEach { data.writeFrame(it) } }
        return out.toByteArray()
    }

    private fun reader(bytes: ByteArray) = DataInputStream(ByteArrayInputStream(bytes))

    private fun raw(
        length: Int,
        type: Int,
        body: ByteArray = ByteArray(0),
    ): ByteArray {
        val out = ByteArrayOutputStream()
        DataOutputStream(out).use {
            it.writeInt(length)
            it.writeByte(type)
            it.write(body)
        }
        return out.toByteArray()
    }

    @Test
    fun `every frame type survives a round trip`() {
        val nonce = ByteArray(NONCE_BYTES) { 7 }
        val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 1, 2, 3)
        val input =
            reader(
                bytesOf(
                    Frame.Hello(PhoneRole.PLAYER, "0.3.0", nonce = nonce),
                    Frame.Ping,
                    Frame.Pong,
                    Frame.Capture(42),
                    Frame.Photo(42, 1_700_000_000_000, 2048, 1536, jpeg),
                    Frame.Error(43, CaptureError.BUSY),
                ),
            )
        val hello = input.readFrame() as Frame.Hello
        assertEquals(PhoneRole.PLAYER, hello.role)
        assertEquals("0.3.0", hello.appVersion)
        assertArrayEquals(nonce, hello.nonce)
        assertNull(hello.proof)
        assertEquals(Frame.Ping, input.readFrame())
        assertEquals(Frame.Pong, input.readFrame())
        assertEquals(Frame.Capture(42), input.readFrame())
        val photo = input.readFrame() as Frame.Photo
        assertEquals(42, photo.requestId)
        assertEquals(1_700_000_000_000, photo.takenAt)
        assertEquals(2048 to 1536, photo.width to photo.height)
        assertArrayEquals(jpeg, photo.jpeg)
        assertEquals(Frame.Error(43, CaptureError.BUSY), input.readFrame())
    }

    @Test
    fun `a declared length over 16 MiB is refused before the body is read`() {
        val oversized = raw(MAX_FRAME_BYTES + 1, 2)
        val error = assertThrows(FrameException::class.java) { reader(oversized).readFrame() }
        assertTrue(error.message!!.contains("refused"))
        assertThrows(FrameException::class.java) { reader(raw(-1, 2)).readFrame() }
    }

    @Test
    fun `a truncated frame ends the connection`() {
        val whole = bytesOf(Frame.Capture(1))
        assertThrows(EOFException::class.java) { reader(whole.copyOf(whole.size - 1)).readFrame() }
        assertThrows(EOFException::class.java) { reader(whole.copyOf(3)).readFrame() }
        assertThrows(EOFException::class.java) { reader(raw(4, 4)).readFrame() }
    }

    @Test
    fun `an unknown frame type ends the connection`() {
        assertThrows(FrameException::class.java) { reader(raw(0, 99)).readFrame() }
    }

    @Test
    fun `a HELLO on another protocol version is read as foreign, whatever follows its version`() {
        val body =
            ByteArrayOutputStream()
                .also {
                    DataOutputStream(it).use { data ->
                        data.writeInt(LINK_VERSION + 1)
                    }
                }.toByteArray()
        val hello = reader(raw(body.size, 1, body)).readFrame()
        assertEquals(LINK_VERSION + 1, (hello as Frame.ForeignHello).version)
    }

    @Test
    fun `an error code this version does not know reads as unknown`() {
        val body =
            ByteArrayOutputStream()
                .also {
                    DataOutputStream(it).use { data ->
                        data.writeInt(5)
                        data.writeUTF("SOMETHING_LATER")
                    }
                }.toByteArray()
        assertEquals(Frame.Error(5, CaptureError.UNKNOWN), reader(raw(body.size, 6, body)).readFrame())
    }
}
