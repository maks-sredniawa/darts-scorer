package app.dartsscorer.link

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.net.InetSocketAddress

/** The release half of the link's debug seam: NSD only, the lock by the rule, no loopback peer. */
object LinkDebug {
    const val ACCEPTS_LOOPBACK = false
    val target: StateFlow<InetSocketAddress?> = MutableStateFlow(null)
    val skipMulticastLock: StateFlow<Boolean> = MutableStateFlow(false)
}
