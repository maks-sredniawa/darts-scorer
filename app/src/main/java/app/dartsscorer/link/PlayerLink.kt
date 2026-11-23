package app.dartsscorer.link

import android.net.Network
import android.net.nsd.NsdServiceInfo
import android.os.SystemClock
import android.util.Log
import app.dartsscorer.camera.PhoneRole
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocket

/** What the Player's phone says about its camera (ADR-0009, decision 8). */
enum class PlayerLinkState {
    LOOKING,
    CONNECTED,
    NOT_FOUND,

    /** The camera refused this phone's pinned certificate: it was unpaired on its side. */
    PAIR_AGAIN,
    OUTDATED,
}

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

/** What a screen needs of the link to its paired camera; [PlayerLink] is the one on a phone. */
interface CameraLink {
    val state: StateFlow<PlayerLinkState>

    /** Keeps the link to the camera pinned as [pin] up until cancelled. */
    suspend fun run(pin: String)

    /** One Photo from the connected camera, or [CaptureFailed]. */
    suspend fun capture(): ReceivedPhoto
}

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
 * it for Photos. Runs only while a screen collects it; nothing runs in the background.
 */
class PlayerLink(
    private val identity: suspend () -> LinkIdentity,
    private val finder: CameraFinder,
    private val appVersion: String,
    private val debugTarget: StateFlow<InetSocketAddress?>,
    private val acceptsLoopback: Boolean,
    private val clock: () -> Long = SystemClock::elapsedRealtime,
) : CameraLink {
    private val mutableState = MutableStateFlow(PlayerLinkState.LOOKING)
    override val state: StateFlow<PlayerLinkState> = mutableState.asStateFlow()

    @Volatile private var session: LinkSession? = null
    private val pending = ConcurrentHashMap<Int, CompletableDeferred<Frame>>()
    private val requestIds = AtomicInteger()
    private val ignored = ConcurrentHashMap.newKeySet<String>()

    /**
     * Pairing mode: offers this phone's certificate to every camera found until one answers with a
     * proof of [token]; returns that camera's fingerprint, the one to pin.
     */
    suspend fun pair(token: String): String =
        coroutineScope {
            val me = identity()
            mutableState.value = PlayerLinkState.LOOKING
            val advertised = finder.advertised().stateIn(this)
            Log.i(LINK_TAG, "Pairing as ${me.fingerprint}")
            try {
                var camera: String? = null
                while (camera == null) {
                    camera = targets(advertised.value).firstNotNullOfOrNull { pairWith(me, token, it) }
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
        var presented: String? = null
        val tls = linkTlsContext(me, trusts = { true }, onPeer = { presented = it })
        return try {
            open(target, tls).useCancellably { session ->
                val nonce = freshNonce()
                session.send(Frame.Hello(PhoneRole.PLAYER, appVersion, nonce = nonce))
                when (val hello = session.read()) {
                    is Frame.ForeignHello -> {
                        mutableState.value = PlayerLinkState.OUTDATED
                        null
                    }
                    is Frame.Hello -> {
                        val camera = presented ?: return@useCancellably null
                        if (proofHolds(hello.proof, token, nonce, camera, me.fingerprint)) {
                            Log.i(LINK_TAG, "Camera ${target.label} proved the token: pinned $camera")
                            camera
                        } else {
                            Log.w(LINK_TAG, "Camera ${target.label} ($camera) gave no valid proof: not accepted")
                            null
                        }
                    }
                    else -> null
                }
            }
        } catch (e: IOException) {
            Log.i(LINK_TAG, "Camera ${target.label} refused pairing, it has not taken this code: $e")
            null
        }
    }

    /** Connected mode: keeps the link to the camera pinned as [pin] up until cancelled. */
    override suspend fun run(pin: String): Unit =
        coroutineScope {
            val me = identity()
            val advertised = finder.advertised().stateIn(this)
            var lookingSince = clock()
            mutableState.value = PlayerLinkState.LOOKING
            Log.i(LINK_TAG, "Looking for the camera $pin")
            while (true) {
                for (target in targets(advertised.value)) {
                    if (target.fingerprintPrefix != null && target.fingerprintPrefix != pin.fingerprintPrefix()) {
                        if (ignored.add(target.label)) {
                            Log.i(LINK_TAG, "Camera ${target.label} is not the paired one: not accepted")
                        }
                        continue
                    }
                    if (connect(me, pin, target)) {
                        lookingSince = clock()
                        mutableState.value = PlayerLinkState.LOOKING
                        break
                    }
                }
                val now = clock()
                if (mutableState.value == PlayerLinkState.LOOKING && now - lookingSince > NOT_FOUND_MILLIS) {
                    mutableState.value = PlayerLinkState.NOT_FOUND
                }
                delay(RETRY_MILLIS)
            }
        }

    /** True when a connection came up and has since dropped. */
    private suspend fun connect(
        me: LinkIdentity,
        pin: String,
        target: LinkTarget,
    ): Boolean {
        var presented: String? = null
        val tls = linkTlsContext(me, trusts = { it == pin }, onPeer = { presented = it })
        var greeted = false
        try {
            open(target, tls).useCancellably { session ->
                session.send(Frame.Hello(PhoneRole.PLAYER, appVersion))
                when (val hello = session.read()) {
                    is Frame.ForeignHello -> {
                        Log.w(LINK_TAG, "The camera speaks link version ${hello.version}, this phone $LINK_VERSION")
                        mutableState.value = PlayerLinkState.OUTDATED
                        return@useCancellably
                    }
                    is Frame.Hello -> greeted = true
                    else -> throw FrameException("Expected HELLO first")
                }
                Log.i(LINK_TAG, "Connected to the camera at ${session.peerAddress}, ${session.protocol}")
                mutableState.value = PlayerLinkState.CONNECTED
                hold(session)
            }
        } catch (e: SSLException) {
            if (!greeted && presented == pin) {
                Log.w(LINK_TAG, "The paired camera refused this phone: pair again ($e)")
                mutableState.value = PlayerLinkState.PAIR_AGAIN
            } else {
                Log.w(LINK_TAG, "Camera ${target.label} failed the handshake, presented $presented: $e")
            }
        } catch (e: IOException) {
            Log.i(LINK_TAG, if (greeted) "The link dropped: $e" else "Camera ${target.label} unreachable: $e")
        }
        return greeted
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
    override suspend fun capture(): ReceivedPhoto {
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

    /** Through the Wi-Fi network the camera was found on, never the default route (phase-G.md §4). */
    private suspend fun open(
        target: LinkTarget,
        tls: SSLContext,
    ): LinkSession =
        withContext(Dispatchers.IO) {
            if (!allowed(target.address)) throw IOException("${target.address.hostAddress} is not a local address")
            val plain = target.network?.socketFactory?.createSocket() ?: Socket()
            try {
                plain.connect(InetSocketAddress(target.address, target.port), CONNECT_TIMEOUT_MILLIS)
                val socket =
                    tls.socketFactory.createSocket(plain, target.address.hostAddress, target.port, true) as SSLSocket
                socket.soTimeout = CameraServer.READ_TIMEOUT_MILLIS
                socket.startHandshake()
                LinkSession(socket)
            } catch (e: IOException) {
                plain.close()
                throw e
            }
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
