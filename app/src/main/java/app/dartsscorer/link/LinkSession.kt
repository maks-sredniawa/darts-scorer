package app.dartsscorer.link

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.DataInputStream
import java.io.DataOutputStream
import java.security.cert.X509Certificate
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLSocket

/**
 * The handshake and the first `HELLO` together, before either phone knows who the other is: a peer
 * that trickles bytes is cut off here rather than holding a connection (ADR-0009, decision 3).
 */
const val GREETING_MILLIS = 5_000L

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

    fun read(limit: Int = MAX_FRAME_BYTES): Frame = input.readFrame(limit)

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

/**
 * Runs blocking [work] on this and closes this if [work] has not finished within [millis] or the
 * caller is cancelled: a deadline over the whole of it, where a socket's timeout bounds each read.
 * Call it on a dispatcher with a thread to spare, such as IO.
 */
internal suspend fun <C : Closeable, T> C.within(
    millis: Long,
    work: () -> T,
): T =
    coroutineScope {
        val finished = AtomicBoolean(false)
        val guard =
            launch {
                try {
                    delay(millis)
                } finally {
                    if (!finished.get()) runCatching { close() }
                }
            }
        try {
            work()
        } finally {
            finished.set(true)
            guard.cancel()
        }
    }

/**
 * Tries every one of [items] at once, so one slow peer cannot hold up the rest. Returns the first
 * result [wins] accepts, the other attempts cancelled and any result they still produced
 * [discard]ed, or every result once all have finished without a winner.
 */
internal suspend fun <T, R> race(
    items: List<T>,
    attempt: suspend (T) -> R,
    wins: (R) -> Boolean,
    discard: (R) -> Unit = {},
): List<R> =
    coroutineScope {
        val results = Channel<R>(Channel.UNLIMITED)
        val attempts = items.map { item -> launch { results.send(attempt(item)) } }
        try {
            val lost = ArrayList<R>(items.size)
            repeat(items.size) {
                val result = results.receive()
                if (wins(result)) return@coroutineScope listOf(result)
                lost += result
            }
            lost
        } finally {
            attempts.forEach { it.cancel() }
            withContext(NonCancellable) { attempts.joinAll() }
            results.close()
            while (true) discard(results.tryReceive().getOrNull() ?: break)
        }
    }
