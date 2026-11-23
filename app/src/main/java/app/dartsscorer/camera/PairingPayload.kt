package app.dartsscorer.camera

/**
 * What the Player's phone's pairing QR carries, and the same thing as one line of text to paste
 * (ADR-0009, decision 4; `phase-G.md` D10): a protocol version, the Player's phone's certificate
 * fingerprint and a one-time token.
 *
 * Uppercase hex and colons only, so the QR fits ZXing's alphanumeric mode and the pasted line has no
 * character a messaging app would rewrite.
 */
data class PairingPayload(
    val version: Int,
    /** SHA-256 of the Player's phone's certificate, 64 uppercase hex digits. */
    val fingerprint: String,
    /** The 128-bit one-time token, 32 uppercase hex digits. Never logged. */
    val token: String,
) {
    fun encode(): String = listOf(PREFIX, version, fingerprint, token).joinToString(SEPARATOR)

    override fun toString(): String = "PairingPayload(version=$version, fingerprint=$fingerprint)"

    companion object {
        const val VERSION = 1
        const val PREFIX = "DARTSSCORER"
        private const val SEPARATOR = ":"
        private const val FINGERPRINT_DIGITS = 64
        private const val TOKEN_DIGITS = 32
        private val WHITESPACE = Regex("\\s+")
        private val HEX = Regex("[0-9A-F]+")

        /**
         * The one parser for a scanned QR and a pasted code. Whitespace and line breaks anywhere are
         * dropped, since a share target may wrap the line; anything else that is not exactly this
         * app's payload at [VERSION] is refused.
         */
        fun parse(text: String): PairingPayload? {
            val parts = text.replace(WHITESPACE, "").uppercase().split(SEPARATOR)
            if (parts.size != 4 || parts[0] != PREFIX) return null
            val version = parts[1].toIntOrNull()?.takeIf { it == VERSION } ?: return null
            val fingerprint = parts[2].takeIf { it.isHex(FINGERPRINT_DIGITS) } ?: return null
            val token = parts[3].takeIf { it.isHex(TOKEN_DIGITS) } ?: return null
            return PairingPayload(version, fingerprint, token)
        }

        private fun String.isHex(digits: Int) = length == digits && HEX.matches(this)
    }
}
