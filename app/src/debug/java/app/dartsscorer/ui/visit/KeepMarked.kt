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
import java.util.UUID

fun keepMarked(
    context: Context,
    visit: VisitPhase.Shown,
    removed: List<ShownDart>,
) {
    try {
        keepMarkedIn(markedDir(context), visit, removed, Instant.now())
    } catch (e: Exception) {
        Log.w("KeepMarked", "the Visit was not kept", e)
    }
}

/** Named after the Photo, so keeping the same Visit again replaces its record rather than adding one. */
internal fun keepMarkedIn(
    dir: File,
    visit: VisitPhase.Shown,
    removed: List<ShownDart>,
    keptAt: Instant,
) {
    dir.mkdirs()
    val name = visit.photo.nameWithoutExtension
    val photo = File(dir, "$name.jpg")
    if (!photo.sameSizeAs(visit.photo)) write(photo) { visit.photo.copyTo(it, overwrite = true) }
    val record = MarkedVisit.of(visit, removed, keptAt, photo.name)
    write(File(dir, "$name.json")) { it.writeText(JSON.encodeToString(MarkedVisit.serializer(), record)) }
}

fun markedVisits(context: Context): Int = markedDir(context).listFiles { file -> file.extension == "json" }?.size ?: 0

private fun markedDir(context: Context) = File(context.filesDir, "marked")

private fun File.sameSizeAs(other: File) = exists() && length() == other.length()

// Written aside and renamed, so a pull never takes a half-written file for a whole one; the part's own
// name lets two keeps of one Visit overlap without writing into the same file.
private inline fun write(
    target: File,
    body: (File) -> Unit,
) {
    val part = File(target.parentFile, "${target.name}.${UUID.randomUUID()}.part")
    try {
        body(part)
        if (!part.renameTo(target)) throw IOException("could not rename ${part.name}")
    } finally {
        part.delete()
    }
}

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

@Serializable
private data class MarkedDart(
    val number: Int,
    val read: MarkedRead?,
    val at: MarkedPoint?,
    val score: String,
    val unsure: Boolean,
    val corrected: Boolean,
    val moved: Boolean,
    val filled: Boolean,
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
                filled = dart.filled,
            )
    }
}

@Serializable
private data class RemovedDart(
    val number: Int,
    val read: MarkedRead,
)
