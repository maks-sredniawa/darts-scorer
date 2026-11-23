package app.dartsscorer.ui.camera

import androidx.compose.runtime.Composable
import app.dartsscorer.link.ReceivedPhoto

@Composable
fun DebugCameraLink() = Unit

@Suppress("UNUSED_PARAMETER")
@Composable
fun DebugPlayerLink(capture: suspend () -> ReceivedPhoto) = Unit
