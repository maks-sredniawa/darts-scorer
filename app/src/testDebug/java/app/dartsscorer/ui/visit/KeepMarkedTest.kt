package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.time.Instant

class KeepMarkedTest {
    @get:Rule val folder = TemporaryFolder()

    private val photo by lazy {
        File(folder.newFolder("photos"), "0b7c4e1a.jpg").apply { writeBytes(byteArrayOf(1, 2, 3, 4)) }
    }
    private val marked by lazy { File(folder.root, "marked") }

    private fun entered(vararg scores: Score) =
        VisitPhase.Entered(photo, 800, 600, scores.mapIndexed { i, score -> ShownDart(i + 1, null, score) })

    private fun record(name: String) = Json.parseToJsonElement(File(marked, name).readText()).jsonObject

    @Test
    fun `keeping the same Visit again replaces its record, named after the Photo`() {
        keepMarkedIn(marked, entered(Score(Ring.TREBLE, 20)), emptyList(), Instant.parse("2026-11-20T10:00:00Z"))
        keepMarkedIn(
            marked,
            entered(Score(Ring.TREBLE, 20), Score(Ring.SINGLE, 5)),
            emptyList(),
            Instant.parse("2026-11-20T10:05:00Z"),
        )
        assertEquals(setOf("0b7c4e1a.jpg", "0b7c4e1a.json"), marked.list()!!.toSet())
        assertArrayEquals(photo.readBytes(), File(marked, "0b7c4e1a.jpg").readBytes())
        val record = record("0b7c4e1a.json")
        assertEquals("2026-11-20T10:05:00Z", record.getValue("keptAt").jsonPrimitive.content)
        assertEquals(65, record.getValue("total").jsonPrimitive.int)
        assertEquals("0b7c4e1a.jpg", record.getValue("photo").jsonPrimitive.content)
    }

    @Test
    fun `a Visit whose Photo is gone keeps nothing and leaves no part behind`() {
        val visit = entered(Score(Ring.TREBLE, 20))
        photo.delete()
        val failed = runCatching { keepMarkedIn(marked, visit, emptyList(), Instant.EPOCH) }
        assertTrue(failed.isFailure)
        assertTrue(marked.list()!!.isEmpty())
    }
}
