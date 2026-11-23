package app.dartsscorer.camera

import android.content.Context
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.os.Build
import android.util.Log
import android.view.Surface
import androidx.annotation.OptIn
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraInfo
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import app.dartsscorer.media.EncodedPhoto
import app.dartsscorer.media.MediaFiles
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.ReaderException
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** No back camera this phone has is one a Mounted camera may use. */
class NoUsableCamera : Exception("No back camera that is not an ultra-wide")

/** What the camera screen needs of the camera, so its rules can be tested without one. */
interface Rig {
    var onQrText: ((String) -> Unit)?

    suspend fun bind(
        owner: LifecycleOwner,
        displayRotation: Int,
    )

    fun unbind()

    fun rotate(displayRotation: Int)

    fun showPreviewOn(surface: Preview.SurfaceProvider?)

    fun previewAspect(): Float?

    suspend fun capture(): EncodedPhoto

    fun close()
}

/**
 * The Mounted camera's CameraX half (ADR-0009, decisions 6 and 7): the main back camera bound with a
 * preview for aiming, an [ImageCapture] taken into memory, and a frame reader for the pairing QR.
 * Bound while the camera screen is in front, preview hidden or not, so a capture never waits for the
 * camera to open.
 */
@OptIn(ExperimentalCamera2Interop::class)
class CameraRig(
    context: Context,
    private val media: MediaFiles,
) : Rig {
    private val appContext = context.applicationContext
    private val frames: ExecutorService = Executors.newSingleThreadExecutor()
    private val preview = Preview.Builder().build()
    private var capture: ImageCapture? = null
    private var analysis: ImageAnalysis? = null
    private var provider: ProcessCameraProvider? = null
    private var rotation = Surface.ROTATION_0

    /** Called on the frame thread with each QR's text while set. */
    @Volatile override var onQrText: ((String) -> Unit)? = null

    override suspend fun bind(
        owner: LifecycleOwner,
        displayRotation: Int,
    ) {
        rotation = displayRotation
        val provider = cameraProvider().also { provider = it }
        val backs = provider.availableCameraInfos.filter(::isBack)
        val camera = chooseBackCamera(backs.map { it.fieldOfView() })?.let(backs::get) ?: throw NoUsableCamera()
        val corrects = camera.offersHighQualityDistortionCorrection()
        val capture =
            ImageCapture
                .Builder()
                .setTargetRotation(rotation)
                .apply {
                    if (corrects) {
                        Camera2Interop.Extender(this).setCaptureRequestOption(
                            CaptureRequest.DISTORTION_CORRECTION_MODE,
                            CameraMetadata.DISTORTION_CORRECTION_MODE_HIGH_QUALITY,
                        )
                    }
                }.build()
        val analysis =
            ImageAnalysis
                .Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setTargetRotation(rotation)
                .build()
                .also { it.setAnalyzer(frames, QrReader { onQrText }) }
        preview.targetRotation = rotation
        provider.unbindAll()
        provider.bindToLifecycle(owner, camera.cameraSelector, preview, capture, analysis)
        this.capture = capture
        this.analysis = analysis
        Log.i(
            PairingStore.TAG,
            "Bound camera ${Camera2CameraInfo.from(camera).cameraId}, " +
                "field of view ${camera.fieldOfView()?.let { "%.0f°".format(it) } ?: "unknown"}, " +
                "distortion correction ${if (corrects) "high quality" else "not offered"}",
        )
    }

    override fun unbind() {
        provider?.unbindAll()
        capture = null
        analysis = null
    }

    /**
     * Follows the display, which a 180° turn moves without recreating the activity, so a phone
     * mounted the other way up still sends an upright Photo.
     */
    override fun rotate(displayRotation: Int) {
        if (displayRotation == rotation) return
        rotation = displayRotation
        preview.targetRotation = displayRotation
        capture?.targetRotation = displayRotation
        analysis?.targetRotation = displayRotation
    }

    override fun showPreviewOn(surface: Preview.SurfaceProvider?) = preview.setSurfaceProvider(surface)

    /** The displayed preview's width over its height, once the camera has chosen a resolution. */
    override fun previewAspect(): Float? =
        preview.resolutionInfo?.let { info ->
            val width = info.resolution.width.toFloat()
            val height = info.resolution.height.toFloat()
            if (info.rotationDegrees % 180 == 0) width / height else height / width
        }

    /** One Photo, into memory and out as [MediaFiles.encodeForSending]'s JPEG; nothing is written to disk. */
    override suspend fun capture(): EncodedPhoto {
        val capture = capture ?: throw IllegalStateException("The camera is not bound")
        val (jpeg, degrees) =
            suspendCancellableCoroutine { continuation ->
                capture.takePicture(
                    ContextCompat.getMainExecutor(appContext),
                    object : ImageCapture.OnImageCapturedCallback() {
                        override fun onCaptureSuccess(image: ImageProxy) {
                            val taken = image.use { it.jpegBytes() to it.imageInfo.rotationDegrees }
                            continuation.resume(taken)
                        }

                        override fun onError(exception: ImageCaptureException) {
                            continuation.resumeWithException(exception)
                        }
                    },
                )
            }
        return media.encodeForSending(jpeg, degrees)
    }

    override fun close() {
        unbind()
        frames.shutdown()
    }

    private suspend fun cameraProvider(): ProcessCameraProvider =
        suspendCancellableCoroutine { continuation ->
            val future = ProcessCameraProvider.getInstance(appContext)
            future.addListener(
                {
                    try {
                        continuation.resume(future.get())
                    } catch (e: Exception) {
                        continuation.resumeWithException(e)
                    }
                },
                ContextCompat.getMainExecutor(appContext),
            )
        }
}

