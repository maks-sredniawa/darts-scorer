package app.dartsscorer.link

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.DataInputStream
import java.io.DataOutputStream
import java.security.cert.X509Certificate
import javax.net.ssl.SSLSocket

/** One TLS connection, after its handshake, carrying frames; writes from several coroutines are serialised. */
internal class LinkSession(
    private val socket: SSLSocket,
) : Closeable {
    private val input = DataInputStream(BufferedInputStream(socket.inputStream))
    private val output = DataOutputStream(BufferedOutputStream(socket.outputStream))

    val peerFingerprint: String
        get() = fingerprintOf(socket.session.peerCertificates[0] as X509Certificate)

    val peerAddress: String
        get() = socket.inetAddress?.hostAddress ?: "?"

    val protocol: String
        get() = "${socket.session.protocol} ${socket.session.cipherSuite}"

    fun read(): Frame = input.readFrame()

    @Synchronized
    fun send(frame: Frame) = output.writeFrame(frame)

    override fun close() {
        runCatching { socket.close() }
    }
}

/**
 * Runs blocking socket work on IO and closes this when it ends or the caller is cancelled, which is
 * the only way to wake a thread blocked in a socket read.
 */
internal suspend fun <C : Closeable, T> C.useCancellably(work: suspend CoroutineScope.(C) -> T): T =
    withContext(Dispatchers.IO) {
        val closer =
            launch(start = CoroutineStart.UNDISPATCHED) {
                try {
                    awaitCancellation()
                } finally {
                    runCatching { close() }
                }
            }
        try {
            work(this@useCancellably)
        } finally {
            closer.cancel()
        }
    }
