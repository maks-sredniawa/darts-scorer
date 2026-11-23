package app.dartsscorer.link

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.ext.SdkExtensions
import android.util.Log
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import java.net.InetAddress
import kotlin.coroutines.resume
import kotlin.random.Random

const val LINK_TAG = "MountedCameraLink"
private const val SERVICE_TYPE = "_dartsscorer._tcp."
private const val TXT_VERSION = "v"
private const val TXT_FINGERPRINT = "fp"
private const val RESOLVE_TIMEOUT_MILLIS = 5_000L

/**
 * Below T extensions 7 the platform drops mDNS packets unless the app holds a `MulticastLock`
 * (ADR-0009, decision 2). The Android version alone does not tell: the extensions come through Play
 * system updates.
 */
fun multicastLockNeeded(): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.R ||
        SdkExtensions.getExtensionVersion(Build.VERSION_CODES.TIRAMISU) < 7

/** Held while NSD runs, and only where [multicastLockNeeded]; [skip] is R2's debug switch. */
class MulticastHold(
    context: Context,
    private val skip: () -> Boolean,
) {
    private val wifi = context.applicationContext.getSystemService(WifiManager::class.java)
    private var lock: WifiManager.MulticastLock? = null

    @Synchronized
    fun acquire() {
        if (lock != null) return
        val needed = multicastLockNeeded()
        if (!needed || skip()) {
            Log.i(LINK_TAG, "MulticastLock not taken: needed=$needed, skipped by the debug switch=${skip()}")
            return
        }
        lock = wifi.createMulticastLock(LINK_TAG).apply { setReferenceCounted(false) }.also { it.acquire() }
        Log.i(LINK_TAG, "MulticastLock acquired")
    }

    @Synchronized
    fun release() {
        val held = lock ?: return
        held.release()
        lock = null
        Log.i(LINK_TAG, "MulticastLock released")
    }
}

/** The Mounted camera's advertisement: a random name, and only the version and a fingerprint prefix. */
class CameraAdvertiser(
    context: Context,
    private val lock: MulticastHold,
) {
    private val nsd = context.applicationContext.getSystemService(NsdManager::class.java)
    private var listener: NsdManager.RegistrationListener? = null

    @Synchronized
    fun start(
        port: Int,
        fingerprint: String,
    ) {
        stop()
        lock.acquire()
        val info =
            NsdServiceInfo().apply {
                serviceName = "camera-" + Random.nextBytes(4).toHex().lowercase()
                serviceType = SERVICE_TYPE
                setPort(port)
                setAttribute(TXT_VERSION, LINK_VERSION.toString())
                setAttribute(TXT_FINGERPRINT, fingerprint.fingerprintPrefix())
            }
        val registration =
            object : NsdManager.RegistrationListener {
                override fun onServiceRegistered(service: NsdServiceInfo) {
                    Log.i(LINK_TAG, "Advertising ${service.serviceName} on port $port")
                }

                override fun onRegistrationFailed(
                    service: NsdServiceInfo,
                    errorCode: Int,
                ) {
                    Log.w(LINK_TAG, "Advertising failed: $errorCode")
                }

                override fun onServiceUnregistered(service: NsdServiceInfo) {
                    Log.i(LINK_TAG, "Stopped advertising")
                }

                override fun onUnregistrationFailed(
                    service: NsdServiceInfo,
                    errorCode: Int,
                ) = Unit
            }
        nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, registration)
        listener = registration
    }

    @Synchronized
    fun stop() {
        listener?.let { runCatching { nsd.unregisterService(it) } }
        listener = null
        lock.release()
    }
}

/** A camera NSD resolved: where to connect, through which network, and who it says it is. */
class FoundCamera(
    val name: String,
    val address: InetAddress,
    val port: Int,
    val network: Network?,
    val version: Int?,
    val fingerprintPrefix: String?,
)

