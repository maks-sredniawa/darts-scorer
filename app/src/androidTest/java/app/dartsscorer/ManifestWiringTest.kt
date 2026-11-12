package app.dartsscorer

import android.content.ComponentName
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.dartsscorer.ui.common.ShareChosenReceiver
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith

/**
 * What Android reads off the installed manifest. Nothing in Kotlin references these receivers — the
 * OS finds them by their intent filters — so a renamed class or a dropped filter compiles cleanly and
 * leaves the app deaf to the broadcast. Add a case here for every component the OS starts on its own.
 */
@RunWith(AndroidJUnit4::class)
class ManifestWiringTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun the_share_receiver_is_private() {
        val receiver = ComponentName(context, ShareChosenReceiver::class.java)
        assertFalse(context.packageManager.getReceiverInfo(receiver, 0).exported)
    }
}
