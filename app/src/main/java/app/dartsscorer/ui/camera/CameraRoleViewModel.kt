package app.dartsscorer.ui.camera

import android.os.SystemClock
import android.util.Log
import androidx.camera.core.Preview
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.camera.DimSlot
import app.dartsscorer.camera.DimTimer
import app.dartsscorer.camera.PairingPayload
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.camera.PhoneRole
import app.dartsscorer.camera.Rig
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.media.EncodedPhoto
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlin.random.Random

data class CameraRoleUiState(
    /** Null until the pairing store has been read, so neither block shows before it is known. */
    val paired: Boolean? = null,
    val codeRejected: Boolean = false,
    val dimmed: Boolean = false,
    val slot: DimSlot = DimSlot.Start,
    val materialYou: Boolean = false,
    val cameraFailed: Boolean = false,
    /** How often [paired] has flipped while this screen was open: each flip is announced and moves focus. */
    val pairingSwaps: Int = 0,
)

/**
 * The camera screen (`phase-G.md` §3): this phone in its Mounted camera role, pairing by QR or pasted
 * code, capturing into memory, and dimming itself while it waits.
 */
class CameraRoleViewModel(
    private val pairing: PairingStore,
    preferences: AppPreferences,
    private val rig: Rig,
    private val clock: () -> Long = SystemClock::elapsedRealtime,
    private val random: Random = Random.Default,
    private val log: (String) -> Unit = { Log.i(PairingStore.TAG, it) },
) : ViewModel() {
    private val local = MutableStateFlow(CameraRoleUiState())
    private var timer = DimTimer()
    private var dimming: Job? = null
    private var binding: Job? = null

    @Volatile private var paired = false

    val state: StateFlow<CameraRoleUiState> =
        combine(local, preferences.materialYou) { local, materialYou ->
            local.copy(materialYou = materialYou)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), local.value)

    init {
        viewModelScope.launch { pairing.setRole(PhoneRole.MOUNTED_CAMERA) }
        viewModelScope.launch {
            pairing.playerPin.collect { pin ->
                val now = pin != null
                paired = now
                rig.onQrText = if (pin == null) ::scanned else null
                local.update {
                    val flipped = it.paired != null && it.paired != now
                    it.copy(paired = now, pairingSwaps = it.pairingSwaps + if (flipped) 1 else 0)
                }
            }
        }
    }

    fun bind(
        owner: LifecycleOwner,
        displayRotation: Int,
    ) {
        binding?.cancel()
        binding =
            viewModelScope.launch {
                try {
                    rig.bind(owner, displayRotation)
                    local.update { it.copy(cameraFailed = false) }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    Log.w(PairingStore.TAG, "The camera could not be bound", e)
                    local.update { it.copy(cameraFailed = true) }
                }
            }
    }

    fun unbind() {
        binding?.cancel()
        rig.unbind()
    }

    fun rotated(displayRotation: Int) = rig.rotate(displayRotation)

    fun showPreviewOn(surface: Preview.SurfaceProvider?) = rig.showPreviewOn(surface)

    fun previewAspect(): Float? = rig.previewAspect()

    /** The one way a Photo leaves the camera. In B only the debug build calls it. */
    suspend fun capture(): EncodedPhoto {
        val photo = rig.capture()
        timer = timer.captured(paired, clock())
        scheduleDim()
        return photo
    }

    /** The text itself stays in the field's own state: a round trip through [state] lags a frame and reorders fast input. */
    fun codeChanged() {
        local.update { it.copy(codeRejected = false) }
        timer = timer.touched(clock())
        scheduleDim()
    }

    /** True when [code] is a pairing code, which is then pinned. */
    fun pairWithCode(code: String): Boolean {
        val payload = PairingPayload.parse(code)
        local.update { it.copy(codeRejected = payload == null) }
        if (payload == null) return false
        viewModelScope.launch { pin(payload, "a pasted code") }
        return true
    }

    /** Also disarms dimming: the pairing screen it returns to is one the player is using. */
    fun unpair() {
        timer = DimTimer()
        dimming?.cancel()
        viewModelScope.launch {
            pairing.unpairPlayer()
            log("Unpaired the Player's phone")
        }
    }

    private suspend fun pin(
        payload: PairingPayload,
        route: String,
    ) {
        pairing.pinPlayer(payload)
        log("Pinned the Player's phone ${payload.fingerprint} from $route")
    }

    /** Suspends until the role is written, so the screen leaving cannot cancel it. */
    suspend fun stop() = pairing.setRole(PhoneRole.PLAYER)

    fun inputActive(active: Boolean) {
        timer = timer.input(active, clock())
        scheduleDim()
    }

    fun touched() {
        if (local.value.dimmed) return
        timer = timer.touched(clock())
        scheduleDim()
    }

    fun wake() {
        local.update { it.copy(dimmed = false) }
        timer = timer.touched(clock())
        scheduleDim()
    }

    private fun scanned(text: String) {
        val payload = PairingPayload.parse(text) ?: return
        rig.onQrText = null
        viewModelScope.launch { if (!paired) pin(payload, "a scanned QR") }
    }

    private fun scheduleDim() {
        dimming?.cancel()
        val at = timer.dimsAt() ?: return
        dimming =
            viewModelScope.launch {
                delay((at - clock()).coerceAtLeast(0))
                local.update { it.copy(dimmed = true) }
                while (true) {
                    delay(DimTimer.MOVE_MILLIS)
                    local.update { it.copy(slot = it.slot.next(random)) }
                }
            }
    }

    override fun onCleared() {
        rig.close()
    }

    companion object {
        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val app = this[APPLICATION_KEY] as MainApplication
                    CameraRoleViewModel(app.container.pairing, app.container.preferences, app.container.cameraRig())
                }
            }
    }
}