/** The Player's phone's half of NSD: what is advertised now, and a resolve per attempt. */
class CameraFinder(
    context: Context,
    private val lock: MulticastHold,
) {
    private val appContext = context.applicationContext
    private val nsd = appContext.getSystemService(NsdManager::class.java)
    private val resolving = Mutex()

    /** The cameras advertised right now, by service name. */
    fun advertised(): Flow<Map<String, NsdServiceInfo>> =
        callbackFlow {
            val seen = linkedMapOf<String, NsdServiceInfo>()
            val discovery =
                object : NsdManager.DiscoveryListener {
                    override fun onDiscoveryStarted(serviceType: String) {
                        Log.i(LINK_TAG, "Looking for cameras")
                    }

                    override fun onServiceFound(service: NsdServiceInfo) {
                        synchronized(seen) {
                            seen[service.serviceName] = service
                            trySend(seen.toMap())
                        }
                    }

                    override fun onServiceLost(service: NsdServiceInfo) {
                        synchronized(seen) {
                            seen.remove(service.serviceName)
                            trySend(seen.toMap())
                        }
                    }

                    override fun onDiscoveryStopped(serviceType: String) = Unit

                    override fun onStartDiscoveryFailed(
                        serviceType: String,
                        errorCode: Int,
                    ) {
                        Log.w(LINK_TAG, "Looking for cameras failed: $errorCode")
                    }

                    override fun onStopDiscoveryFailed(
                        serviceType: String,
                        errorCode: Int,
                    ) = Unit
                }
            lock.acquire()
            trySend(emptyMap())
            nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discovery)
            awaitClose {
                runCatching { nsd.stopServiceDiscovery(discovery) }
                lock.release()
            }
        }

    /**
     * One resolve at a time, as `resolveService` allows before API 34; null when it fails or takes
     * longer than [RESOLVE_TIMEOUT_MILLIS], since a service that left the network may never answer.
     */
    suspend fun resolve(service: NsdServiceInfo): FoundCamera? =
        resolving.withLock {
            var listener: NsdManager.ResolveListener? = null
            val found =
                withTimeoutOrNull(RESOLVE_TIMEOUT_MILLIS) {
                    suspendCancellableCoroutine { continuation ->
                        val resolve =
                            object : NsdManager.ResolveListener {
                                override fun onResolveFailed(
                                    info: NsdServiceInfo,
                                    errorCode: Int,
                                ) {
                                    Log.w(LINK_TAG, "Resolving ${info.serviceName} failed: $errorCode")
                                    if (continuation.isActive) continuation.resume(null)
                                }

                                override fun onServiceResolved(info: NsdServiceInfo) {
                                    if (continuation.isActive) continuation.resume(info.toFound())
                                }
                            }
                        listener = resolve
                        @Suppress("DEPRECATION")
                        nsd.resolveService(service, resolve)
                    }
                }
            if (found == null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                listener?.let { runCatching { nsd.stopServiceResolution(it) } }
            }
            found
        }

    private fun NsdServiceInfo.toFound(): FoundCamera? {
        @Suppress("DEPRECATION")
        val address = host ?: return null
        return FoundCamera(
            name = serviceName,
            address = address,
            port = port,
            network = wifiNetwork(),
            version = attributes[TXT_VERSION]?.let { String(it, Charsets.US_ASCII).toIntOrNull() },
            fingerprintPrefix = attributes[TXT_FINGERPRINT]?.let { String(it, Charsets.US_ASCII).uppercase() },
        )
    }

    /**
     * The Wi-Fi network the camera was found on, so the connection leaves by it rather than by the
     * default route, which may be mobile data or the emulator's `eth0` (phase-G.md §4).
     */
    private fun NsdServiceInfo.wifiNetwork(): Network? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) network?.let { return it }
        val connectivity = appContext.getSystemService(ConnectivityManager::class.java)
        @Suppress("DEPRECATION")
        return connectivity.allNetworks.firstOrNull { candidate ->
            connectivity.getNetworkCapabilities(candidate)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
    }
}
