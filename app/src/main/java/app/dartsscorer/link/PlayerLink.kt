package app.dartsscorer.link

import android.net.Network
import android.net.nsd.NsdServiceInfo
import android.os.SystemClock
import android.util.Log
import app.dartsscorer.camera.PhoneRole
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.net.ConnectException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket

/** What the Player's phone says about its camera (ADR-0009, decision 8). */
enum class PlayerLinkState {
    LOOKING,
    CONNECTED,
    NOT_FOUND,

    /** The pinned camera, proven by a completed handshake, said it is no longer paired with this phone. */
    PAIR_AGAIN,
    OUTDATED,
}

/** What one attempt at a camera came to, strongest first. */
internal enum class Answer {
    GREETED,
    REFUSED,
    OUTDATED,
    UNREACHABLE,
}

/**
 * The camera's first frame, read only after this phone's pinned handshake completed, or null when
 * none was: a TLS failure or a reset on the way is [Answer.UNREACHABLE]. Only the camera's own
 * [Frame.NotPaired], over the authenticated channel, is [Answer.REFUSED].
 */
internal fun answerOf(reply: Frame?): Answer =
    when (reply) {
        is Frame.Hello -> Answer.GREETED
        Frame.NotPaired -> Answer.REFUSED
        is Frame.ForeignHello -> Answer.OUTDATED
        else -> Answer.UNREACHABLE
    }

/**
 * The state after a round of attempts. Silence turns *Looking* into *Camera not found*, and a stale
 * *Pair again* too, once the camera has said nothing for [PlayerLink.NOT_FOUND_MILLIS].
 */
internal fun PlayerLinkState.after(
    answer: Answer,
    silentFor: Long,
): PlayerLinkState =
    when (answer) {
        Answer.GREETED -> PlayerLinkState.LOOKING
        Answer.REFUSED -> PlayerLinkState.PAIR_AGAIN
        Answer.OUTDATED -> PlayerLinkState.OUTDATED
        Answer.UNREACHABLE ->
            if ((this == PlayerLinkState.LOOKING || this == PlayerLinkState.PAIR_AGAIN) &&
                silentFor > PlayerLink.NOT_FOUND_MILLIS
            ) {
                PlayerLinkState.NOT_FOUND
            } else {
                this
            }
    }

/** A refused connection reached the camera's address, so no other route will do better; anything else might. */
internal fun anotherRouteMayWork(failure: IOException): Boolean = failure !is ConnectException

private class Attempt(
    val answer: Answer,
    val session: LinkSession? = null,
)

private class Opened(
    val session: LinkSession,
    val reply: Frame,
)

class ReceivedPhoto(
    val jpeg: ByteArray,
    val width: Int,
    val height: Int,
    val takenAt: Long,
)

enum class CaptureFailure {
    NOT_CONNECTED,
    TIMED_OUT,
    LINK_LOST,
    CAMERA_ERROR,
}

class CaptureFailed(
    val failure: CaptureFailure,
    val code: CaptureError? = null,
) : Exception(listOfNotNull(failure.name, code?.name).joinToString(" "))

/** Where to connect: what NSD resolved, or the debug build's address field. */
class LinkTarget(
    val label: String,
    val address: InetAddress,
    val port: Int,
    val network: Network?,
    val fingerprintPrefix: String?,
)

/**
 * The Player's phone's end of the link (ADR-0009, decisions 3, 4 and 8): pairs with a camera that
 * proves it holds the QR's token, then connects to the pinned camera, pings it every 5 s and asks
 * it for Photos. One per app, held by `AppContainer`, and it runs only while a screen collects it:
 * nothing runs in the background. A second screen that starts it takes it over from the first.
 */
