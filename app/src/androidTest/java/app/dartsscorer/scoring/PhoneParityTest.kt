package app.dartsscorer.scoring

import android.content.Context
import android.util.Log
import androidx.core.net.toUri
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.dartsscorer.media.MediaFiles
import app.dartsscorer.media.MediaKind
import kotlinx.coroutines.test.runTest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import kotlin.math.hypot

/**
 * Phase 1's gate (phase-1.md §1), driven by `darts-ml phone-parity`, which pushes the Photos and
 * Python's results into the app's external files and runs one method at a time. Without them both
 * methods are skipped, so CI's instrumented legs stay green with no `DARTS_DATA`.
 */
@RunWith(AndroidJUnit4::class)
class PhoneParityTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val folder = File(context.getExternalFilesDir(null), "parity")
    private val sources = File(folder, "source")
    private val written = File(folder, "written")

    @Test
    fun writesEachPhotoThroughMediaFiles() =
        runTest {
            val photos = sources.listFiles { file -> file.extension == "jpg" }?.sorted().orEmpty()
            assumeTrue("no Photos pushed to $sources", photos.isNotEmpty())
            val root = File(context.cacheDir, "parity-media").apply { deleteRecursively() }
            val media = MediaFiles(context, root)
            written.deleteRecursively()
            written.mkdirs()
            photos.forEach { photo ->
                val persisted = media.persist(photo.toUri(), MediaKind.Photo)
                media.resolve(persisted.path).copyTo(File(written, photo.name))
            }
            root.deleteRecursively()
        }

    @Test
    fun matchesPythonOnEachPhoto() {
        val expectedFile = File(folder, "expected.json")
        assumeTrue("no $expectedFile pushed", expectedFile.exists())
        val photos = JSONObject(expectedFile.readText()).getJSONArray("photos")
        val reader = LiteRtModel(context)
        val lines = mutableListOf<String>()
        val boardOnOneSide = mutableListOf<String>()
        val crossingsOver = mutableListOf<String>()
        val dartsDiffer = mutableListOf<String>()
        val millis = mutableListOf<Long>()
        var worstMm = 0.0
        var bothFound = 0
        reader.use { model ->
            val pipeline = PhotoReader(model)
            for (i in 0 until photos.length()) {
                val python = photos.getJSONObject(i)
                val name = python.getString("name")
                val image = checkNotNull(decodePhoto(File(written, name))) { "cannot decode $name" }
                val started = System.nanoTime()
                val phone = pipeline.read(image)
                millis += (System.nanoTime() - started) / 1_000_000
                val pythonFound = python.getBoolean("found")
                if (pythonFound != phone.found) {
                    boardOnOneSide += "$name: Board found by ${if (phone.found) "the phone" else "Python"} only " +
                        "(Python kept ${python.getJSONObject(
                            "calibration",
                        ).length()} Calibration points, the phone ${phone.calibration.size})"
                    continue
                }
                val ours = phone.darts.map { it.score.token }.sorted()
                val theirs =
                    python
                        .getJSONArray("darts")
                        .let { d ->
                            (0 until d.length()).map { d.getJSONArray(it).getString(3) }
                        }.sorted()
                if (ours != theirs) dartsDiffer += "$name: the phone $ours, Python $theirs"
                if (!pythonFound) continue
                bothFound++
                val worst = worstCrossingMm(python.getJSONArray("crossings_px"), phone.toBoard!!)
                worstMm = maxOf(worstMm, worst)
                if (worst > PARITY_MM) crossingsOver += "$name: a crossing %.4f mm from Python's".format(worst)
            }
        }
        val count = photos.length()
        val sameDarts = count - dartsDiffer.size
        val pass = boardOnOneSide.isEmpty() && crossingsOver.isEmpty() && sameDarts >= SAME_DARTS * count
        lines += "${if (pass) "PASS" else "FAIL"}: $count Photos"
        lines +=
            "Board found by both $bothFound, by neither ${count - bothFound - boardOnOneSide.size}, by one only ${boardOnOneSide.size}"
        lines +=
            "crossings: worst %.5f mm; Photos with one over %.1f mm: %d".format(worstMm, PARITY_MM, crossingsOver.size)
        lines +=
            "kept Darts' Scores the same in $sameDarts of $count Photos (%.1f%%; the bar is %.0f%%)"
                .format(100.0 * sameDarts / count, 100 * SAME_DARTS)
        lines +=
            "both passes per Photo: median ${millis.sorted()[millis.size / 2]} ms, at ${LiteRtModel.DEFAULT_THREADS} threads"
        lines += boardOnOneSide + crossingsOver + dartsDiffer
        val report = lines.joinToString("\n")
        File(folder, "report.txt").writeText(report + "\n")
        report.lines().forEach { Log.i("PhoneParity", it) }
        assertTrue(report, pass)
    }

    private fun worstCrossingMm(
        crossingsPx: JSONArray,
        toBoard: Homography,
    ): Double =
        Board.CALIBRATION_POINTS.indices.maxOf { i ->
            val pixel = crossingsPx.getJSONArray(i)
            val mm = toBoard.project(pixel.getDouble(0), pixel.getDouble(1))
            val board = Board.CALIBRATION_POINTS[i].mm
            hypot(mm.x - board.x, mm.y - board.y)
        }

    private companion object {
        const val PARITY_MM = 0.1
        const val SAME_DARTS = 0.99
    }
}
