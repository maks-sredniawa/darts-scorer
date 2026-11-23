package app.dartsscorer.link

import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress

/**
 * Whether the link may talk to [address] (ADR-0009, decision 3): RFC 1918, 169.254/16, fe80::/10 and
 * fc00::/7 only. With `INTERNET` declared, this check is what keeps a Photo on the local network.
 */
fun isLocalPeer(address: InetAddress): Boolean {
    val bytes = address.address
    val first = bytes[0].toInt() and 0xFF
    val second = bytes[1].toInt() and 0xFF
    return when (address) {
        is Inet4Address ->
            first == 10 ||
                (first == 172 && second in 16..31) ||
                (first == 192 && second == 168) ||
                (first == 169 && second == 254)
        is Inet6Address -> (first == 0xFE && (second and 0xC0) == 0x80) || (first and 0xFE) == 0xFC
        else -> false
    }
}
