package app.dartsscorer.ui.camera

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.camera.PairingPayload
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.link.LINK_TAG
import app.dartsscorer.link.LinkIdentity
import app.dartsscorer.link.PlayerLink
import app.dartsscorer.link.PlayerLinkState
import app.dartsscorer.link.ReceivedPhoto
import app.dartsscorer.link.freshToken
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class AddMountedCameraUiState(
    /** The QR's payload, one line; null while this phone's key is being made. */
    val code: String? = null,
    val paired: Boolean = false,
    val link: PlayerLinkState = PlayerLinkState.LOOKING,
    /** Paired while this screen was open, so the status says *Camera paired* until the link has news. */
    val justPaired: Boolean = false,
)

/**
 * *Add a mounted camera* on the Player's phone (`phase-G.md` §4): the QR and its text while unpaired,
 * the paired camera and its link state once paired. The token lives here, in memory only: it
 * survives the share sheet and a trip to another app, but not process death (ADR-0009, decision 4).
 */
class AddMountedCameraViewModel(
    private val pairing: PairingStore,
    private val link: PlayerLink,
    private val identity: suspend () -> LinkIdentity,
) : ViewModel() {
    private var token: String? = null
    private val code = MutableStateFlow<String?>(null)
    private val justPaired = MutableStateFlow(false)
    private var running: Job? = null

    val state: StateFlow<AddMountedCameraUiState> =
        combine(code, pairing.cameraPins, link.state, justPaired) { code, pins, link, justPaired ->
            AddMountedCameraUiState(code, pins.isNotEmpty(), link, justPaired)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AddMountedCameraUiState())

    /** Pairs or holds the link only while the screen is in front: nothing runs in the background. */
    fun start() {
        if (running?.isActive == true) return
        running =
            viewModelScope.launch {
                pairing.cameraPins
                    .map { it.firstOrNull() }
                    .distinctUntilChanged()
                    .collectLatest { pin -> if (pin == null) pairOnce() else link.run(pin) }
            }
    }

    fun stop() {
        running?.cancel()
        running = null
    }

    private suspend fun pairOnce() {
        val me = identity()
        val current = token ?: freshToken().also { token = it }
        code.value = PairingPayload(PairingPayload.VERSION, me.fingerprint, current).encode()
        val camera = link.pair(current)
        token = null
        code.value = null
        justPaired.value = true
        pairing.pinCamera(camera)
    }

    /** Also *Pair again*: the pin goes, and the QR comes back with a new token. */
    fun unpair() {
        justPaired.value = false
        viewModelScope.launch {
            pairing.unpairCameras()
            Log.i(LINK_TAG, "Unpaired the Mounted camera")
        }
    }

    suspend fun capture(): ReceivedPhoto = link.capture()

    companion object {
        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val container = (this[APPLICATION_KEY] as MainApplication).container
                    AddMountedCameraViewModel(container.pairing, container.playerLink, container::linkIdentity)
                }
            }
    }
}
