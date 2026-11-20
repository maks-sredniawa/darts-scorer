package app.dartsscorer.ui.visit

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.tip.TipJar
import app.dartsscorer.tip.tipAskDue
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException
import java.time.Instant

/** Something that went wrong outside the Visit's own result, said in a banner until the next Photo. */
enum class VisitNotice { NoCamera, Unreadable }

data class VisitUiState(
    val phase: VisitPhase = VisitPhase.Empty,
    val notice: VisitNotice? = null,
    /** False wherever Play will not sell a tip: nothing is asked for that cannot be bought. */
    val showTipAsk: Boolean = false,
)

/**
 * A Visit's life (phase-1.md §4). The Photo on screen and whether it was counted live in
 * [SavedStateHandle], so after process death the result is read again from the file, not counted
 * again, and the start-up sweep leaves that file alone.
 */
class VisitViewModel(
    private val preferences: AppPreferences,
    tipJar: TipJar,
    installedAt: Instant,
    private val photos: VisitPhotos,
    private val saved: SavedStateHandle,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) : ViewModel() {
    private val visit =
        MutableStateFlow(VisitUiState(phase = if (saved.contains(PHOTO)) VisitPhase.Reading else VisitPhase.Empty))

    val state: StateFlow<VisitUiState> =
        combine(visit, preferences.tipAsked, preferences.visitsScored, tipJar.offers) { visit, asked, visits, offers ->
            visit.copy(
                showTipAsk =
                    visit.phase == VisitPhase.Empty &&
                        offers.isNotEmpty() &&
                        tipAskDue(asked, visits, installedAt, Instant.now()),
            )
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), visit.value)

    // Here rather than in Application.onCreate: only this handle knows which Photo survived process
    // death. A Photo arriving waits for it, so a fresh file is never taken for a leftover.
    private val swept: Job = viewModelScope.launch(io) { sweep() }

    private var arriving: Job? = null

    init {
        // Prices are queried only once the ask could be due, saving a product query on every other
        // start. The binding itself happens on every foreground anyway, to settle tips.
        viewModelScope.launch {
            val due =
                tipAskDue(preferences.tipAsked.first(), preferences.visitsScored.first(), installedAt, Instant.now())
            if (due) tipJar.refresh()
        }
        saved.get<String>(PHOTO)?.let { photo -> arriving = viewModelScope.launch { show(photo) } }
    }

    fun answerTipAsk() {
        viewModelScope.launch { preferences.markTipAsked() }
    }

    /** The Uri to hand the camera app, remembered across process death until it comes back. */
    fun cameraTarget(): String = photos.newCameraTarget().also { saved[CAMERA] = it }

    fun cameraUnavailable() {
        saved.remove<String>(CAMERA)
        visit.update { it.copy(notice = VisitNotice.NoCamera) }
    }

    /** A cancelled camera changes nothing: the result on screen stays. */
    fun cameraReturned(taken: Boolean) {
        val target = saved.remove<String>(CAMERA) ?: return
        if (taken) {
            arrive(target, cameraTarget = target)
        } else {
            viewModelScope.launch(io) { photos.discardCameraTarget(target) }
        }
    }

    fun photoChosen(source: String?) {
        if (source != null) arrive(source, cameraTarget = null)
    }

    private fun arrive(
        source: String,
        cameraTarget: String?,
    ) {
        arriving?.cancel()
        val before = visit.value.phase.takeUnless { it == VisitPhase.Reading } ?: VisitPhase.Empty
        visit.update { it.copy(phase = VisitPhase.Reading, notice = null) }
        arriving =
            viewModelScope.launch {
                swept.join()
                val photo =
                    try {
                        photos.persist(source)
                    } catch (e: IOException) {
                        null
                    } catch (e: SecurityException) {
                        null
                    }
                withContext(io) { cameraTarget?.let(photos::discardCameraTarget) }
                if (photo == null) {
                    visit.update { it.copy(phase = before, notice = VisitNotice.Unreadable) }
                    return@launch
                }
                val previous = saved.get<String>(PHOTO)
                saved[PHOTO] = photo
                saved[COUNTED] = false
                previous?.let { withContext(io) { photos.delete(it) } }
                show(photo)
            }
    }

    private suspend fun show(photo: String) {
        val reading = photos.read(photo)
        if (reading == null) {
            forget(photo)
            visit.update { it.copy(phase = VisitPhase.Empty, notice = VisitNotice.Unreadable) }
            return
        }
        val phase = phaseOf(photos.resolve(photo), reading)
        visit.update { it.copy(phase = phase) }
        // The first time a Photo's result is shown, so the last Visit of a session counts too. Saved
        // before the write: a death between the two loses one Visit rather than counting one twice.
        if (phase is VisitPhase.Scored && saved.get<Boolean>(COUNTED) != true) {
            saved[COUNTED] = true
            preferences.incrementVisitsScored()
        }
    }

    private suspend fun forget(photo: String) {
        saved.remove<String>(PHOTO)
        saved.remove<Boolean>(COUNTED)
        withContext(io) { photos.delete(photo) }
    }

    private fun sweep() {
        val keep = saved.get<String>(PHOTO)
        photos.storedPhotos().filter { it != keep }.forEach(photos::delete)
        val pending = saved.get<String>(CAMERA)
        photos.cameraTargets().filter { it != pending }.forEach(photos::discardCameraTarget)
    }

    companion object {
        internal const val PHOTO = "photo"
        internal const val COUNTED = "counted"
        internal const val CAMERA = "camera"

        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val app = this[APPLICATION_KEY] as MainApplication
                    VisitViewModel(
                        app.container.preferences,
                        app.container.tipJar,
                        app.container.installedAt,
                        app.container.visitPhotos,
                        createSavedStateHandle(),
                    )
                }
            }
    }
}
