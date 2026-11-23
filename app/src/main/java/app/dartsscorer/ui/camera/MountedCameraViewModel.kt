package app.dartsscorer.ui.camera

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.camera.PairingStore
import kotlinx.coroutines.launch

/** Settings' *Mounted camera*, which asks for `CAMERA` too and records the ask the handheld ask reads. */
class MountedCameraViewModel(
    private val pairing: PairingStore,
) : ViewModel() {
    fun cameraPermissionAnswered() {
        viewModelScope.launch { pairing.markCameraAsked() }
    }

    companion object {
        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val app = this[APPLICATION_KEY] as MainApplication
                    MountedCameraViewModel(app.container.pairing)
                }
            }
    }
}
