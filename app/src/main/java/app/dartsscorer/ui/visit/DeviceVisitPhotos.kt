package app.dartsscorer.ui.visit

import android.content.Context
import androidx.core.content.FileProvider
import androidx.core.net.toUri
import app.dartsscorer.media.MediaFiles
import app.dartsscorer.media.MediaKind
import app.dartsscorer.scoring.LiteRtModel
import app.dartsscorer.scoring.PhotoReader
import app.dartsscorer.scoring.decodePhoto
import app.dartsscorer.scoring.logReadTime
import app.dartsscorer.scoring.readThreads
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

class DeviceVisitPhotos(
    context: Context,
    private val media: MediaFiles,
) : VisitPhotos {
    private val appContext = context.applicationContext
    private val cameraDir = File(appContext.cacheDir, CAMERA_DIR)
    private val photosDir = media.resolve(MediaKind.Photo.directory)
    private val authority = "${appContext.packageName}.fileprovider"

    // LiteRtModel holds one interpreter and its buffers: one Photo at a time.
    private val reading = Mutex()
    private var loaded: Loaded? = null

    override fun newCameraTarget(): String {
        cameraDir.mkdirs()
        return uriOf(File(cameraDir, "${UUID.randomUUID()}.jpg"))
    }

    override fun cameraTargets(): List<String> = cameraDir.listFiles()?.map(::uriOf).orEmpty()

    override fun discardCameraTarget(target: String) {
        target.toUri().lastPathSegment?.let { File(cameraDir, it).delete() }
    }

    override suspend fun persist(source: String): String = media.persist(source.toUri(), MediaKind.Photo).path

    override fun storedPhotos(): List<String> =
        photosDir.listFiles()?.map { "${MediaKind.Photo.directory}/${it.name}" }.orEmpty()

    override fun delete(photo: String) {
        media.delete(photo)
    }

    override fun resolve(photo: String): File = media.resolve(photo)

    override suspend fun read(photo: String): PhotoReading? =
        withContext(Dispatchers.Default) {
            reading.withLock {
                val image = decodePhoto(media.resolve(photo)) ?: return@withLock null
                val threads = readThreads(appContext)
                val reader = readerAt(threads)
                val started = System.nanoTime()
                val located = reader.read(image)
                logReadTime((System.nanoTime() - started) / 1_000_000, threads)
                PhotoReading(image.width, image.height, located)
            }
        }

    /** A new interpreter only when the count changed, which only the debug build's Settings can do. */
    private fun readerAt(threads: Int): PhotoReader {
        loaded?.takeIf { it.model.threads == threads }?.let { return it.reader }
        loaded?.model?.close()
        loaded = null
        return Loaded(LiteRtModel(appContext, threads)).also { loaded = it }.reader
    }

    private class Loaded(
        val model: LiteRtModel,
    ) {
        val reader = PhotoReader(model)
    }

    private fun uriOf(file: File): String = FileProvider.getUriForFile(appContext, authority, file).toString()

    private companion object {
        /** The `cache-path` that `res/xml/file_paths.xml` shares with the camera app. */
        const val CAMERA_DIR = "camera"
    }
}
