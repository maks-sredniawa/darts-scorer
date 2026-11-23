package app.dartsscorer.link

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.InetAddress

/** `phase-G.md`, *Tests*: fails toward a Photo sent off the LAN. */
class LocalPeerTest {
    private fun local(literal: String) = isLocalPeer(InetAddress.getByName(literal))

    @Test
    fun `private, link-local and unique-local addresses are accepted`() {
        for (address in listOf(
            "10.0.2.16",
            "172.16.0.1",
            "172.31.255.254",
            "192.168.1.20",
            "169.254.10.1",
            "fe80::1",
            "febf::1",
            "fc00::1",
            "fd12:3456::1",
            "::ffff:192.168.0.5",
        )) {
            assertTrue(address, local(address))
        }
    }

    @Test
    fun `public, loopback, unspecified and carrier-grade NAT addresses are refused`() {
        for (address in listOf(
            "8.8.8.8",
            "172.15.0.1",
            "172.32.0.1",
            "192.169.0.1",
            "100.64.0.1",
            "100.127.255.254",
            "127.0.0.1",
            "0.0.0.0",
            "255.255.255.255",
            "224.0.0.251",
            "2001:4860:4860::8888",
            "::1",
            "::",
            "fec0::1",
            "ff02::fb",
        )) {
            assertFalse(address, local(address))
        }
    }
}
