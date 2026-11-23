package app.dartsscorer.ui.visit

import app.dartsscorer.scoring.Located
import java.io.File

/** What one stored Photo gave: its size in pixels and what [app.dartsscorer.scoring.PhotoReader] found on it. */
data class PhotoReading(
    val width: Int,
    val height: Int,
    val located: Located,
)

/**
 * The files a Visit touches, behind an interface so [VisitViewModel] is tested on the JVM. A source and
 * a camera target are Uri strings, a Photo is `MediaFiles`' relative path.
 */
interface VisitPhotos {
    /** A content Uri in `cacheDir/camera/` for the camera app to write into; no file exists until it does. */
    fun newCameraTarget(): String

    fun cameraTargets(): List<String>

    fun discardCameraTarget(target: String)

    /**
     * A Mounted camera's JPEG, written as a new camera target so it takes the handheld Photo's path
     * from here, and so the start-up sweep removes it if the process dies before it is persisted.
     */
    suspend fun receive(jpeg: ByteArray): String

    /** Through `MediaFiles` as the `photos` kind; the relative path it wrote. */
    suspend fun persist(source: String): String

    fun storedPhotos(): List<String>

    fun delete(photo: String)

    fun resolve(photo: String): File

    /** Null when the file is missing or does not decode. */
    suspend fun read(photo: String): PhotoReading?

    /** An ended [visit] and the Darts read on it that the player [removed], before its Photo is deleted. */
    fun keep(
        visit: VisitPhase.Shown,
        removed: List<ShownDart>,
    )

    /** A Mounted camera's Photo on which no Board was found: the Photos gate A most needs (`phase-G.md` §2). */
    fun keepNoBoard(visit: VisitPhase.NoBoard)
}
