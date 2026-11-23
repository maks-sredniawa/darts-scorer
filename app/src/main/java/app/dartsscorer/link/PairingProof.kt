package app.dartsscorer.link

import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

const val NONCE_BYTES = 16

/**
 * `HMAC-SHA256(token, "pair" ‖ nonce ‖ camera fingerprint ‖ player fingerprint)` (ADR-0009,
 * decision 4). The camera fingerprint is the one the TLS session presented, so a relay that swaps
 * certificates cannot reuse a proof.
 */
fun pairingProof(
    token: String,
    nonce: ByteArray,
    cameraFingerprint: String,
    playerFingerprint: String,
): ByteArray {
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(token.hexToBytes(), "HmacSHA256"))
    mac.update("pair".toByteArray(Charsets.US_ASCII))
    mac.update(nonce)
    mac.update(cameraFingerprint.uppercase().toByteArray(Charsets.US_ASCII))
    mac.update(playerFingerprint.uppercase().toByteArray(Charsets.US_ASCII))
    return mac.doFinal()
}

fun proofHolds(
    proof: ByteArray?,
    token: String,
    nonce: ByteArray,
    cameraFingerprint: String,
    playerFingerprint: String,
): Boolean =
    proof != null &&
        MessageDigest.isEqual(proof, pairingProof(token, nonce, cameraFingerprint, playerFingerprint))

fun freshNonce(random: SecureRandom = SecureRandom()): ByteArray = ByteArray(NONCE_BYTES).also(random::nextBytes)

/** A fresh 128-bit pairing token, as the QR carries it: 32 uppercase hex digits. */
fun freshToken(random: SecureRandom = SecureRandom()): String = ByteArray(16).also(random::nextBytes).toHex()

fun ByteArray.toHex(): String = joinToString("") { "%02X".format(it) }

private fun String.hexToBytes(): ByteArray = chunked(2).map { it.toInt(16).toByte() }.toByteArray()
