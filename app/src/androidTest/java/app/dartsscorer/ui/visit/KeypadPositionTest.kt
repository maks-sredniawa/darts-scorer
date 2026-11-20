package app.dartsscorer.ui.visit

import android.accessibilityservice.AccessibilityServiceInfo
import android.view.accessibility.AccessibilityNodeInfo
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.dartsscorer.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** TalkBack's "n of 23" on the bed keys comes from the platform node, so that is what is read here. */
@RunWith(AndroidJUnit4::class)
class KeypadPositionTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun everyBedKeyReadsItsOwnPositionOfTwentyThree() {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.serviceInfo =
            automation.serviceInfo.apply { flags = flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS }
        compose.setContent {
            KeypadSheet(Keypad(dart = 1), {}, {}, {}, {}, {}, {})
        }
        compose.waitForIdle()

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val labels =
            (1..20).map(Int::toString) +
                listOf(R.string.keypad_outer_bull, R.string.keypad_bull, R.string.keypad_miss).map(context::getString)
        val roots = automation.windows.mapNotNull { it.root }
        labels.forEachIndexed { index, label ->
            val key = roots.firstNotNullOfOrNull { keyNamed(it, label) }
            assertNotNull("no key reads \"$label\"", key)
            val item = key!!.collectionItemInfo
            assertNotNull("\"$label\" has no position", item)
            assertEquals("\"$label\"'s position", index, item.rowIndex)
            assertEquals("\"$label\"'s column", 0, item.columnIndex)
            val group = key.parent.collectionInfo
            assertNotNull("\"$label\"'s group states no size", group)
            assertEquals("the group's size", labels.size, group.rowCount)
            assertEquals("the group's columns", 1, group.columnCount)
        }
    }

    /** The key is the checkable node and its label a child Text. Compose's nodes are walked, not searched. */
    private fun keyNamed(
        node: AccessibilityNodeInfo,
        label: String,
    ): AccessibilityNodeInfo? {
        val children = (0 until node.childCount).mapNotNull(node::getChild)
        if (node.isCheckable && children.any { it.text?.toString() == label }) return node
        return children.firstNotNullOfOrNull { keyNamed(it, label) }
    }
}
