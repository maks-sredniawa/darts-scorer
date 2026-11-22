package app.dartsscorer.spike

import android.app.Activity
import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.ext.SdkExtensions
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Log
import java.net.InetSocketAddress
import java.net.NetworkInterface
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
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509KeyManager
import javax.net.ssl.X509TrustManager

private const val TAG = "LinkSpike"
private const val SERVICE_TYPE = "_dartsscorer._tcp."

class SpikeActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val mode = intent.getStringExtra("mode") ?: return
        val digests = intent.getStringExtra("digests") ?: "sha256"
        val alias = intent.getStringExtra("alias") ?: "link-$digests"
        val port = intent.getIntExtra("port", 0)
        val host = intent.getStringExtra("host")
        val pin = intent.getStringExtra("pin")
        val lock = intent.getStringExtra("lock") ?: "auto"
        log("start mode=$mode sdk=${Build.VERSION.SDK_INT} alias=$alias digests=$digests ${addresses()}")
        Thread {
            runCatching {
                when (mode) {
                    "key" -> Identity.of(alias, digests)
                    "loop" -> loopback(digests)
                    "server" -> serve(Identity.of(alias, digests), port, pin, advertise = false, lock)
                    "serve-nsd" -> serve(Identity.of(alias, digests), port, pin, advertise = true, lock)
                    "client" -> connect(Identity.of(alias, digests), host!!, port, pin)
                    "discover" -> discover(Identity.of(alias, digests), pin, lock)
                    else -> log("unknown mode")
                }
            }.onFailure { Log.e(TAG, "FAIL $mode: $it", it) }
        }.start()
    }

    private fun loopback(digests: String) {
        val server = Identity.of("loop-server-$digests", digests)
        val client = Identity.of("loop-client-$digests", digests)
        val socket = tlsContext(server, client.fingerprint).serverSocketFactory.createServerSocket(0) as SSLServerSocket
        socket.needClientAuth = true
        Thread { runCatching { handleServer(socket.accept() as SSLSocket) }.onFailure { Log.e(TAG, "FAIL server: $it", it) } }.start()
        handshakeAsClient(client, "127.0.0.1", socket.localPort, server.fingerprint)
        socket.close()
        log("LOOP RESULT OK digests=$digests")
    }

    private fun serve(
        me: Identity,
        port: Int,
        pin: String?,
        advertise: Boolean,
        lock: String,
    ) {
        val socket = tlsContext(me, pin).serverSocketFactory.createServerSocket(port) as SSLServerSocket
        socket.needClientAuth = true
        log("SERVER listening on ${socket.localPort}")
        if (advertise) {
            multicastLock(lock)
            val info =
                NsdServiceInfo().apply {
                    serviceName = "spike-" + me.fingerprint.take(8)
                    serviceType = SERVICE_TYPE
                    setPort(socket.localPort)
                    setAttribute("v", "1")
                    setAttribute("fp", me.fingerprint.take(16))
                }
            nsd().registerService(
                info,
                NsdManager.PROTOCOL_DNS_SD,
                object : NsdManager.RegistrationListener {
                    override fun onServiceRegistered(s: NsdServiceInfo) = log("NSD REGISTERED ${s.serviceName}")

                    override fun onRegistrationFailed(
                        s: NsdServiceInfo,
                        code: Int,
                    ) = log("NSD REGISTER FAILED $code")

                    override fun onServiceUnregistered(s: NsdServiceInfo) = log("NSD UNREGISTERED")

                    override fun onUnregistrationFailed(
                        s: NsdServiceInfo,
                        code: Int,
                    ) = Unit
                },
            )
        }
        while (true) {
            val client = socket.accept() as SSLSocket
            Thread { runCatching { handleServer(client) }.onFailure { Log.e(TAG, "FAIL server handshake: $it", it) } }.start()
        }
    }

    private fun handleServer(socket: SSLSocket) {
        socket.use {
            it.startHandshake()
            val s = it.session
            val peer = fingerprint(s.peerCertificates[0] as X509Certificate)
            log("SERVER HANDSHAKE OK from=${it.inetAddress.hostAddress} ${s.protocol} ${s.cipherSuite} peer=$peer")
            val line = it.inputStream.bufferedReader().readLine()
            it.outputStream.write("echo:$line\n".toByteArray())
            it.outputStream.flush()
        }
    }

    private fun connect(
        me: Identity,
        host: String,
        port: Int,
        pin: String?,
    ) = handshakeAsClient(me, host, port, pin)

    private fun handshakeAsClient(
        me: Identity,
        host: String,
        port: Int,
        pin: String?,
    ) {
        val socket = tlsContext(me, pin).socketFactory.createSocket() as SSLSocket
        socket.use {
            it.connect(InetSocketAddress(host, port), 5000)
            it.soTimeout = 5000
            it.startHandshake()
            val s = it.session
            val peer = fingerprint(s.peerCertificates[0] as X509Certificate)
            it.outputStream.write("hello from sdk ${Build.VERSION.SDK_INT}\n".toByteArray())
            it.outputStream.flush()
            val reply = it.inputStream.bufferedReader().readLine()
            log("CLIENT HANDSHAKE OK to=$host:$port ${s.protocol} ${s.cipherSuite} peer=$peer reply=$reply")
        }
    }

    private fun discover(
        me: Identity,
        pin: String?,
        lock: String,
    ) {
        multicastLock(lock)
        val manager = nsd()
        manager.discoverServices(
            SERVICE_TYPE,
            NsdManager.PROTOCOL_DNS_SD,
            object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(type: String) = log("NSD DISCOVERY STARTED")

                override fun onServiceFound(s: NsdServiceInfo) {
                    log("NSD FOUND ${s.serviceName}")
                    @Suppress("DEPRECATION")
                    manager.resolveService(
                        s,
                        object : NsdManager.ResolveListener {
                            override fun onResolveFailed(
                                s: NsdServiceInfo,
                                code: Int,
                            ) = log("NSD RESOLVE FAILED $code")

                            override fun onServiceResolved(s: NsdServiceInfo) {
                                @Suppress("DEPRECATION")
                                val address = s.host.hostAddress!!
                                val fp = s.attributes["fp"]?.let { String(it) }
                                log("NSD RESOLVED ${s.serviceName} $address:${s.port} fp=$fp")
                                Thread {
                                    runCatching { handshakeAsClient(me, address, s.port, pin) }
                                        .onFailure { Log.e(TAG, "FAIL client: $it", it) }
                                }.start()
                            }
                        },
                    )
                }

                override fun onServiceLost(s: NsdServiceInfo) = log("NSD LOST ${s.serviceName}")

                override fun onDiscoveryStopped(type: String) = log("NSD DISCOVERY STOPPED")

                override fun onStartDiscoveryFailed(
                    type: String,
                    code: Int,
                ) = log("NSD DISCOVERY FAILED $code")

                override fun onStopDiscoveryFailed(
                    type: String,
                    code: Int,
                ) = Unit
            },
        )
    }

    private fun multicastLock(mode: String) {
        val needed =
            Build.VERSION.SDK_INT < 30 ||
                SdkExtensions.getExtensionVersion(Build.VERSION_CODES.TIRAMISU) < 7
        val take = mode == "on" || (mode == "auto" && needed)
        log("MULTICAST LOCK needed=$needed taken=$take")
        if (take) {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifi.createMulticastLock(TAG).apply { setReferenceCounted(false) }.acquire()
            log("MULTICAST LOCK ACQUIRED")
        }
    }

    private fun nsd() = getSystemService(Context.NSD_SERVICE) as NsdManager

    private fun addresses() =
        NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp }.joinToString(" ") { nif ->
            nif.name + "=" + nif.inetAddresses.toList().joinToString(",") { it.hostAddress ?: "" }
        }
}

