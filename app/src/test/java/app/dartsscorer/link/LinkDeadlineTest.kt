package app.dartsscorer.link

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicInteger

/** A slow or silent peer is cut off and cannot hold up the real camera. Fails toward the link hanging on a stranger. */
class LinkDeadlineTest {
    @Test
    fun `a peer that never answers is cut off at the deadline, not the read timeout`() =
        runBlocking {
            ServerSocket(0, 1, InetAddress.getLoopbackAddress()).use { server ->
                val socket = Socket(server.inetAddress, server.localPort)
                socket.soTimeout = 60_000
                val started = System.nanoTime()
                val failure =
                    runCatching {
                        withContext(
                            Dispatchers.IO,
                        ) { socket.within(200) { socket.getInputStream().read() } }
                    }
                val tookMillis = (System.nanoTime() - started) / 1_000_000
                assertTrue(failure.exceptionOrNull() is IOException)
                assertTrue("took $tookMillis ms", tookMillis < 5_000)
                assertTrue(socket.isClosed)
            }
        }

    @Test
    fun `work finished in time leaves the socket open`() =
        runBlocking {
            ServerSocket(0, 1, InetAddress.getLoopbackAddress()).use { server ->
                val socket = Socket(server.inetAddress, server.localPort)
                assertEquals(7, withContext(Dispatchers.IO) { socket.within(5_000) { 7 } })
                delay(50)
                assertTrue(!socket.isClosed)
                socket.close()
            }
        }

    @Test
    fun `a peer that hangs does not stop another from winning`() =
        runTest {
            val winner =
                race(
                    listOf("stranger", "camera"),
                    { if (it == "stranger") awaitCancellation() else it },
                    wins = { it == "camera" },
                )
            assertEquals(listOf("camera"), winner)
        }

    @Test
    fun `results that lose to the winner are discarded`() =
        runTest {
            val discarded = AtomicInteger()
            val result =
                race(
                    listOf(1, 2, 3),
                    { it },
                    wins = { it == 1 },
                    discard = { discarded.incrementAndGet() },
                )
            assertEquals(listOf(1), result)
            assertEquals(2, discarded.get())
        }

    @Test
    fun `with no winner every result comes back`() =
        runTest {
            assertEquals(setOf(1, 2, 3), race(listOf(1, 2, 3), { it }, wins = { false }).toSet())
            assertEquals(emptyList<Int>(), race(emptyList<Int>(), { it }, wins = { true }))
        }
}
