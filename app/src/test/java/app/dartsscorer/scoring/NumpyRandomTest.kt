package app.dartsscorer.scoring

import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Test

class NumpyRandomTest {
    @Test
    fun drawsTheSetsOfFourNumpyDraws() {
        val random = NumpyRandom()
        Fixtures.json("rng.json").jsonArray.forEachIndexed { i, draw ->
            val record = draw.jsonObject
            val population = record.getValue("population").jsonPrimitive.int
            assertArrayEquals(
                "draw $i of $population",
                Fixtures.ints(record.getValue("picked")),
                random.choice(population, 4),
            )
        }
    }
}
