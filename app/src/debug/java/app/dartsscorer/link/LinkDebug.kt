package app.dartsscorer.link

import kotlinx.coroutines.flow.MutableStateFlow
import java.net.InetSocketAddress

/**
 * The link's debug half (`phase-G.md` §4): an address to connect to instead of NSD, for emulators a
 * multicast cannot reach, and R2's switch that skips the `MulticastLock`. Loopback is accepted so the
 * address can be an `adb forward`.
 */
object LinkDebug {
    const val ACCEPTS_LOOPBACK = true
    val target = MutableStateFlow<InetSocketAddress?>(null)
    val skipMulticastLock = MutableStateFlow(false)
}
