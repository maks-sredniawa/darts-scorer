package app.dartsscorer.scoring

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DecodingTest {
    @Test
    fun noBoardDecodesAndFindsNothing() = check("no-board")

    @Test
    fun twoDartsInOneBedStayTwo() = check("two-in-one-bed")

    @Test
    fun threeDartsInThreeBeds() = check("three-beds")

    @Test
    fun aPeakJustInsideTheFarthestRadiusIsKept() {
        assertEquals(
            listOf(0),
            Decoding.keptEntries(listOf(Point(0.0, radii(Decoding.FARTHEST_RADII - 0.01))), listOf(0.9)),
        )
    }

    @Test
    fun aPeakJustBeyondTheFarthestRadiusIsDropped() {
        assertEquals(
            emptyList<Int>(),
            Decoding.keptEntries(listOf(Point(radii(Decoding.FARTHEST_RADII + 0.01), 0.0)), listOf(0.9)),
        )
    }

    @Test
    fun aDroppedFarPeakGivesItsPlaceToTheNextMostConfident() {
        val boardMm =
            listOf(Point(0.0, 20.0), Point(radii(1.81), 0.0), Point(-30.0, 0.0), Point(0.0, -60.0), Point(90.0, 0.0))
        assertEquals(listOf(0, 2, 3), Decoding.keptEntries(boardMm, listOf(0.9, 0.85, 0.8, 0.7, 0.3)))
    }

    private fun radii(count: Double) = count * Board.OUTER_DOUBLE.outerMm

    private fun check(name: String) {
        val record = Fixtures.json("heads-$name.json").jsonObject
        val heads = Heads(Fixtures.tensor(record.getValue("board")), Fixtures.tensor(record.getValue("entry")))
        val decoded = Decoding.decode(heads)

        val calibration = record.getValue("calibration").jsonObject
        assertEquals(
            "$name: channels found",
            calibration.keys.map(String::toInt).sorted(),
            decoded.calibration.keys.sorted(),
        )
        calibration.forEach { (channel, peak) ->
            assertPeak("$name channel $channel", peak, decoded.calibration.getValue(channel.toInt()))
        }
        val entries = record.getValue("entries").jsonArray
        assertEquals("$name: Entry points", entries.size, decoded.entries.size)
        entries.forEachIndexed { i, peak -> assertPeak("$name Entry point $i", peak, decoded.entries[i]) }

        val expected = record.getValue("located").jsonObject
        val located = PhotoReader.located(Homography(Fixtures.doubles(record.getValue("matrix"))), heads)
        assertEquals("$name: Board found", expected.getValue("found").jsonPrimitive.boolean, located.found)
        if (expected.getValue("to_board") == JsonNull) {
            assertNull(located.toBoard)
            return
        }
        val toBoard = Fixtures.doubles(expected.getValue("to_board"))
        toBoard.forEachIndexed { i, value ->
            assertEquals(
                "$name: homography[$i]",
                value,
                located.toBoard!!.values[i],
                1e-9 * (1 + Math.abs(value)),
            )
        }
        assertEquals("$name: inliers", expected.getValue("calibration").jsonObject.keys, located.calibration.keys)
        val darts = expected.getValue("darts").jsonArray
        assertEquals("$name: Darts kept", darts.size, located.darts.size)
        darts.forEachIndexed { i, dart ->
            val fields = dart.jsonArray
            assertEquals("$name Dart $i x", fields[0].jsonPrimitive.double, located.darts[i].x, 1e-4)
            assertEquals("$name Dart $i y", fields[1].jsonPrimitive.double, located.darts[i].y, 1e-4)
            assertEquals("$name Dart $i Score", fields[3].jsonPrimitive.content, located.darts[i].score.token)
        }
    }

    private fun assertPeak(
        what: String,
        expected: JsonElement,
        peak: Peak,
    ) {
        val (x, y, confidence) = Fixtures.doubles(expected).toList()
        assertEquals("$what x", x, peak.x, 1e-4)
        assertEquals("$what y", y, peak.y, 1e-4)
        assertEquals("$what confidence", confidence, peak.confidence, 1e-12)
    }
}