class Identity(
    val alias: String,
    val key: PrivateKey,
    val certificate: X509Certificate,
) {
    val fingerprint = fingerprint(certificate)

    companion object {
        fun of(
            alias: String,
            digests: String,
        ): Identity {
            val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            if (!store.containsAlias(alias)) {
                val allowed =
                    when (digests) {
                        "sha256" -> arrayOf(KeyProperties.DIGEST_SHA256)
                        "none" -> arrayOf(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
                        else -> arrayOf(
                            KeyProperties.DIGEST_NONE,
                            KeyProperties.DIGEST_SHA256,
                            KeyProperties.DIGEST_SHA384,
                            KeyProperties.DIGEST_SHA512,
                        )
                    }
                KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").apply {
                    initialize(
                        KeyGenParameterSpec
                            .Builder(alias, KeyProperties.PURPOSE_SIGN)
                            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                            .setDigests(*allowed)
                            .build(),
                    )
                }.generateKeyPair()
            }
            val entry = store.getEntry(alias, null) as KeyStore.PrivateKeyEntry
            val certificate = entry.certificate as X509Certificate
            Log.i(
                TAG,
                "KEY $alias digests=${digests} class=${entry.privateKey.javaClass.name} " +
                    "subject=${certificate.subjectX500Principal} sigAlg=${certificate.sigAlgName} fp=${fingerprint(certificate)}",
            )
            return Identity(alias, entry.privateKey, certificate)
        }
    }
}

fun fingerprint(certificate: X509Certificate) = MessageDigest.getInstance("SHA-256").digest(certificate.encoded).joinToString("") { "%02x".format(it) }

private fun log(message: String) {
    Log.i(TAG, message)
}

fun tlsContext(
    me: Identity,
    pin: String?,
): SSLContext {
    val keys =
        object : X509KeyManager {
            override fun getClientAliases(
                type: String?,
                issuers: Array<out Principal>?,
            ) = arrayOf(me.alias)

            override fun chooseClientAlias(
                types: Array<out String>?,
                issuers: Array<out Principal>?,
                socket: Socket?,
            ) = me.alias

            override fun getServerAliases(
                type: String?,
                issuers: Array<out Principal>?,
            ) = arrayOf(me.alias)

            override fun chooseServerAlias(
                type: String?,
                issuers: Array<out Principal>?,
                socket: Socket?,
            ) = me.alias

            override fun getCertificateChain(alias: String?) = arrayOf(me.certificate)

            override fun getPrivateKey(alias: String?) = me.key
        }
    val pinned =
        object : X509TrustManager {
            private fun check(chain: Array<out X509Certificate>) {
                val seen = fingerprint(chain[0])
                if (pin != null && pin != "any" && seen != pin) {
                    log("PIN REJECTED seen=$seen expected=$pin")
                    throw CertificateException("not the pinned peer")
                }
            }

            override fun checkClientTrusted(
                chain: Array<out X509Certificate>,
                authType: String?,
            ) = check(chain)

            override fun checkServerTrusted(
                chain: Array<out X509Certificate>,
                authType: String?,
            ) = check(chain)

            override fun getAcceptedIssuers() = arrayOf<X509Certificate>()
        }
    return SSLContext.getInstance("TLS").apply { init(arrayOf(keys), arrayOf(pinned), null) }
}
