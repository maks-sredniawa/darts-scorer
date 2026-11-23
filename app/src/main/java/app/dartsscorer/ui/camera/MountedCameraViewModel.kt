package app.dartsscorer.ui.camera

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.camera.PairingStore
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

data class MountedCameraUiState(
    val cameraPaired: Boolean = false,
)

/** Settings' *Mounted camera*: whether this phone has a camera paired (ADR-0009, decision 9). */
class MountedCameraViewModel(
    pairing: PairingStore,
) : ViewModel() {
    val state: StateFlow<MountedCameraUiState> =
        pairing.cameraPins
            .map { MountedCameraUiState(cameraPaired = it.isNotEmpty()) }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), MountedCameraUiState())

    companion object {
        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    MountedCameraViewModel((this[APPLICATION_KEY] as MainApplication).container.pairing)
                }
            }
    }
}
