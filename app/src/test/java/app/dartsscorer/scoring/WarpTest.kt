package app.dartsscorer.scoring

import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

class WarpTest {
    private val mean = floatArrayOf(0.485f, 0.456f, 0.406f)
    private val std = floatArrayOf(0.229f, 0.224f, 0.225f)

    @Test
    fun theInputIsPillowsToTheBit() {
        val record = Fixtures.json("warp.json").jsonObject
        val photo =
            RgbImage(
                record.getValue("width").jsonPrimitive.int,
                record.getValue("height").jsonPrimitive.int,
                Fixtures.ints(record.getValue("pixels")),
            )
        record.getValue("cases").jsonArray.forEachIndexed { case, element ->
            val fields = element.jsonObject
            val size = fields.getValue("size").jsonPrimitive.int
            val expected = Fixtures.ints(fields.getValue("expected"))
            val input = Warp.input(photo, Homography(Fixtures.doubles(fields.getValue("matrix"))), size)
            var differ = 0
            for (y in 0 until size) {
                for (x in 0 until size) {
                    for (c in 0..2) {
                        val byte = expected[(y * size + x) * 3 + c]
                        val want = (byte.toFloat() / 255f - mean[c]) / std[c]
                        if (input[c * size * size + y * size + x] != want) differ++
                    }
                }
            }
            assertEquals("case $case: values unlike Pillow's", 0, differ)
        }
    }

    @Test
    fun letterboxCentresTheLongEdge() {
        val box = Warp.letterbox(800, 600, 640)
        assertEquals(0.8, box[0, 0], 0.0)
        assertEquals(0.0, box[0, 2], 0.0)
        assertEquals(80.0, box[1, 2], 1e-12)
    }
}
