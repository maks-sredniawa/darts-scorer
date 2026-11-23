package app.dartsscorer.camera

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

/** `phase-G.md`, *Tests*: one parser for the scanned QR and the pasted text. Fails toward pairing with garbage. */
class PairingPayloadTest {
    private val fingerprint = "0123456789ABCDEF".repeat(4)
    private val token = "FEDCBA9876543210".repeat(2)
    private val payload = PairingPayload(PairingPayload.VERSION, fingerprint, token)

    @Test
    fun `a QR and its pasted text give the same payload`() {
        val qr = payload.encode()
        assertEquals(payload, PairingPayload.parse(qr))
        assertEquals(PairingPayload.parse(qr), PairingPayload.parse("  \n$qr\r\n\t "))
    }

    @Test
    fun `line breaks inside a wrapped paste are dropped`() {
        val qr = payload.encode()
        assertEquals(payload, PairingPayload.parse(qr.substring(0, 40) + "\n" + qr.substring(40)))
    }

    @Test
    fun `lowercase hex reads as the same payload`() =
        assertEquals(payload, PairingPayload.parse(payload.encode().lowercase()))

    @Test
    fun `a wrong version is refused`() {
        assertNull(PairingPayload.parse("DARTSSCORER:2:$fingerprint:$token"))
        assertNull(PairingPayload.parse("DARTSSCORER:0:$fingerprint:$token"))
        assertNull(PairingPayload.parse("DARTSSCORER:x:$fingerprint:$token"))
    }

    @Test
    fun `a malformed fingerprint is refused`() {
        assertNull(PairingPayload.parse("DARTSSCORER:1:${fingerprint.drop(1)}:$token"))
        assertNull(PairingPayload.parse("DARTSSCORER:1:${fingerprint}0:$token"))
        assertNull(PairingPayload.parse("DARTSSCORER:1:${fingerprint.dropLast(1)}G:$token"))
    }

    @Test
    fun `a short or long token is refused`() {
        assertNull(PairingPayload.parse("DARTSSCORER:1:$fingerprint:${token.drop(2)}"))
        assertNull(PairingPayload.parse("DARTSSCORER:1:$fingerprint:${token}00"))
        assertNull(PairingPayload.parse("DARTSSCORER:1:$fingerprint:"))
    }

    @Test
    fun `anything else is refused`() {
        assertNull(PairingPayload.parse(""))
        assertNull(PairingPayload.parse("   "))
        assertNull(PairingPayload.parse("https://example.com/$fingerprint"))
        assertNull(PairingPayload.parse("OTHERAPP:1:$fingerprint:$token"))
        assertNull(PairingPayload.parse("${payload.encode()}:EXTRA"))
    }

    @Test
    fun `the token never reaches a log through toString`() = assertFalse(token in payload.toString())
}
