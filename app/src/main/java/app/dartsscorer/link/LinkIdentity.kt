package app.dartsscorer.link

import android.annotation.SuppressLint
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.net.Socket
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.Principal
import java.security.PrivateKey
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.security.spec.ECGenParameterSpec
import javax.net.ssl.SSLContext
import javax.net.ssl.X509KeyManager
import javax.net.ssl.X509TrustManager

/**
 * This phone's half of the link (ADR-0009, decision 4): an EC P-256 key in the Android Keystore, made
 * once, never exported and never in a backup, with the self-signed certificate the Keystore issues.
 */
class LinkIdentity private constructor(
    val key: PrivateKey,
    val certificate: X509Certificate,
) {
    /** SHA-256 of the certificate, 64 uppercase hex digits: what the other phone pins. */
    val fingerprint: String = fingerprintOf(certificate)

    companion object {
        const val ALIAS = "mounted-camera-link"

        /** Blocking, and slow the first time: call it off the main thread. */
        fun load(): LinkIdentity {
            val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            if (!store.containsAlias(ALIAS)) {
                KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").run {
                    // DIGEST_NONE because the platform's TLS hashes the handshake itself and asks the
                    // Keystore to sign the digest; without it every handshake fails (phase-G.md §4).
                    initialize(
                        KeyGenParameterSpec
                            .Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
                            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                            .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
                            .build(),
                    )
                    generateKeyPair()
                }
            }
            val entry = store.getEntry(ALIAS, null) as KeyStore.PrivateKeyEntry
            return LinkIdentity(entry.privateKey, entry.certificate as X509Certificate)
        }
    }
}

fun fingerprintOf(certificate: X509Certificate): String =
    MessageDigest.getInstance("SHA-256").digest(certificate.encoded).toHex()

/** The first 16 hex digits of a fingerprint: all a camera's NSD TXT record says about it. */
fun String.fingerprintPrefix(): String = take(16)

/**
 * A fresh context per connection, so no TLS session is ever resumed past a pin that has since
 * changed. [trusts] sees the peer's fingerprint and decides; [onPeer] is told it either way.
 */
internal fun linkTlsContext(
    me: LinkIdentity,
    trusts: (String) -> Boolean,
    onPeer: (String) -> Unit = {},
): SSLContext {
    val keys =
        object : X509KeyManager {
            override fun getClientAliases(
                keyType: String?,
                issuers: Array<out Principal>?,
            ) = arrayOf(LinkIdentity.ALIAS)

            override fun chooseClientAlias(
                keyType: Array<out String>?,
                issuers: Array<out Principal>?,
                socket: Socket?,
            ) = LinkIdentity.ALIAS

            override fun getServerAliases(
                keyType: String?,
                issuers: Array<out Principal>?,
            ) = arrayOf(LinkIdentity.ALIAS)

            override fun chooseServerAlias(
                keyType: String?,
                issuers: Array<out Principal>?,
                socket: Socket?,
            ) = LinkIdentity.ALIAS

            override fun getCertificateChain(alias: String?) = arrayOf(me.certificate)

            override fun getPrivateKey(alias: String?) = me.key
        }

    // Pinning to one self-signed certificate is the design (ADR-0009, decision 4): there is no CA.
    @SuppressLint("CustomX509TrustManager")
    val pinned =
        object : X509TrustManager {
            private fun check(chain: Array<out X509Certificate>?) {
                val peer = chain?.firstOrNull() ?: throw CertificateException("No certificate")
                val fingerprint = fingerprintOf(peer)
                onPeer(fingerprint)
                if (!trusts(fingerprint)) throw CertificateException("Not the pinned phone")
            }

            override fun checkClientTrusted(
                chain: Array<out X509Certificate>?,
                authType: String?,
            ) = check(chain)

            override fun checkServerTrusted(
                chain: Array<out X509Certificate>?,
                authType: String?,
            ) = check(chain)

            override fun getAcceptedIssuers() = arrayOf<X509Certificate>()
        }
    return SSLContext.getInstance("TLS").apply { init(arrayOf(keys), arrayOf(pinned), null) }
}
