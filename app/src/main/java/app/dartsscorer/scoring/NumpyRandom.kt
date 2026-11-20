package app.dartsscorer.scoring

/**
 * numpy's `default_rng(0)` and its `choice(n, k, replace=False)`, bit for bit, so RANSAC draws the
 * same sets of four as `ml/`'s `ransac` and the gate compares the port rather than two random walks.
 * Python's `ransac` seeds a fresh generator on every call; so does every [NumpyRandom].
 */
internal class NumpyRandom {
    private var high = SEED_STATE_HIGH
    private var low = SEED_STATE_LOW
    private var buffered: Long? = null

    /** PCG64: one 128-bit LCG step, then the XSL-RR output of the new state. */
    fun next64(): Long {
        val productHigh = high * MULTIPLIER_LOW + low * MULTIPLIER_HIGH + unsignedMultiplyHigh(low, MULTIPLIER_LOW)
        val productLow = low * MULTIPLIER_LOW
        val sumLow = productLow + INCREMENT_LOW
        val carry = if (java.lang.Long.compareUnsigned(sumLow, productLow) < 0) 1L else 0L
        high = productHigh + INCREMENT_HIGH + carry
        low = sumLow
        return java.lang.Long.rotateRight(high xor low, (high ushr 58).toInt())
    }

    private fun next32(): Long {
        buffered?.let {
            buffered = null
            return it
        }
        val next = next64()
        buffered = next ushr 32
        return next and MASK32
    }

    /** An integer in [0, inclusiveMax] by Lemire's method, as numpy's `random_bounded_uint64` draws one. */
    fun bounded(inclusiveMax: Int): Int {
        if (inclusiveMax == 0) return 0
        val exclusive = inclusiveMax.toLong() + 1
        var product = next32() * exclusive
        var leftover = product and MASK32
        if (leftover < exclusive) {
            val threshold = (MASK32 - inclusiveMax) % exclusive
            while (leftover < threshold) {
                product = next32() * exclusive
                leftover = product and MASK32
            }
        }
        return (product ushr 32).toInt()
    }

    /** `choice(population, size, replace=False)`: Floyd's algorithm over a hash set, then a shuffle. */
    fun choice(
        population: Int,
        size: Int,
    ): IntArray {
        require(size in 0..population && population <= 10_000)
        val picked = IntArray(size)
        var mask = (1.2 * size).toInt()
        for (shift in intArrayOf(1, 2, 4, 8, 16)) mask = mask or (mask ushr shift)
        val slots = IntArray(mask + 1) { EMPTY }
        for (j in population - size until population) {
            val value = bounded(j)
            var slot = value and mask
            while (slots[slot] != EMPTY && slots[slot] != value) slot = (slot + 1) and mask
            if (slots[slot] == EMPTY) {
                slots[slot] = value
                picked[j - population + size] = value
            } else {
                slot = j and mask
                while (slots[slot] != EMPTY) slot = (slot + 1) and mask
                slots[slot] = j
                picked[j - population + size] = j
            }
        }
        for (i in size - 1 downTo 1) {
            val j = bounded(i)
            val kept = picked[j]
            picked[j] = picked[i]
            picked[i] = kept
        }
        return picked
    }

    private companion object {
        const val EMPTY = -1
        const val MASK32 = 0xFFFFFFFFL

        // numpy's PCG64 state after seeding with 0: `np.random.default_rng(0).bit_generator.state`.
        const val SEED_STATE_HIGH = 0x1aa1b5345996452dL
        const val SEED_STATE_LOW = 0x09585eb7a69561e3L
        const val INCREMENT_HIGH = 0x418ddadb3af71a82L
        const val INCREMENT_LOW = 0x588133bc447873a9L
        const val MULTIPLIER_HIGH = 0x2360ed051fc65da4L
        const val MULTIPLIER_LOW = 0x4385df649fccf645L

        fun unsignedMultiplyHigh(
            a: Long,
            b: Long,
        ): Long {
            val aLow = a and MASK32
            val aHigh = a ushr 32
            val bLow = b and MASK32
            val bHigh = b ushr 32
            val lowLow = aLow * bLow
            val middle1 = aHigh * bLow + (lowLow ushr 32)
            val middle2 = aLow * bHigh + (middle1 and MASK32)
            return aHigh * bHigh + (middle1 ushr 32) + (middle2 ushr 32)
        }
    }
}
