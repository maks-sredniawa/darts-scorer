package app.dartsscorer.ui.camera

import android.util.Log
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import app.dartsscorer.R
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.media.EncodedPhoto
import app.dartsscorer.theme.Spacing
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/** Takes one Photo and logs it, until checkpoint C's link asks for Photos instead (`phase-G.md` §3). */
@Composable
fun DebugCapture(capture: suspend () -> EncodedPhoto) {
    val scope = rememberCoroutineScope()
    OutlinedButton(
        onClick = {
            scope.launch {
                try {
                    val photo = capture()
                    Log.i(
                        PairingStore.TAG,
                        "Captured a JPEG of ${photo.bytes.size} bytes, ${photo.width}x${photo.height}, " +
                            "EXIF ${if (photo.bytes.hasExif()) "present" else "none"}",
                    )
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    Log.w(PairingStore.TAG, "The capture failed", e)
                }
            }
        },
        modifier = Modifier.fillMaxWidth().padding(top = Spacing.tight),
    ) {
        Text(stringResource(R.string.debug_capture))
    }
}

private val EXIF_HEADER = "Exif\u0000\u0000".toByteArray(Charsets.ISO_8859_1)

private fun ByteArray.hasExif(): Boolean =
    (0..size - EXIF_HEADER.size).any { start -> EXIF_HEADER.indices.all { this[start + it] == EXIF_HEADER[it] } }
