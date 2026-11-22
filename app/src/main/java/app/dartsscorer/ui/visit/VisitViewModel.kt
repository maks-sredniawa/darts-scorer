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
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Ring
import app.dartsscorer.tip.TipJar
import app.dartsscorer.tip.tipAskDue
import kotlinx.coroutines.CancellationException
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
    val keypad: Keypad? = null,
    /** The Dart last removed, offered back with *Undo* until the next change or the snackbar's dismissal. */
    val removed: ShownDart? = null,
    /** Where focus goes next, once the sheet has closed; cleared by [VisitViewModel.focusPlaced]. */
    val focus: VisitFocus? = null,
)

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

    // phase-1.md §4, The start-up sweep. The handle is read here, on the main thread, because
    // cameraReturned may clear CAMERA before the sweep runs.
    private val swept: Job =
        sweep(keep = saved.get<String>(PHOTO), pending = saved.get<String>(CAMERA))

    private var arriving: Job? = null

    /** The Darts as the model read them on the Photo on screen, to tell which the player removed. */
    private var readDarts: List<ShownDart> = emptyList()

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
        val ended = marked(before)
        visit.update {
            it.copy(phase = VisitPhase.Reading, notice = null, keypad = null, removed = null, focus = null)
        }
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
                previous?.let { old ->
                    withContext(io) {
                        ended?.let { (shown, removed) -> photos.keep(shown, removed) }
                        photos.delete(old)
                    }
                }
                show(photo)
            }
    }

    /** Called on every stop of the screen, which each close or kill passes through, so the last Visit is kept too. */
    fun keepShown() {
        val (shown, removed) = marked(visit.value.phase) ?: return
        viewModelScope.launch(io) { photos.keep(shown, removed) }
    }

    fun openDart(number: Int) {
        visit.update { state ->
            val shown = state.phase as? VisitPhase.Shown ?: return@update state
            val dart = shown.darts.firstOrNull { it.number == number } ?: return@update state
            state.copy(keypad = Correction.open(dart, (shown as? VisitPhase.Scored)?.toBoard))
        }
    }

    /** *Add a Dart*, and on no Board found *Enter the Score yourself* (D6): the keypad with nothing picked. */
    fun addDart() {
        visit.update { state ->
            val phase = state.phase
            val open = phase is VisitPhase.NoBoard || (phase is VisitPhase.Shown && Correction.canAdd(phase.darts))
            if (open) state.copy(keypad = Keypad(dart = null)) else state
        }
    }

    /** A tap on an empty spot of the Photo, in its pixels: a new Dart with the bed under the finger. */
    fun addDartAt(photo: Point) {
        visit.update { state ->
            val scored = state.phase as? VisitPhase.Scored ?: return@update state
            if (Correction.canPlace(scored.darts)) {
                state.copy(keypad = Correction.openAt(photo, scored.toBoard))
            } else {
                state
            }
        }
    }

    fun pickRing(ring: Ring) = visit.update { state -> state.copy(keypad = state.keypad?.withRing(ring)) }

    fun pickNumber(number: Int) = visit.update { state -> state.copy(keypad = state.keypad?.withNumber(number)) }

    fun pickBullOrMiss(ring: Ring) = visit.update { state -> state.copy(keypad = state.keypad?.withBullOrMiss(ring)) }

    fun dismissKeypad() {
        visit.update { state ->
            val keypad = state.keypad ?: return@update state
            val focus =
                when {
                    keypad.dart != null -> VisitFocus.Chip(keypad.dart)
                    state.phase is VisitPhase.Shown -> Correction.focusAfterDismissing(state.phase.darts)
                    state.phase is VisitPhase.NoBoard -> VisitFocus.EnterScore
                    else -> VisitFocus.AddDart
                }
            state.copy(keypad = null, focus = focus)
        }
    }

    /** *Done*: the keypad's Score onto its Dart. The first Dart entered by hand counts the Visit, once. */
    fun commitKeypad() {
        val before = visit.value
        val keypad = before.keypad ?: return
        if (keypad.score == null) return
        val (shown, darts) =
            when (val phase = before.phase) {
                is VisitPhase.Scored -> phase to Correction.commit(phase.darts, keypad, phase.toBoard)
                is VisitPhase.Entered -> phase to Correction.commit(phase.darts, keypad, null)
                is VisitPhase.NoBoard ->
                    VisitPhase.Entered(phase.photo, phase.width, phase.height, emptyList()).let {
                        it to Correction.commit(it.darts, keypad, null)
                    }
                else -> return
            }
        val committed = keypad.dart ?: darts.firstOrNull { it !in shown.darts }?.number
        visit.value =
            before.copy(
                phase = shown.withDarts(darts),
                keypad = null,
                removed = null,
                focus = committed?.let { VisitFocus.Chip(it) },
            )
        if (shown is VisitPhase.Entered && darts.isNotEmpty()) {
            saved.get<String>(PHOTO)?.let { viewModelScope.launch { preferences.incrementVisitsScored(it) } }
        }
    }

    /** A Dart's ring dragged to [to], in Photo pixels, on every move so the chip and total follow it. */
    fun moveDart(
        number: Int,
        to: Point,
        nearRead: Boolean = false,
    ) {
        visit.update { state ->
            val scored = state.phase as? VisitPhase.Scored ?: return@update state
            state.copy(
                phase = scored.copy(darts = Correction.move(scored.darts, number, to, scored.toBoard, nearRead)),
                removed = null,
            )
        }
    }

    /** The sheet's *Back to the app's reading*: the Dart as it was read. */
    fun backToReading(number: Int) {
        visit.update { state ->
            val shown = state.phase as? VisitPhase.Shown ?: return@update state
            val fromSheet = state.keypad?.dart == number
            state.copy(
                phase = shown.withDarts(Correction.backToReading(shown.darts, number)),
                keypad = if (fromSheet) null else state.keypad,
                removed = null,
                focus = if (fromSheet) VisitFocus.Chip(number) else state.focus,
            )
        }
    }

    fun removeDart(number: Int) {
        visit.update { state ->
            val shown = state.phase as? VisitPhase.Shown ?: return@update state
            val dart = shown.darts.firstOrNull { it.number == number } ?: return@update state
            val darts = Correction.remove(shown.darts, number)
            state.copy(
                phase = shown.withDarts(darts),
                keypad = null,
                removed = dart,
                focus = Correction.focusAfterRemoving(darts, number),
            )
        }
    }

    fun undoRemove() {
        visit.update { state ->
            val shown = state.phase as? VisitPhase.Shown ?: return@update state
            val dart = state.removed ?: return@update state
            state.copy(
                phase = shown.withDarts(Correction.restore(shown.darts, dart)),
                removed = null,
                focus = VisitFocus.Chip(dart.number),
            )
        }
    }

    fun removalSettled() = visit.update { it.copy(removed = null) }

    fun focusPlaced() = visit.update { it.copy(focus = null) }

    private suspend fun show(photo: String) {
        val reading = readOrNull(photo)
        if (reading == null) {
            forget(photo)
            visit.update { it.copy(phase = VisitPhase.Empty, notice = VisitNotice.Unreadable) }
            return
        }
        val phase = phaseOf(photos.resolve(photo), reading)
        readDarts = (phase as? VisitPhase.Scored)?.darts.orEmpty()
        visit.update { it.copy(phase = phase) }
        if (phase is VisitPhase.Scored) preferences.incrementVisitsScored(photo)
    }

    private fun marked(phase: VisitPhase): Pair<VisitPhase.Shown, List<ShownDart>>? {
        val shown = (phase as? VisitPhase.Shown)?.takeIf { it is VisitPhase.Scored || it.darts.isNotEmpty() }
        return shown?.let { it to readDarts.filter { read -> it.darts.none { dart -> dart.read == read.read } } }
    }

    // A model that will not load or run, or a Photo too big for memory, is an unreadable Photo, not a crash.
    private suspend fun readOrNull(photo: String): PhotoReading? =
        try {
            photos.read(photo)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            null
        } catch (e: OutOfMemoryError) {
            null
        } catch (e: LinkageError) {
            null
        }

    private suspend fun forget(photo: String) {
        saved.remove<String>(PHOTO)
        withContext(io) { photos.delete(photo) }
    }

    private fun sweep(
        keep: String?,
        pending: String?,
    ): Job =
        viewModelScope.launch(io) {
            photos.storedPhotos().filter { it != keep }.forEach(photos::delete)
            photos.cameraTargets().filter { it != pending }.forEach(photos::discardCameraTarget)
        }

    companion object {
        internal const val PHOTO = "photo"
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