@OptIn(ExperimentalCamera2Interop::class)
private fun <T> CameraInfo.characteristic(key: CameraCharacteristics.Key<T>): T? =
    Camera2CameraInfo.from(this).getCameraCharacteristic(key)

private fun isBack(info: CameraInfo): Boolean =
    info.characteristic(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK

private fun CameraInfo.fieldOfView(): Double? {
    val focal = characteristic(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)?.firstOrNull()
    val sensor = characteristic(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE)
    if (focal == null || sensor == null) return null
    return horizontalFieldOfView(focal, maxOf(sensor.width, sensor.height))
}

private fun CameraInfo.offersHighQualityDistortionCorrection(): Boolean =
    Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
        characteristic(CameraCharacteristics.DISTORTION_CORRECTION_AVAILABLE_MODES)
            ?.contains(CameraMetadata.DISTORTION_CORRECTION_MODE_HIGH_QUALITY) == true

private fun ImageProxy.jpegBytes(): ByteArray {
    val buffer = planes[0].buffer
    return ByteArray(buffer.remaining()).also { buffer.get(it) }
}

/** Reads a QR from each frame's luminance plane while someone listens; other frames are dropped unread. */
private class QrReader(
    private val listener: () -> ((String) -> Unit)?,
) : ImageAnalysis.Analyzer {
    private val reader = QRCodeReader()
    private val hints = mapOf(DecodeHintType.TRY_HARDER to true)

    override fun analyze(image: ImageProxy) {
        val found = listener()
        if (found == null) {
            image.close()
            return
        }
        val text =
            image.use {
                val plane = it.planes[0]
                val buffer = plane.buffer
                val luminance = ByteArray(buffer.remaining()).also { bytes -> buffer.get(bytes) }
                val source =
                    PlanarYUVLuminanceSource(luminance, plane.rowStride, it.height, 0, 0, it.width, it.height, false)
                try {
                    reader.decode(BinaryBitmap(HybridBinarizer(source)), hints).text
                } catch (e: ReaderException) {
                    null
                } finally {
                    reader.reset()
                }
            }
        text?.let(found)
    }
}
