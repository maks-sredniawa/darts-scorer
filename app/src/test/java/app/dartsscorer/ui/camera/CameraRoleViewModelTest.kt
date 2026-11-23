package app.dartsscorer.ui.camera

import androidx.camera.core.Preview
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.viewModelScope
import app.dartsscorer.camera.DimTimer
import app.dartsscorer.camera.PairingPayload
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.camera.Rig
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.media.EncodedPhoto
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** The dimming and pairing rules of `phase-G.md` §3, on a virtual clock and a camera that is not there. */
@OptIn(ExperimentalCoroutinesApi::class)
class CameraRoleViewModelTest {
    @get:Rule val folder = TemporaryFolder()

    private val dispatcher = StandardTestDispatcher()
    private val stores = CoroutineScope(UnconfinedTestDispatcher(dispatcher.scheduler) + SupervisorJob())
    private val preferences by lazy {
        AppPreferences(PreferenceDataStoreFactory.create(scope = stores) { folder.newFile("app.preferences_pb") })
    }
    private val pairing by lazy {
        PairingStore(PreferenceDataStoreFactory.create(scope = stores) { folder.newFile("pairing.preferences_pb") })
    }
    private val code =
        PairingPayload(PairingPayload.VERSION, "0123456789ABCDEF".repeat(4), "FEDCBA9876543210".repeat(2))
    private var viewModel: CameraRoleViewModel? = null

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() {
        viewModel?.viewModelScope?.cancel()
        stores.cancel()
        Dispatchers.resetMain()
    }

    /** Ends the ViewModel's own scope with the test, or `runTest` would follow the dimmed line's moves forever. */
    private fun screen(body: suspend TestScope.() -> Unit) =
        runTest(dispatcher) {
            try {
                body()
            } finally {
                viewModel?.viewModelScope?.cancel()
            }
        }

    private fun TestScope.camera(): CameraRoleViewModel =
        CameraRoleViewModel(pairing, preferences, NoCamera, clock = { testScheduler.currentTime }, log = {})
            .also { viewModel = it }
            .also { vm -> backgroundScope.launch { vm.state.collect {} } }
            .also { runCurrent() }

    private fun TestScope.pairWithCode(vm: CameraRoleViewModel) {
        assertTrue(vm.pairWithCode(code.encode()))
        runCurrent()
    }

    private fun TestScope.idle(millis: Long = DimTimer.IDLE_MILLIS + 1) {
        advanceTimeBy(millis)
        runCurrent()
    }

    @Test
    fun `a capture while paired dims the screen after the idle time`() =
        screen {
            val vm = camera()
            pairWithCode(vm)
            vm.capture()
            idle()
            assertTrue(vm.state.value.dimmed)
        }

    @Test
    fun `pairing from a focused field still arms the dim once the field is gone`() =
        screen {
            val vm = camera()
            vm.inputActive(true)
            pairWithCode(vm)
            vm.inputActive(false)
            vm.capture()
            idle()
            assertTrue(vm.state.value.dimmed)
        }

    @Test
    fun `unpairing disarms the dim`() =
        screen {
            val vm = camera()
            pairWithCode(vm)
            vm.capture()
            vm.unpair()
            runCurrent()
            idle(DimTimer.IDLE_MILLIS * 3)
            assertFalse(vm.state.value.dimmed)
            assertEquals(false, vm.state.value.paired)
        }

    @Test
    fun `an open confirmation holds the screen lit`() =
        screen {
            val vm = camera()
            pairWithCode(vm)
            vm.capture()
            vm.inputActive(true)
            idle(DimTimer.IDLE_MILLIS * 3)
            assertFalse(vm.state.value.dimmed)
            vm.inputActive(false)
            idle()
            assertTrue(vm.state.value.dimmed)
        }

    @Test
    fun `each pairing change is counted, the first read of the store is not`() =
        screen {
            val vm = camera()
            assertEquals(false, vm.state.value.paired)
            assertEquals(0, vm.state.value.pairingSwaps)
            pairWithCode(vm)
            assertEquals(true, vm.state.value.paired)
            assertEquals(1, vm.state.value.pairingSwaps)
            vm.unpair()
            runCurrent()
            assertEquals(false, vm.state.value.paired)
            assertEquals(2, vm.state.value.pairingSwaps)
        }

    @Test
    fun `a camera opened already paired starts with no change to announce`() =
        screen {
            pairing.pinPlayer(code)
            val vm = camera()
            assertEquals(true, vm.state.value.paired)
            assertEquals(0, vm.state.value.pairingSwaps)
        }

    private object NoCamera : Rig {
        override var onQrText: ((String) -> Unit)? = null

        override suspend fun bind(
            owner: LifecycleOwner,
            displayRotation: Int,
        ) = Unit

        override fun unbind() = Unit

        override fun rotate(displayRotation: Int) = Unit

        override fun showPreviewOn(surface: Preview.SurfaceProvider?) = Unit

        override fun previewAspect(): Float? = null

        override suspend fun capture() = EncodedPhoto(ByteArray(0), 1, 1)

        override fun close() = Unit
    }
}
