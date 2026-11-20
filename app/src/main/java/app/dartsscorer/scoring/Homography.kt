package app.dartsscorer.scoring

import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.sqrt

/** A 3×3 projective map, row-major. A port of `ml/`'s `homography.py`. */
class Homography(
    val values: DoubleArray,
) {
    init {
        require(values.size == 9)
    }

    operator fun get(
        row: Int,
        column: Int,
    ): Double = values[row * 3 + column]

    fun project(point: Point): Point = project(point.x, point.y)

    fun project(
        x: Double,
        y: Double,
    ): Point {
        val u = x * values[0] + y * values[1] + values[2]
        val v = x * values[3] + y * values[4] + values[5]
        val w = x * values[6] + y * values[7] + values[8]
        return Point(u / w, v / w)
    }

    operator fun times(other: Homography): Homography {
        val product = DoubleArray(9)
        for (row in 0..2) {
            for (column in 0..2) {
                var sum = 0.0
                for (k in 0..2) sum += this[row, k] * other[k, column]
                product[row * 3 + column] = sum
            }
        }
        return Homography(product)
    }

    fun inverse(): Homography =
        Homography(
            Linear.solve(values, 3, IDENTITY.values.copyOf(), 3) ?: error("singular homography"),
        )

    fun scaledToUnitCorner(): Homography = Homography(DoubleArray(9) { values[it] / values[8] })

    override fun equals(other: Any?): Boolean = other is Homography && values.contentEquals(other.values)

    override fun hashCode(): Int = values.contentHashCode()

    override fun toString(): String = values.joinToString(prefix = "Homography(", postfix = ")")

    companion object {
        const val MIN_POINTS = 4
        val IDENTITY = Homography(doubleArrayOf(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

        /**
         * The normalised DLT, refined by Levenberg–Marquardt on the projection error in the target's
         * units; null where `fit` in Python raises (too few, coincident or degenerate points).
         */
        fun fit(
            source: List<Point>,
            target: List<Point>,
        ): Homography? {
            require(source.size == target.size)
            if (source.size < MIN_POINTS) return null
            val sourceNorm = normaliser(source) ?: return null
            val targetNorm = normaliser(target) ?: return null
            val s = source.map(sourceNorm::project)
            val t = target.map(targetNorm::project)
            val h = dlt(s, t) ?: return null
            return targetNorm.inverse() * refine(h, s, t) * sourceNorm
        }

        /** RANSAC's minimal fit: null where Python's `_four_point` returns None. */
        fun fourPoint(
            source: List<Point>,
            target: List<Point>,
        ): Homography? {
            val sourceNorm = normaliser(source) ?: return null
            val targetNorm = normaliser(target) ?: return null
            val svd =
                Svd.of(
                    design(source.map(sourceNorm::project), target.map(targetNorm::project)),
                    source.size * 2,
                    9,
                )
            val shared = minOf(source.size * 2, 9)
            if (svd.singular[shared - 1] < 1e-9 * svd.singular[0]) return null
            val h = targetNorm.inverse() * Homography(svd.nullVector()) * sourceNorm
            return if (abs(h[2, 2]) > 1e-12) h.scaledToUnitCorner() else null
        }

        internal fun normaliser(points: List<Point>): Homography? {
            val cx = points.sumOf { it.x } / points.size
            val cy = points.sumOf { it.y } / points.size
            val spread = points.sumOf { hypot(it.x - cx, it.y - cy) } / points.size
            if (spread == 0.0) return null
            val scale = sqrt(2.0) / spread
            return Homography(doubleArrayOf(scale, 0.0, -scale * cx, 0.0, scale, -scale * cy, 0.0, 0.0, 1.0))
        }

        private fun design(
            source: List<Point>,
            target: List<Point>,
        ): DoubleArray {
            val rows = DoubleArray(source.size * 2 * 9)
            source.forEachIndexed { i, (x, y) ->
                val (u, v) = target[i]
                doubleArrayOf(-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u).copyInto(rows, i * 18)
                doubleArrayOf(0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v).copyInto(rows, i * 18 + 9)
            }
            return rows
        }

        private fun dlt(
            source: List<Point>,
            target: List<Point>,
        ): Homography? {
            val rows = source.size * 2
            val svd = Svd.of(design(source, target), rows, 9)
            val rank = svd.singular.take(minOf(rows, 9)).count { it > 1e-9 }
            if (rank < 8) return null
            return Homography(svd.nullVector()).scaledToUnitCorner()
        }

        private fun refine(
            start: Homography,
            source: List<Point>,
            target: List<Point>,
        ): Homography {
            var params = start.values.copyOf(8)
            var cost = cost(params, source, target)
            var damping = 1e-3
            repeat(100) {
                val (residual, jacobian) = residualAndJacobian(params, source, target)
                val rows = residual.size
                val normal = DoubleArray(64)
                val gradient = DoubleArray(8)
                for (i in 0 until 8) {
                    for (j in 0 until 8) {
                        var sum = 0.0
                        for (r in 0 until rows) sum += jacobian[r * 8 + i] * jacobian[r * 8 + j]
                        normal[i * 8 + j] = sum
                    }
                    var sum = 0.0
                    for (r in 0 until rows) sum += jacobian[r * 8 + i] * residual[r]
                    gradient[i] = -sum
                }
                val damped = normal.copyOf()
                for (i in 0 until 8) damped[i * 8 + i] += damping * (normal[i * 8 + i] + 1e-12)
                val step = Linear.solve(damped, 8, gradient, 1) ?: return@repeat
                val candidate = DoubleArray(8) { params[it] + step[it] }
                val candidateCost = cost(candidate, source, target)
                if (candidateCost < cost) {
                    params = candidate
                    cost = candidateCost
                    damping /= 10
                    if (norm(step) < 1e-12 * (1 + norm(params))) return finished(params)
                } else {
                    damping *= 10
                    if (damping > 1e12) return finished(params)
                }
            }
            return finished(params)
        }

        private fun finished(params: DoubleArray) = Homography(params.copyOf(9).also { it[8] = 1.0 })

        private fun norm(values: DoubleArray): Double = sqrt(values.sumOf { it * it })

        private fun cost(
            params: DoubleArray,
            source: List<Point>,
            target: List<Point>,
        ): Double {
            val h = finished(params)
            var sum = 0.0
            source.forEachIndexed { i, point ->
                val mapped = h.project(point)
                val du = mapped.x - target[i].x
                val dv = mapped.y - target[i].y
                sum += du * du + dv * dv
            }
            return sum
        }

        /** Rows: every u residual, then every v residual, as Python stacks them. */
        private fun residualAndJacobian(
            p: DoubleArray,
            source: List<Point>,
            target: List<Point>,
        ): Pair<DoubleArray, DoubleArray> {
            val n = source.size
            val residual = DoubleArray(2 * n)
            val jacobian = DoubleArray(2 * n * 8)
            source.forEachIndexed { i, (x, y) ->
                val w = p[6] * x + p[7] * y + 1
                val u = (p[0] * x + p[1] * y + p[2]) / w
                val v = (p[3] * x + p[4] * y + p[5]) / w
                residual[i] = u - target[i].x
                residual[n + i] = v - target[i].y
                doubleArrayOf(x / w, y / w, 1 / w, 0.0, 0.0, 0.0, -u * x / w, -u * y / w).copyInto(jacobian, i * 8)
                doubleArrayOf(
                    0.0,
                    0.0,
                    0.0,
                    x / w,
                    y / w,
                    1 / w,
                    -v * x / w,
                    -v * y / w,
                ).copyInto(jacobian, (n + i) * 8)
            }
            return residual to jacobian
        }
    }
}

internal object Linear {
    /** Solves A·X = B by Gaussian elimination with partial pivoting; A is n×n, B is n×columns, both row-major. */
    fun solve(
        a: DoubleArray,
        n: Int,
        b: DoubleArray,
        columns: Int,
    ): DoubleArray? {
        val m = a.copyOf()
        val x = b.copyOf()
        for (pivot in 0 until n) {
            var best = pivot
            for (row in pivot + 1 until n) if (abs(m[row * n + pivot]) > abs(m[best * n + pivot])) best = row
            if (m[best * n + pivot] == 0.0) return null
            if (best != pivot) {
                for (k in 0 until n) m.swap(pivot * n + k, best * n + k)
                for (k in 0 until columns) x.swap(pivot * columns + k, best * columns + k)
            }
            for (row in pivot + 1 until n) {
                val factor = m[row * n + pivot] / m[pivot * n + pivot]
                if (factor == 0.0) continue
                for (k in pivot until n) m[row * n + k] -= factor * m[pivot * n + k]
                for (k in 0 until columns) x[row * columns + k] -= factor * x[pivot * columns + k]
            }
        }
        for (row in n - 1 downTo 0) {
            for (k in 0 until columns) {
                var sum = x[row * columns + k]
                for (j in row + 1 until n) sum -= m[row * n + j] * x[j * columns + k]
                x[row * columns + k] = sum / m[row * n + row]
            }
        }
        return x
    }

    private fun DoubleArray.swap(
        i: Int,
        j: Int,
    ) {
        val kept = this[i]
        this[i] = this[j]
        this[j] = kept
    }
}

/**
 * One-sided Jacobi SVD, for the DLT's 2N×9 design matrix: accurate to machine precision on the small
 * singular values the degeneracy checks compare, which an eigendecomposition of AᵀA would square away.
 */
internal class Svd private constructor(
    /** Descending; as many as the matrix has columns, the extra ones zero for a wide matrix. */
    val singular: DoubleArray,
    private val v: DoubleArray,
    private val order: IntArray,
    private val columns: Int,
) {
    /** The right singular vector of the smallest singular value: numpy's `vt[-1]`. */
    fun nullVector(): DoubleArray {
        val column = order.last()
        return DoubleArray(columns) { v[it * columns + column] }
    }

    companion object {
        fun of(
            matrix: DoubleArray,
            rows: Int,
            columns: Int,
        ): Svd {
            val a = matrix.copyOf()
            val v = DoubleArray(columns * columns).also { for (i in 0 until columns) it[i * columns + i] = 1.0 }
            for (sweep in 0 until 80) {
                var rotated = false
                for (p in 0 until columns - 1) {
                    for (q in p + 1 until columns) {
                        var alpha = 0.0
                        var beta = 0.0
                        var gamma = 0.0
                        for (r in 0 until rows) {
                            val ap = a[r * columns + p]
                            val aq = a[r * columns + q]
                            alpha += ap * ap
                            beta += aq * aq
                            gamma += ap * aq
                        }
                        if (gamma == 0.0 || abs(gamma) <= 1e-15 * sqrt(alpha * beta)) continue
                        rotated = true
                        val zeta = (beta - alpha) / (2 * gamma)
                        val t =
                            Math.signum(zeta).let { if (it == 0.0) 1.0 else it } / (abs(zeta) + sqrt(1 + zeta * zeta))
                        val c = 1 / sqrt(1 + t * t)
                        val s = c * t
                        for (r in 0 until rows) {
                            val ap = a[r * columns + p]
                            val aq = a[r * columns + q]
                            a[r * columns + p] = c * ap - s * aq
                            a[r * columns + q] = s * ap + c * aq
                        }
                        for (r in 0 until columns) {
                            val vp = v[r * columns + p]
                            val vq = v[r * columns + q]
                            v[r * columns + p] = c * vp - s * vq
                            v[r * columns + q] = s * vp + c * vq
                        }
                    }
                }
                if (!rotated) break
            }
            val norms =
                DoubleArray(columns) { column ->
                    sqrt(
                        (0 until rows).sumOf {
                            a[it * columns + column].let { x ->
                                x *
                                    x
                            }
                        },
                    )
                }
            val order = (0 until columns).sortedByDescending { norms[it] }.toIntArray()
            return Svd(DoubleArray(columns) { norms[order[it]] }, v, order, columns)
        }
    }
}
