package app.dartsscorer.link

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** `phase-G.md`, *Tests*: fails toward a stranger's phone being trusted. */
class PairingProofTest {
    private val token = "0123456789ABCDEF0123456789ABCDEF"
    private val camera = "AB".repeat(32)
    private val player = "CD".repeat(32)
    private val nonce = ByteArray(NONCE_BYTES) { it.toByte() }
    private val proof = pairingProof(token, nonce, camera, player)

    @Test
    fun `the proof over the session's fingerprints and nonce under the token holds`() {
        assertTrue(proofHolds(proof, token, nonce, camera, player))
        assertEquals(32, proof.size)
    }

    @Test
    fun `a proof under the wrong token is refused`() {
        val stranger = pairingProof("FEDCBA9876543210FEDCBA9876543210", nonce, camera, player)
        assertFalse(proofHolds(stranger, token, nonce, camera, player))
    }

    @Test
    fun `a proof over swapped fingerprints is refused`() {
        val swapped = pairingProof(token, nonce, player, camera)
        assertFalse(proofHolds(swapped, token, nonce, camera, player))
    }

    @Test
    fun `a proof over a fingerprint other than the session's is refused`() {
        val relayed = "EF".repeat(32)
        assertFalse(proofHolds(proof, token, nonce, relayed, player))
        assertFalse(proofHolds(proof, token, nonce, camera, relayed))
    }

    @Test
    fun `a proof replayed against a new nonce is refused`() {
        val next = ByteArray(NONCE_BYTES) { (it + 1).toByte() }
        assertFalse(proofHolds(proof, token, next, camera, player))
    }

    @Test
    fun `no proof, or a cut one, is refused`() {
        assertFalse(proofHolds(null, token, nonce, camera, player))
        assertFalse(proofHolds(proof.copyOf(16), token, nonce, camera, player))
    }

    @Test
    fun `a fresh token is 32 uppercase hex digits and nonces differ`() {
        assertTrue(Regex("[0-9A-F]{32}").matches(freshToken()))
        assertFalse(freshNonce().contentEquals(freshNonce()))
    }
}
