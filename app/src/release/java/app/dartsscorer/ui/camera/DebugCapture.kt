package app.dartsscorer.ui.camera

import androidx.compose.runtime.Composable
import app.dartsscorer.media.EncodedPhoto

/** The release half of the debug capture seam: nothing. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun DebugCapture(capture: suspend () -> EncodedPhoto) = Unit
