package app.dartsscorer.ui.visit

import android.content.Context
import android.util.Log
import app.dartsscorer.BuildConfig
import app.dartsscorer.scoring.Point
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.io.IOException
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * A marked Visit, its Photo copied byte for byte and its reading and corrections beside it, into
 * `filesDir/marked/` for `scripts/pull-marked.py`. Outside the backup's include list (ADR-0005).
 */
fun keepMarked(
    context: Context,
    visit: VisitPhase.Shown,
    removed: List<ShownDart>,
) {
    val keptAt = Instant.now()
    val name = "${STAMP.format(keptAt)}-${UUID.randomUUID()}"
    val dir = markedDir(context)
    try {
        dir.mkdirs()
        // Written aside and renamed, so a pull never takes a half-written file for a whole one.
        write(File(dir, "$name.jpg")) { visit.photo.copyTo(it, overwrite = true) }
        val record = MarkedVisit.of(visit, removed, keptAt, "$name.jpg")
        write(File(dir, "$name.json")) { it.writeText(JSON.encodeToString(MarkedVisit.serializer(), record)) }
    } catch (e: IOException) {
        Log.w("KeepMarked", "the Visit was not kept", e)
    }
}

fun markedVisits(context: Context): Int = markedDir(context).listFiles { file -> file.extension == "json" }?.size ?: 0

private fun markedDir(context: Context) = File(context.filesDir, "marked")

private inline fun write(
    target: File,
    body: (File) -> Unit,
) {
    val part = File(target.parentFile, "${target.name}.part")
    body(part)
    if (!part.renameTo(target)) throw IOException("could not rename ${part.name}")
}

private val STAMP = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC)

private val JSON =
    Json {
        prettyPrint = true
        encodeDefaults = true
    }

@Serializable
private data class MarkedVisit(
    val versionName: String,
    val versionCode: Int,
    val keptAt: String,
    val photo: String,
    val width: Int,
    val height: Int,
    val boardFound: Boolean,
    /** Photo pixels to Board millimetres, row-major. */
    val toBoard: List<Double>?,
    val crop: MarkedCrop?,
    val total: Int,
    val darts: List<MarkedDart>,
    val removed: List<RemovedDart>,
) {
    companion object {
        fun of(
            visit: VisitPhase.Shown,
            removed: List<ShownDart>,
            keptAt: Instant,
            photo: String,
        ): MarkedVisit {
            val scored = visit as? VisitPhase.Scored
            return MarkedVisit(
                versionName = BuildConfig.VERSION_NAME,
                versionCode = BuildConfig.VERSION_CODE,
                keptAt = keptAt.toString(),
                photo = photo,
                width = visit.width,
                height = visit.height,
                boardFound = scored != null,
                toBoard = scored?.toBoard?.values?.toList(),
                crop = scored?.crop?.let { MarkedCrop(it.left, it.top, it.right, it.bottom) },
                total = visit.darts.total,
                darts = visit.darts.map(MarkedDart::of),
                removed = removed.mapNotNull { dart -> dart.read?.let { RemovedDart(dart.number, MarkedRead.of(it)) } },
            )
        }
    }
}

@Serializable
private data class MarkedPoint(
    val x: Double,
    val y: Double,
)

private fun Point.marked() = MarkedPoint(x, y)

@Serializable
private data class MarkedCrop(
    val left: Double,
    val top: Double,
    val right: Double,
    val bottom: Double,
)

/** The model's reading of a Dart, in Photo pixels, before any correction. */
@Serializable
private data class MarkedRead(
    val at: MarkedPoint,
    val score: String,
    val unsure: Boolean,
) {
    companion object {
        fun of(read: DartRead) = MarkedRead(read.at.marked(), read.score.token, read.unsure)
    }
}

/** A Dart as the Visit ended; [read] is null for one added by hand. */
@Serializable
private data class MarkedDart(
    val number: Int,
    val read: MarkedRead?,
    val at: MarkedPoint?,
    val score: String,
    val unsure: Boolean,
    val corrected: Boolean,
    val moved: Boolean,
) {
    companion object {
        fun of(dart: ShownDart) =
            MarkedDart(
                number = dart.number,
                read = dart.read?.let(MarkedRead::of),
                at = dart.at?.marked(),
                score = dart.score.token,
                unsure = dart.unsure,
                corrected = dart.corrected,
                moved = dart.moved,
            )
    }
}

@Serializable
private data class RemovedDart(
    val number: Int,
    val read: MarkedRead,
)
