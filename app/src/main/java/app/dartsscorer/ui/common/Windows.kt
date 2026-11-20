package app.dartsscorer.ui.common

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.unit.dp

/**
 * Below this a window is too short to stack things: the shell's tabs move to a rail, the Visit result
 * puts its Photo beside the Score, and the keypad's two groups sit side by side.
 */
internal val SHORT_WINDOW = 480.dp

@Composable
internal fun isShortWindow(): Boolean {
    val height = LocalWindowInfo.current.containerSize.height
    return with(LocalDensity.current) { height.toDp() } < SHORT_WINDOW
}
