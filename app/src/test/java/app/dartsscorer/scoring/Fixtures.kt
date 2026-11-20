package app.dartsscorer.scoring

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Files `darts-ml phone-fixtures` writes from the Python reference (ml/README.md, *Phase 1's gate*). */
object Fixtures {
    fun text(name: String): String =
        checkNotNull(Fixtures::class.java.getResource("/scoring/$name")) { "no fixture $name" }.readText()

    fun json(name: String): JsonElement = Json.parseToJsonElement(text(name))

    fun doubles(element: JsonElement): DoubleArray = element.jsonArray.map { it.jsonPrimitive.double }.toDoubleArray()

    fun ints(element: JsonElement): IntArray = element.jsonArray.map { it.jsonPrimitive.int }.toIntArray()

    /** A head written sparse: per-channel defaults (the fill for heat channels, 0 for offsets), then its cells. */
    fun tensor(element: JsonElement): Tensor3 {
        val record = element.jsonObject
        val (channels, height, width) = ints(record.getValue("shape")).toList()
        val (heatFrom, heatTo) = ints(record.getValue("heat")).toList()
        val fill =
            record
                .getValue("fill")
                .jsonPrimitive.double
                .toFloat()
        val plane = height * width
        val data = FloatArray(channels * plane)
        for (channel in heatFrom until heatTo) data.fill(fill, channel * plane, (channel + 1) * plane)
        for (cell in record.getValue("cells").jsonArray) {
            val pair = cell as JsonArray
            data[pair[0].jsonPrimitive.int] = pair[1].jsonPrimitive.double.toFloat()
        }
        return Tensor3(channels, height, width, data)
    }
}
