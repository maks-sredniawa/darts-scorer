package app.dartsscorer.ui.visit

import android.view.accessibility.AccessibilityNodeInfo
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.hasAnyDescendant
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isFocused
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.dartsscorer.R
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** A Mounted camera's Photo arrives with no window change, so focus must be moved to the Reading by hand. */
@RunWith(AndroidJUnit4::class)
class ReadingFocusTest {
    @get:Rule
    val compose = createComposeRule()

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val reading = instrumentation.targetContext.getString(R.string.visit_reading)

    @Test
    fun theReadingTakesFocusWhenAskedForIt() {
        var placed = false
        compose.setContent { ReadingPhoto(focusRequested = true, onFocusPlaced = { placed = true }) }
        compose.mainClock.advanceTimeBy(WINDOW_SETTLE_MS + SETTLE_SLACK_MS)
        compose.onNode(isFocused() and showing(reading)).assertExists()
        assertTrue(placed)
        compose.waitForIdle()
        val node = platformNode(instrumentation.uiAutomation.rootInActiveWindow, reading)
        assertTrue("the platform node for \"$reading\" is not focused", node?.isFocused == true)
    }

    @Test
    fun aResultReadBeforeTheWindowSettlesStillTakesFocus() {
        compose.mainClock.autoAdvance = false
        var read by mutableStateOf(false)
        val noBoard = VisitPhase.NoBoard(File("missing.jpg"), 800, 600)
        compose.setContent { if (read) NoBoardBanner(noBoard) else ReadingPhoto(focusRequested = true) {} }
        compose.mainClock.advanceTimeBy(WINDOW_SETTLE_MS / 3)
        read = true
        compose.mainClock.advanceTimeBy(WINDOW_SETTLE_MS + SETTLE_SLACK_MS)
        val title = instrumentation.targetContext.getString(R.string.visit_no_board_title)
        compose.onNode(isFocused() and showing(title)).assertExists()
    }

    private fun showing(text: String): SemanticsMatcher = hasText(text) or hasAnyDescendant(hasText(text))

    private fun platformNode(
        node: AccessibilityNodeInfo?,
        text: String,
    ): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.text?.toString() == text) return node
        return (0 until node.childCount).firstNotNullOfOrNull { platformNode(node.getChild(it), text) }
    }

    private companion object {
        const val SETTLE_SLACK_MS = 100L
    }
}