class PlayerLink(
    private val identity: suspend () -> LinkIdentity,
    private val finder: CameraFinder,
    private val appVersion: String,
    private val debugTarget: StateFlow<InetSocketAddress?>,
    private val acceptsLoopback: Boolean,
    private val clock: () -> Long = SystemClock::elapsedRealtime,
) {
    private val mutableState = MutableStateFlow(PlayerLinkState.LOOKING)
    val state: StateFlow<PlayerLinkState> = mutableState.asStateFlow()

    @Volatile private var session: LinkSession? = null
    private val pending = ConcurrentHashMap<Int, CompletableDeferred<Frame>>()
    private val requestIds = AtomicInteger()
    private val ignored = ConcurrentHashMap.newKeySet<String>()

    private val turns = Mutex()
    private var turn: Job? = null

    /** Runs [work] as the link's only mode, cancelling whichever screen held it before. */
    private suspend fun <T> exclusively(work: suspend CoroutineScope.() -> T): T =
        coroutineScope {
            val mine = async(start = CoroutineStart.LAZY) { coroutineScope { work() } }
            turns.withLock {
                turn?.cancelAndJoin()
                turn = mine
            }
            mine.await()
        }

    /**
     * Pairing mode: offers this phone's certificate to every camera found until one answers with a
     * proof of [token]; returns that camera's fingerprint, the one to pin.
     */
    suspend fun pair(token: String): String =
        exclusively {
            val me = identity()
            mutableState.value = PlayerLinkState.LOOKING
            val advertised = finder.advertised().stateIn(this)
            Log.i(LINK_TAG, "Pairing as ${me.fingerprint}")
            try {
                var camera: String? = null
                while (camera == null) {
                    camera =
                        race(targets(advertised.value), { pairWith(me, token, it) }, { it != null })
                            .firstNotNullOfOrNull { it }
                    if (camera == null) delay(RETRY_MILLIS)
                }
                camera
            } finally {
                coroutineContext.cancelChildren()
            }
        }

    private suspend fun pairWith(
        me: LinkIdentity,
        token: String,
        target: LinkTarget,
    ): String? {
        val nonce = freshNonce()
        val tls = linkTlsContext(me, trusts = { true })
        val opened =
            try {
                open(target, tls, Frame.Hello(PhoneRole.PLAYER, appVersion, nonce = nonce))
            } catch (e: IOException) {
                Log.i(LINK_TAG, "Camera ${target.label} not reachable for pairing: $e")
                return null
            }
        val camera = opened.session.peerFingerprint
        opened.session.close()
        return when (val hello = opened.reply) {
            is Frame.ForeignHello -> {
                mutableState.value = PlayerLinkState.OUTDATED
                null
            }
            is Frame.Hello ->
                if (proofHolds(hello.proof, token, nonce, camera, me.fingerprint)) {
                    Log.i(LINK_TAG, "Camera ${target.label} proved the token: pinned $camera")
                    camera
                } else {
                    Log.w(LINK_TAG, "Camera ${target.label} ($camera) gave no valid proof: not accepted")
                    null
                }
            else -> {
                Log.i(LINK_TAG, "Camera ${target.label} has not taken this code")
                null
            }
        }
    }

    /** Connected mode: keeps the link to the camera pinned as [pin] up until cancelled. */
    suspend fun run(pin: String): Unit =
        exclusively {
            val me = identity()
            val advertised = finder.advertised().stateIn(this)
            var heardAt = clock()
            mutableState.value = PlayerLinkState.LOOKING
            Log.i(LINK_TAG, "Looking for the camera $pin")
            while (true) {
                val candidates = targets(advertised.value).filter { it.mayBe(pin) }
                val attempts =
                    race(
                        candidates,
                        { greet(me, pin, it) },
                        wins = { it.answer == Answer.GREETED },
                        discard = { it.session?.close() },
                    )
                val answer = attempts.minOfOrNull { it.answer } ?: Answer.UNREACHABLE
                attempts.firstNotNullOfOrNull { it.session }?.let { stayConnected(it) }
                if (answer != Answer.UNREACHABLE) heardAt = clock()
                mutableState.value = mutableState.value.after(answer, clock() - heardAt)
                delay(RETRY_MILLIS)
            }
        }

    private fun LinkTarget.mayBe(pin: String): Boolean {
        if (fingerprintPrefix == null || fingerprintPrefix == pin.fingerprintPrefix()) return true
        if (ignored.add(label)) Log.i(LINK_TAG, "Camera $label is not the paired one: not accepted")
        return false
    }

    /** The handshake pinned to [pin] and the camera's first frame; a greeted attempt keeps its session open. */
    private suspend fun greet(
        me: LinkIdentity,
        pin: String,
        target: LinkTarget,
    ): Attempt {
        val opened =
            try {
                open(target, linkTlsContext(me, trusts = { it == pin }), Frame.Hello(PhoneRole.PLAYER, appVersion))
            } catch (e: IOException) {
                Log.i(LINK_TAG, "Camera ${target.label} unreachable: $e")
                null
            }
        val answer = answerOf(opened?.reply)
        if (answer == Answer.GREETED) return Attempt(answer, opened?.session)
        when (val reply = opened?.reply) {
            null -> Unit
            Frame.NotPaired -> Log.w(LINK_TAG, "The paired camera says it is no longer paired with this phone")
            is Frame.ForeignHello ->
                Log.w(LINK_TAG, "The camera speaks link version ${reply.version}, this phone $LINK_VERSION")
            else -> Log.w(LINK_TAG, "Camera ${target.label} sent ${reply.describe()} first")
        }
        opened?.session?.close()
        return Attempt(answer)
    }

    /** Until a greeted session drops. */
    private suspend fun stayConnected(session: LinkSession) {
        Log.i(LINK_TAG, "Connected to the camera at ${session.peerAddress}, ${session.protocol}")
        mutableState.value = PlayerLinkState.CONNECTED
        try {
            session.useCancellably { hold(it) }
        } catch (e: IOException) {
            Log.i(LINK_TAG, "The link dropped: $e")
        } finally {
            session.close()
        }
    }

    private suspend fun CoroutineScope.hold(session: LinkSession) {
        this@PlayerLink.session = session
        var lastPong = clock()
        val pinger =
            launch {
                while (true) {
                    delay(PING_MILLIS)
                    if (clock() - lastPong > PING_MILLIS * MISSED_PINGS) {
                        Log.w(LINK_TAG, "$MISSED_PINGS pings missed: the link is down")
                        session.close()
                        break
                    }
                    session.send(Frame.Ping)
                }
            }
        try {
            while (true) {
                when (val frame = session.read()) {
                    Frame.Pong -> lastPong = clock()
                    is Frame.Photo -> pending.remove(frame.requestId)?.complete(frame)
                    is Frame.Error -> pending.remove(frame.requestId)?.complete(frame)
                    else -> throw FrameException("Unexpected ${frame::class.simpleName} from the camera")
                }
            }
        } finally {
            pinger.cancel()
            this@PlayerLink.session = null
            pending.values.forEach { it.completeExceptionally(CaptureFailed(CaptureFailure.LINK_LOST)) }
            pending.clear()
        }
    }

    /** One Photo from the connected camera, within 10 s (ADR-0009, decision 8). */
    suspend fun capture(): ReceivedPhoto {
        val current = session ?: throw CaptureFailed(CaptureFailure.NOT_CONNECTED)
        val id = requestIds.incrementAndGet()
        val reply = CompletableDeferred<Frame>()
        pending[id] = reply
        try {
            try {
                withContext(Dispatchers.IO) { current.send(Frame.Capture(id)) }
            } catch (e: IOException) {
                throw CaptureFailed(CaptureFailure.LINK_LOST)
            }
            return when (val frame = withTimeoutOrNull(CAPTURE_TIMEOUT_MILLIS) { reply.await() }) {
                null -> throw CaptureFailed(CaptureFailure.TIMED_OUT)
                is Frame.Photo -> ReceivedPhoto(frame.jpeg, frame.width, frame.height, frame.takenAt)
                is Frame.Error -> throw CaptureFailed(CaptureFailure.CAMERA_ERROR, frame.code)
                else -> throw CaptureFailed(CaptureFailure.LINK_LOST)
            }
        } finally {
            pending.remove(id)
        }
    }

    private suspend fun targets(advertised: Map<String, NsdServiceInfo>): List<LinkTarget> {
        debugTarget.value?.let { address ->
            return listOf(
                LinkTarget("debug ${address.hostString}:${address.port}", address.address, address.port, null, null),
            )
        }
        return advertised.values.mapNotNull { service ->
            val found = finder.resolve(service) ?: return@mapNotNull null
            if (found.version != null && found.version != LINK_VERSION) {
                Log.w(LINK_TAG, "Camera ${found.name} advertises link version ${found.version}")
            }
            if (!allowed(found.address)) {
                Log.w(LINK_TAG, "Camera ${found.name} resolved to ${found.address.hostAddress}: not a local address")
                return@mapNotNull null
            }
            LinkTarget(found.name, found.address, found.port, found.network, found.fingerprintPrefix)
        }
    }

    private fun allowed(address: InetAddress) = isLocalPeer(address) || (acceptsLoopback && address.isLoopbackAddress)

    /**
     * Through the Wi-Fi network the camera was found on, never the default route (phase-G.md §4).
     * The handshake and the camera's first frame share one deadline, and that frame is read under
     * [MAX_HELLO_BYTES], since nothing about the peer is known yet.
     */
    private suspend fun open(
        target: LinkTarget,
        tls: SSLContext,
        hello: Frame.Hello,
    ): Opened =
        withContext(Dispatchers.IO) {
            if (!allowed(target.address)) throw IOException("${target.address.hostAddress} is not a local address")
            val plain = connected(target)
            try {
                plain.within(GREETING_MILLIS) {
                    val socket =
                        tls.socketFactory.createSocket(
                            plain,
                            target.address.hostAddress,
                            target.port,
                            true,
                        ) as SSLSocket
                    socket.soTimeout = CameraServer.READ_TIMEOUT_MILLIS
                    socket.startHandshake()
                    val session = LinkSession(socket)
                    session.send(hello)
                    Opened(session, session.read(MAX_HELLO_BYTES))
                }
            } catch (e: Throwable) {
                plain.close()
                throw e
            }
        }

    /**
     * Through the network NSD found the camera on, else by whatever route the system picks: an app
     * under a VPN it cannot bypass may not bind to Wi-Fi at all (`EPERM`), and a phone hosting the
     * hotspot has no Wi-Fi network of its own to bind to. [allowed] still holds for either.
     */
    private fun connected(target: LinkTarget): Socket {
        val address = InetSocketAddress(target.address, target.port)
        target.network?.let { network ->
            var bound: Socket? = null
            try {
                bound = network.socketFactory.createSocket()
                bound.connect(address, CONNECT_TIMEOUT_MILLIS)
                return bound
            } catch (e: IOException) {
                bound?.close()
                if (!anotherRouteMayWork(e)) throw e
                Log.i(
                    LINK_TAG,
                    "Camera ${target.label} not reachable through network $network, trying the default route: $e",
                )
            }
        }
        val plain = Socket()
        try {
            plain.connect(address, CONNECT_TIMEOUT_MILLIS)
        } catch (e: IOException) {
            plain.close()
            throw e
        }
        return plain
    }

    companion object {
        const val PING_MILLIS = 5_000L
        const val MISSED_PINGS = 3
        const val CAPTURE_TIMEOUT_MILLIS = 10_000L
        const val NOT_FOUND_MILLIS = 10_000L
        private const val RETRY_MILLIS = 2_000L
        private const val CONNECT_TIMEOUT_MILLIS = 5_000
    }
}
