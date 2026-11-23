package app.dartsscorer.link

import android.content.Context
import android.util.Log
import app.dartsscorer.camera.PairingPayload
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.camera.PhoneRole
import app.dartsscorer.media.EncodedPhoto
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLSocket

/** What the camera screen's status line says (ADR-0009, decision 8). */
enum class CameraLinkState {
    WAITING,
    CONNECTED,

    /** The pinned Player's phone came back in pairing mode: it dropped its pin, so this one went too. */
    PAIR_AGAIN,
    OUTDATED,
}

/** Thrown by a capture that cannot take a Photo, with the code the Player's phone is sent. */
class CaptureRefused(
    val code: CaptureError,
) : Exception(code.name)

/**
 * The Mounted camera's end of the link (ADR-0009, decisions 2 to 4): listens on a port the system
 * picks, advertises it by NSD, and answers only the pinned Player's phone over mutual TLS.
 */
class CameraServer(
    context: Context,
    private val identity: suspend () -> LinkIdentity,
    private val pairing: PairingStore,
    private val appVersion: String,
    private val acceptsLoopback: Boolean,
    skipLock: () -> Boolean,
) {
    private val advertiser = CameraAdvertiser(context, MulticastHold(context, skipLock))
    private val sessions = ConcurrentHashMap.newKeySet<LinkSession>()
    private val capturing = AtomicBoolean(false)
    private val mutableState = MutableStateFlow(CameraLinkState.WAITING)
    val state: StateFlow<CameraLinkState> = mutableState.asStateFlow()

    @Volatile private var pin: String? = null

    /** Held in memory only, until the Player's phone asks for its proof once. */
    @Volatile private var token: String? = null

    /** The camera scanned or was pasted [payload]; its pin is stored by the caller. */
    fun expectPairing(payload: PairingPayload) {
        token = payload.token
        mutableState.value = CameraLinkState.WAITING
    }

    /** Unpaired here: the token goes, and so does every open connection. */
    fun forget() {
        token = null
        pin = null
        sessions.forEach { it.close() }
    }

    /** Listens until cancelled; [capture] runs on the main thread. */
    suspend fun serve(capture: suspend () -> EncodedPhoto): Unit =
        coroutineScope {
            val me = identity()
            pin = pairing.playerPin.first()
            launch { pairing.playerPin.collect { pin = it } }
            ServerSocket(0).useCancellably { server ->
                advertiser.start(server.localPort, me.fingerprint)
                Log.i(LINK_TAG, "Listening on port ${server.localPort} as ${me.fingerprint}")
                try {
                    while (true) {
                        val socket = server.accept()
                        launch {
                            try {
                                answer(me, socket, capture)
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                Log.w(LINK_TAG, "A connection failed: $e")
                            }
                        }
                    }
                } finally {
                    advertiser.stop()
                }
            }
        }

    private suspend fun answer(
        me: LinkIdentity,
        plain: Socket,
        capture: suspend () -> EncodedPhoto,
    ) {
        val address = plain.inetAddress
        if (!isLocalPeer(address) && !(acceptsLoopback && address.isLoopbackAddress)) {
            Log.w(LINK_TAG, "Refused ${address.hostAddress}: not a local address")
            plain.close()
            return
        }
        val tls = linkTlsContext(me, trusts = { it == pin })
        val socket = tls.socketFactory.createSocket(plain, address.hostAddress, plain.port, true) as SSLSocket
        socket.useClientMode = false
        socket.needClientAuth = true
        socket.soTimeout = READ_TIMEOUT_MILLIS
        socket.useCancellably {
            try {
                socket.startHandshake()
            } catch (e: IOException) {
                Log.w(LINK_TAG, "Refused ${address.hostAddress}: the handshake failed, not the pinned phone ($e)")
                return@useCancellably
            }
            val session = LinkSession(socket)
            val peer = session.peerFingerprint
            Log.i(LINK_TAG, "Handshake with $peer at ${session.peerAddress}, ${session.protocol}")
            try {
                if (greet(me, session, peer)) serveFrames(session, capture)
            } catch (e: IOException) {
                Log.i(LINK_TAG, "The Player's phone dropped: $e")
            }
        }
    }

    /** True when this is a working connection rather than pairing or a version mismatch. */
    private suspend fun greet(
        me: LinkIdentity,
        session: LinkSession,
        peer: String,
    ): Boolean {
        val ours = Frame.Hello(PhoneRole.MOUNTED_CAMERA, appVersion)
        when (val hello = session.read()) {
            is Frame.ForeignHello -> {
                session.send(ours)
                Log.w(LINK_TAG, "The Player's phone speaks link version ${hello.version}, this one $LINK_VERSION")
                mutableState.value = CameraLinkState.OUTDATED
                return false
            }
            is Frame.Hello -> {
                val nonce =
                    hello.nonce ?: run {
                        session.send(ours)
                        return true
                    }
                val pending = token
                if (pending != null) {
                    session.send(
                        Frame.Hello(
                            PhoneRole.MOUNTED_CAMERA,
                            appVersion,
                            proof = pairingProof(pending, nonce, me.fingerprint, peer),
                        ),
                    )
                    token = null
                    Log.i(LINK_TAG, "Sent the pairing proof to $peer, pinned as the Player's phone")
                } else {
                    pairing.unpairPlayer()
                    pin = null
                    mutableState.value = CameraLinkState.PAIR_AGAIN
                    session.send(ours)
                    Log.i(LINK_TAG, "The pinned phone $peer is pairing again without a token here: unpinned it")
                }
                return false
            }
            else -> throw FrameException("Expected HELLO first")
        }
    }

    private suspend fun CoroutineScope.serveFrames(
        session: LinkSession,
        capture: suspend () -> EncodedPhoto,
    ) {
        sessions += session
        mutableState.value = CameraLinkState.CONNECTED
        try {
            while (true) {
                when (val frame = session.read()) {
                    Frame.Ping -> session.send(Frame.Pong)
                    is Frame.Capture -> launch { answerCapture(session, frame.requestId, capture) }
                    else -> throw FrameException("Unexpected ${frame::class.simpleName} from the Player's phone")
                }
            }
        } finally {
            sessions -= session
            mutableState.update {
                if (sessions.isEmpty() &&
                    it == CameraLinkState.CONNECTED
                ) {
                    CameraLinkState.WAITING
                } else {
                    it
                }
            }
        }
    }

    private suspend fun answerCapture(
        session: LinkSession,
        requestId: Int,
        capture: suspend () -> EncodedPhoto,
    ) {
        if (!capturing.compareAndSet(false, true)) {
            session.send(Frame.Error(requestId, CaptureError.BUSY))
            return
        }
        try {
            val takenAt = System.currentTimeMillis()
            val reply =
                try {
                    val photo = withContext(Dispatchers.Main) { capture() }
                    Frame.Photo(requestId, takenAt, photo.width, photo.height, photo.bytes)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: CaptureRefused) {
                    Frame.Error(requestId, e.code)
                } catch (e: IllegalStateException) {
                    Frame.Error(requestId, CaptureError.NOT_READY)
                } catch (e: Exception) {
                    Log.w(LINK_TAG, "The capture for request $requestId failed", e)
                    Frame.Error(requestId, CaptureError.FAILED)
                }
            session.send(reply)
            Log.i(LINK_TAG, "Answered request $requestId: ${reply.describe()}")
        } catch (e: IOException) {
            Log.i(LINK_TAG, "Request $requestId's answer was dropped: $e")
        } finally {
            capturing.set(false)
        }
    }

    companion object {
        /** Three of the Player's phone's 5 s pings missed, and a little more. */
        const val READ_TIMEOUT_MILLIS = 20_000
    }
}

internal fun Frame.describe(): String =
    when (this) {
        is Frame.Photo -> "a Photo of ${jpeg.size} bytes, ${width}x$height"
        is Frame.Error -> "error ${code.name}"
        else -> this::class.simpleName ?: "frame"
    }
