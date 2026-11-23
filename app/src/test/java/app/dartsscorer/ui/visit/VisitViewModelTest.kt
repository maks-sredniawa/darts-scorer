package app.dartsscorer.ui.visit

import android.app.Activity
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.lifecycle.SavedStateHandle
import app.dartsscorer.camera.PairingStore
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.link.CameraLink
import app.dartsscorer.link.CaptureError
import app.dartsscorer.link.CaptureFailed
import app.dartsscorer.link.CaptureFailure
import app.dartsscorer.link.PlayerLinkState
import app.dartsscorer.link.ReceivedPhoto
import app.dartsscorer.scoring.Board
import app.dartsscorer.scoring.FoundDart
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Located
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Ring
import app.dartsscorer.scoring.Score
import app.dartsscorer.tip.TipBilling
import app.dartsscorer.tip.TipJar
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ProductDetails
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException
import java.time.Instant

/**
 * The ViewModel, DataStore and the tip jar all run on one unconfined dispatcher unless a test says
 * otherwise, so each call has done its work, preference writes and `state` included, by the time it
 * returns. On a DataStore thread of its own, `state` could still show the value from before the call.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class VisitViewModelTest {
    @get:Rule val folder = TemporaryFolder()

    private val dispatcher = UnconfinedTestDispatcher()
    private val scope = CoroutineScope(dispatcher + SupervisorJob())
    private val preferences by lazy {
        AppPreferences(PreferenceDataStoreFactory.create(scope = scope) { folder.newFile("app.preferences_pb") })
    }
    private val pairing by lazy {
        PairingStore(PreferenceDataStoreFactory.create(scope = scope) { folder.newFile("pairing.preferences_pb") })
    }
    private val tipJar by lazy { TipJar(scope) { NoBilling } }
    private val photos = FakePhotos()
    private val link = FakeLink()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() {
        scope.cancel()
        Dispatchers.resetMain()
    }

    private fun viewModel(saved: SavedStateHandle = SavedStateHandle()) =
        VisitViewModel(preferences, pairing, tipJar, Instant.EPOCH, photos, saved, link, dispatcher)

    /** The state once it shows [settled]: `state` is shared while watched, so its first value may be stale. */
    private fun VisitViewModel.stateWhen(settled: (VisitUiState) -> Boolean): VisitUiState =
        runBlocking { withTimeout(5_000) { state.first(settled) } }

    private fun VisitViewModel.scored(): VisitPhase.Scored =
        stateWhen {
            it.phase is VisitPhase.Scored
        }.phase as VisitPhase.Scored

    private fun visitsScored(): Int = runBlocking { preferences.visitsScored.first() }

    @Test
    fun `a Board found is counted once, even from a handle saved before it was counted`() {
        val saved = SavedStateHandle()
        photos.next = board()
        viewModel(saved).photoChosen("content://picked/1")
        viewModel(SavedStateHandle(mapOf(VisitViewModel.PHOTO to saved.get<String>(VisitViewModel.PHOTO)))).scored()
        // DataStore applies edits in order: had the second ViewModel counted, its edit would land first.
        runBlocking { preferences.incrementVisitsScored("photos/other.jpg") }
        assertEquals(2, visitsScored())
    }

    @Test
    fun `a camera Photo delivered before the sweep runs is kept`() {
        val io = StandardTestDispatcher()
        val saved = SavedStateHandle(mapOf(VisitViewModel.CAMERA to "content://camera/pending.jpg"))
        photos.camera += "content://camera/pending.jpg"
        photos.next = board()
        val visit = VisitViewModel(preferences, pairing, tipJar, Instant.EPOCH, photos, saved, link, io)
        visit.cameraReturned(taken = true)
        io.scheduler.advanceUntilIdle()
        visit.scored()
        assertEquals(listOf(saved.get<String>(VisitViewModel.PHOTO)), photos.stored)
        assertTrue(photos.camera.isEmpty())
    }

    @Test
    fun `a model that fails on a Photo says it is unreadable rather than crashing`() {
        listOf(IllegalStateException("interpreter"), OutOfMemoryError(), UnsatisfiedLinkError()).forEach { failure ->
            photos.readFailure = failure
            val visit = viewModel()
            visit.photoChosen("content://picked/1")
            val state = visit.stateWhen { it.notice != null }
            assertEquals(VisitNotice.Unreadable, state.notice)
            assertEquals(VisitPhase.Empty, state.phase)
        }
    }

    @Test
    fun `the first Take a Photo without the camera explains before the system asks`() {
        val visit = viewModel()
        visit.cameraNotAllowed(systemWouldExplain = false)
        assertTrue(visit.stateWhen { it.cameraRationale }.cameraRationale)
        visit.cameraRationaleClosed()
        assertEquals(null, visit.stateWhen { !it.cameraRationale }.notice)
    }

    @Test
    fun `a denial shows the banner, and a grant in the settings clears it`() {
        val visit = viewModel()
        visit.cameraPermissionAnswered(granted = false)
        assertEquals(VisitNotice.CameraDenied, visit.stateWhen { it.notice != null }.notice)
        visit.cameraAllowed()
        assertNull(visit.stateWhen { it.notice == null }.notice)
    }

    @Test
    fun `once asked and refused for good, the banner shows without the dialog`() {
        val visit = viewModel()
        visit.cameraPermissionAnswered(granted = false)
        visit.cameraAllowed()
        visit.cameraNotAllowed(systemWouldExplain = false)
        val state = visit.stateWhen { it.notice != null }
        assertEquals(VisitNotice.CameraDenied, state.notice)
        assertFalse(state.cameraRationale)
    }

    @Test
    fun `a denial the system will ask about again explains again`() {
        val visit = viewModel()
        visit.cameraPermissionAnswered(granted = false)
        visit.cameraNotAllowed(systemWouldExplain = true)
        assertTrue(visit.stateWhen { it.cameraRationale }.cameraRationale)
    }

    @Test
    fun `no Board found is shown with the whole Photo and not counted`() {
        photos.next = PhotoReading(800, 600, Located(null))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val phase = visit.stateWhen { it.phase is VisitPhase.NoBoard }.phase as VisitPhase.NoBoard
        assertEquals(800, phase.width)
        assertEquals(0, visitsScored())
    }

    @Test
    fun `the sweep removes leftover Photos and camera files but not the ones the handle holds`() {
        photos.stored += listOf("photos/kept.jpg", "photos/old.jpg")
        photos.camera += listOf("content://camera/pending.jpg", "content://camera/old.jpg")
        photos.next = board()
        viewModel(
            SavedStateHandle(
                mapOf(
                    VisitViewModel.PHOTO to "photos/kept.jpg",
                    VisitViewModel.CAMERA to "content://camera/pending.jpg",
                ),
            ),
        )
        assertEquals(listOf("photos/kept.jpg"), photos.stored)
        assertEquals(listOf("content://camera/pending.jpg"), photos.camera)
    }

    @Test
    fun `a new Photo replaces the previous one, and the camera's file is dropped`() {
        val saved = SavedStateHandle()
        photos.next = board()
        val visit = viewModel(saved)
        visit.photoChosen("content://picked/1")
        val first = saved.get<String>(VisitViewModel.PHOTO)
        val target = visit.cameraTarget()
        photos.camera += target
        visit.cameraReturned(taken = true)
        assertTrue(first !in photos.stored)
        assertEquals(listOf(saved.get<String>(VisitViewModel.PHOTO)), photos.stored)
        assertTrue(photos.camera.isEmpty())
        assertNull(saved.get<String>(VisitViewModel.CAMERA))
    }

    @Test
    fun `a cancelled camera leaves the result on screen`() {
        photos.next = board()
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val before = visit.scored()
        photos.camera += visit.cameraTarget()
        visit.cameraReturned(taken = false)
        assertEquals(before, visit.scored())
        assertTrue(photos.camera.isEmpty())
        assertEquals(1, photos.stored.size)
    }

    @Test
    fun `no camera app says so and keeps the result`() {
        photos.next = board()
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.cameraTarget()
        visit.cameraUnavailable()
        val state = visit.stateWhen { it.notice != null }
        assertEquals(VisitNotice.NoCamera, state.notice)
        assertTrue(state.phase is VisitPhase.Scored)
    }

    @Test
    fun `a Photo that cannot be stored keeps the previous result and says so`() {
        photos.next = board()
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val before = visit.scored()
        photos.failPersist = true
        visit.photoChosen("content://picked/2")
        val state = visit.stateWhen { it.notice != null }
        assertEquals(before, state.phase)
        assertEquals(VisitNotice.Unreadable, state.notice)
    }

    @Test
    fun `a Photo gone after process death leaves the empty state, not a crash`() {
        val saved = SavedStateHandle(mapOf(VisitViewModel.PHOTO to "photos/gone.jpg"))
        photos.next = null
        val visit = viewModel(saved)
        assertEquals(VisitNotice.Unreadable, visit.stateWhen { it.phase == VisitPhase.Empty }.notice)
        assertNull(saved.get<String>(VisitViewModel.PHOTO))
    }

    @Test
    fun `Darts are numbered from the top of the Photo and the crop stays inside it`() {
        val reading =
            PhotoReading(
                800,
                800,
                Located(
                    BOARD,
                    darts =
                        listOf(
                            FoundDart(400.0, 500.0, 0.9, Score.MISS),
                            FoundDart(400.0, 100.0, 0.3, Score.BULL),
                            FoundDart(300.0, 300.0, 0.9, Score.OUTER_BULL),
                        ),
                ),
            )
        val phase = phaseOf(File("photos/a.jpg"), reading) as VisitPhase.Scored
        assertEquals(listOf(100.0, 300.0, 500.0), phase.darts.map { it.at?.y })
        assertEquals(listOf(1, 2, 3), phase.darts.map { it.number })
        assertEquals(listOf(true, false, false), phase.darts.map { it.unsure })
        assertEquals(75, phase.darts.total)
        assertEquals(Crop(0.0, 0.0, 800.0, 800.0), phase.crop)
    }

    @Test
    fun `a Dart's ring and number are changed on the keypad and committed with Done`() {
        photos.next = board(FoundDart(400.0, 194.0, 0.9, Score(Ring.TREBLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.openDart(1)
        assertEquals(Keypad(1, Ring.TREBLE, 20, near = Point(0.0, 103.0)), visit.stateWhen { it.keypad != null }.keypad)
        visit.pickRing(Ring.DOUBLE)
        visit.pickNumber(5)
        visit.commitKeypad()
        val state = visit.stateWhen { it.keypad == null }
        val dart = (state.phase as VisitPhase.Scored).darts.single { it.number == 1 }
        assertEquals(Score(Ring.DOUBLE, 5), dart.score)
        assertTrue(dart.corrected)
        assertEquals(10, state.phase.darts.total)
        assertEquals(VisitFocus.Chip(1), state.focus)
    }

    @Test
    fun `Done on an unsure Dart confirms it where it was measured`() {
        photos.next = board(FoundDart(400.0, 194.0, 0.3, Score(Ring.TREBLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.openDart(1)
        visit.commitKeypad()
        val dart = visit.scored().darts.single { it.number == 1 }
        val read = DartRead(Point(400.0, 194.0), Score(Ring.TREBLE, 20), unsure = true)
        assertEquals(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20), read = read), dart)
    }

    @Test
    fun `a dragged ring changes the Score as it moves, and the sheet puts it back`() {
        photos.next = board(FoundDart(400.0, 194.0, 0.9, Score(Ring.TREBLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val before = visit.scored()
        visit.moveDart(1, Point(400.0 + 2 * 60.0, 400.0))
        assertEquals(6, visit.scored().darts.total)
        visit.moveDart(1, Point(400.0, 400.0))
        assertEquals(50, visit.scored().darts.total)
        visit.openDart(1)
        assertTrue(visit.stateWhen { it.keypad != null }.keypad!!.restorable)
        visit.backToReading(1)
        val back = visit.stateWhen { it.keypad == null }
        assertEquals(before, back.phase)
        assertEquals(VisitFocus.Chip(1), back.focus)
    }

    @Test
    fun `a removed Dart comes back with Undo, and focus moves to the next chip`() {
        photos.next =
            board(
                FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)),
                FoundDart(400.0, 500.0, 0.9, Score(Ring.SINGLE, 3)),
            )
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val before = visit.scored()
        visit.openDart(1)
        visit.removeDart(1)
        val removed = visit.stateWhen { it.removed != null }
        assertEquals(listOf(1, 2), (removed.phase as VisitPhase.Scored).darts.map { it.number })
        assertEquals(VisitFocus.Chip(1), removed.focus)
        assertNull(removed.keypad)
        visit.undoRemove()
        val back = visit.stateWhen { it.removed == null }
        assertEquals(before, back.phase)
        assertEquals(VisitFocus.Chip(1), back.focus)
    }

    @Test
    fun `the last Dart removed, Misses too, sends focus to Add a Dart, and a dismissed snackbar forgets it`() {
        photos.next = board(FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.removeDart(1)
        assertEquals(VisitFocus.Chip(1), visit.stateWhen { it.removed != null }.focus)
        visit.removalSettled()
        visit.removeDart(2)
        visit.removalSettled()
        visit.removeDart(1)
        assertEquals(VisitFocus.AddDart, visit.stateWhen { it.removed != null }.focus)
        visit.removalSettled()
        visit.undoRemove()
        assertTrue(visit.scored().darts.isEmpty())
    }

    @Test
    fun `a tap on the Photo proposes the bed under it, and Done adds the Dart at the bed's centre`() {
        photos.next = board()
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.addDartAt(Point(400.0, 400.0 + 2 * 164.0))
        assertEquals(Score(Ring.DOUBLE, 3), visit.stateWhen { it.keypad != null }.keypad?.score)
        visit.commitKeypad()
        val state = visit.stateWhen { it.keypad == null }
        val darts = (state.phase as VisitPhase.Scored).darts
        assertEquals(listOf(1, 2, 3), darts.map { it.number })
        val dart = darts.single { !it.filled }
        assertEquals(Score(Ring.DOUBLE, 3), dart.score)
        assertEquals(Score(Ring.DOUBLE, 3), Board.score(BOARD.project(dart.at!!)))
        assertTrue(dart.corrected)
        assertEquals(VisitFocus.Chip(dart.number), state.focus)
        assertEquals(3, dart.number)
    }

    @Test
    fun `a tap's keypad closed without Done with three shown returns focus to the Miss it would have taken`() {
        photos.next = board()
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.addDartAt(Point(400.0, 400.0))
        visit.stateWhen { it.keypad != null }
        visit.dismissKeypad()
        val state = visit.stateWhen { it.keypad == null }
        assertEquals(VisitFocus.Chip(3), state.focus)
        assertTrue((state.phase as VisitPhase.Scored).darts.all { it.filled })
    }

    @Test
    fun `no fourth Dart can be added`() {
        photos.next =
            board(
                FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)),
                FoundDart(400.0, 300.0, 0.9, Score(Ring.SINGLE, 20)),
                FoundDart(400.0, 500.0, 0.9, Score(Ring.SINGLE, 3)),
            )
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.addDart()
        visit.addDartAt(Point(400.0, 400.0))
        assertNull(visit.stateWhen { it.phase is VisitPhase.Scored }.keypad)
    }

    @Test
    fun `a Visit entered by hand on no Board found is counted once, at its first Dart`() {
        photos.next = PhotoReading(800, 600, Located(null))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.stateWhen { it.phase is VisitPhase.NoBoard }
        visit.addDart()
        visit.pickRing(Ring.TREBLE)
        visit.pickNumber(20)
        visit.commitKeypad()
        visit.addDart()
        visit.pickBullOrMiss(Ring.BULL)
        visit.commitKeypad()
        val entered =
            visit
                .stateWhen {
                    it.phase is VisitPhase.Entered && it.keypad == null
                }.phase as VisitPhase.Entered
        assertEquals(listOf(1, 2), entered.darts.map { it.number })
        assertEquals(110, entered.darts.total)
        assertTrue(entered.darts.all { it.at == null })
        runBlocking { preferences.incrementVisitsScored("photos/other.jpg") }
        assertEquals(2, visitsScored())
    }

    @Test
    fun `a keypad closed without Done changes nothing and enters nothing`() {
        photos.next = PhotoReading(800, 600, Located(null))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.stateWhen { it.phase is VisitPhase.NoBoard }
        visit.addDart()
        visit.pickNumber(20)
        // Without seeing the keypad open first, `keypad == null` could match the state from before it.
        visit.stateWhen { it.keypad?.score != null }
        visit.dismissKeypad()
        val state = visit.stateWhen { it.keypad == null }
        assertTrue(state.phase is VisitPhase.NoBoard)
        assertEquals(VisitFocus.EnterScore, state.focus)
        assertEquals(0, visitsScored())
    }

    @Test
    fun `a new Photo closes the keypad and drops the corrections`() {
        photos.next = board(FoundDart(400.0, 194.0, 0.9, Score(Ring.TREBLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
        visit.removeDart(1)
        visit.addDart()
        visit.photoChosen("content://picked/2")
        val state = visit.stateWhen { it.phase is VisitPhase.Scored && it.removed == null }
        assertNull(state.keypad)
        assertEquals(listOf(false, true, true), (state.phase as VisitPhase.Scored).darts.map { it.filled })
    }

    @Test
    fun `a new Photo keeps the ended Visit with the Darts removed from its reading, before deleting its Photo`() {
        photos.next =
            board(
                FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)),
                FoundDart(400.0, 500.0, 0.9, Score(Ring.SINGLE, 3)),
            )
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val read = visit.scored()
        visit.removeDart(1)
        visit.moveDart(2, Point(400.0, 400.0))
        val ended = visit.scored()
        visit.photoChosen("content://picked/2")
        visit.stateWhen { it.phase is VisitPhase.Scored && it.phase != ended }
        val (kept, removed) = photos.kept.single()
        assertEquals(ended, kept)
        assertEquals(listOf(read.darts.first()), removed)
        assertEquals(listOf("keep photos/0.jpg", "delete photos/0.jpg"), photos.log)
    }

    @Test
    fun `a Visit with no result is not kept, on a stop or on a new Photo`() {
        photos.next = PhotoReading(800, 600, Located(null))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.stateWhen { it.phase is VisitPhase.NoBoard }
        visit.keepShown()
        visit.addDart()
        visit.pickRing(Ring.TREBLE)
        visit.pickNumber(20)
        visit.commitKeypad()
        visit.removeDart(1)
        visit.stateWhen { (it.phase as? VisitPhase.Entered)?.darts?.isEmpty() == true }
        visit.keepShown()
        visit.photoChosen("content://picked/2")
        visit.stateWhen { it.phase is VisitPhase.NoBoard && photos.stored.size == 1 }
        assertTrue(photos.kept.isEmpty())
    }

    @Test
    fun `a stop keeps the Visit on screen as it stands, and a new Photo keeps it again`() {
        photos.next =
            board(
                FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)),
                FoundDart(400.0, 500.0, 0.9, Score(Ring.SINGLE, 3)),
            )
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        val read = visit.scored()
        visit.removeDart(2)
        val shown = visit.scored()
        visit.keepShown()
        assertEquals(listOf(shown to listOf(read.darts[1])), photos.kept)
        assertEquals(listOf("photos/0.jpg"), photos.stored)
        visit.photoChosen("content://picked/2")
        visit.stateWhen { it.phase is VisitPhase.Scored && photos.stored == listOf("photos/1.jpg") }
        assertEquals(listOf(shown, shown), photos.kept.map { it.first })
    }

    @Test
    fun `a stop with no Visit on screen keeps nothing`() {
        viewModel().keepShown()
        assertTrue(photos.kept.isEmpty())
    }

    @Test
    fun `with no camera paired the Visit screen shows none`() {
        assertNull(viewModel().stateWhen { true }.camera)
    }

    @Test
    fun `a Photo from the mounted camera takes the handheld path and is counted once`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        photos.next = board()
        val visit = viewModel()
        visit.takeWithMountedCamera()
        visit.scored()
        assertEquals(1, photos.received)
        assertTrue(photos.camera.isEmpty())
        assertEquals(1, visitsScored())
        val camera = visit.stateWhen { it.camera?.capturing == false }.camera!!
        assertNull(camera.failure)
        assertTrue(photos.keptNoBoard.isEmpty())
    }

    @Test
    fun `a second tap while a capture is in flight is ignored`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        link.hold = CompletableDeferred()
        val visit = viewModel()
        visit.takeWithMountedCamera()
        visit.takeWithMountedCamera()
        assertEquals(1, link.captures)
        assertTrue(visit.stateWhen { it.camera?.capturing == true }.camera!!.capturing)
        link.hold!!.complete(Unit)
    }

    @Test
    fun `a capture that fails says why and leaves the Visit as it was`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        link.failure = CaptureFailed(CaptureFailure.TIMED_OUT)
        val visit = viewModel()
        visit.takeWithMountedCamera()
        val state = visit.stateWhen { it.camera?.failure != null }
        assertEquals(CameraFailure.NoReply, state.camera!!.failure)
        assertEquals(VisitPhase.Empty, state.phase)
        link.failure = CaptureFailed(CaptureFailure.CAMERA_ERROR, CaptureError.BUSY)
        visit.takeWithMountedCamera()
        assertEquals(CameraFailure.Busy, visit.stateWhen { it.camera?.failure == CameraFailure.Busy }.camera!!.failure)
    }

    @Test
    fun `a camera not found fails the tap without asking it`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.NOT_FOUND
        val visit = viewModel()
        visit.takeWithMountedCamera()
        assertEquals(CameraFailure.NotFound, visit.stateWhen { it.camera?.failure != null }.camera!!.failure)
        assertEquals(0, link.captures)
    }

    @Test
    fun `a linked Photo with no Board is kept for the gate, and a handheld one is not`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        photos.next = PhotoReading(800, 600, Located(null))
        val visit = viewModel()
        visit.takeWithMountedCamera()
        visit.stateWhen { it.phase is VisitPhase.NoBoard }
        assertEquals(1, photos.keptNoBoard.size)
        visit.photoChosen("content://picked/1")
        visit.stateWhen { it.phase is VisitPhase.NoBoard }
        assertEquals(1, photos.keptNoBoard.size)
    }

    @Test
    fun `a linked Photo with no Board restored after process death is not kept again`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        photos.next = PhotoReading(800, 600, Located(null))
        val saved = SavedStateHandle()
        viewModel(saved).apply {
            takeWithMountedCamera()
            stateWhen { it.phase is VisitPhase.NoBoard }
        }
        viewModel(SavedStateHandle(saved.keys().associateWith { saved.get<Any>(it) }))
            .stateWhen { it.phase is VisitPhase.NoBoard }
        assertEquals(1, photos.keptNoBoard.size)
    }

    @Test
    fun `a tap on a link still looking waits for it and takes the Photo once it connects`() {
        runBlocking { pairing.pinCamera(PIN) }
        photos.next = board()
        val visit = viewModel()
        visit.takeWithMountedCamera()
        dispatcher.scheduler.advanceTimeBy(VisitViewModel.CONNECT_WAIT_MILLIS - 1)
        assertEquals(0, link.captures)
        link.state.value = PlayerLinkState.CONNECTED
        visit.scored()
        assertEquals(1, link.captures)
        assertNull(visit.stateWhen { it.camera?.capturing == false }.camera!!.failure)
    }

    @Test
    fun `a link still looking after the wait fails the tap as not found without asking the camera`() {
        runBlocking { pairing.pinCamera(PIN) }
        val visit = viewModel()
        visit.takeWithMountedCamera()
        dispatcher.scheduler.advanceTimeBy(VisitViewModel.CONNECT_WAIT_MILLIS + 1)
        assertEquals(CameraFailure.NotFound, visit.stateWhen { it.camera?.failure != null }.camera!!.failure)
        assertEquals(0, link.captures)
    }

    @Test
    fun `a link that wants pairing again or is outdated fails the tap with that reason`() {
        runBlocking { pairing.pinCamera(PIN) }
        val visit = viewModel()
        mapOf(
            PlayerLinkState.PAIR_AGAIN to CameraFailure.PairAgain,
            PlayerLinkState.OUTDATED to CameraFailure.Outdated,
        ).forEach { (state, failure) ->
            link.state.value = state
            visit.takeWithMountedCamera()
            assertEquals(failure, visit.stateWhen { it.camera?.failure == failure }.camera!!.failure)
        }
        assertEquals(0, link.captures)
    }

    @Test
    fun `a failure read from the link is dropped once the link moves on`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.PAIR_AGAIN
        val visit = viewModel()
        visit.takeWithMountedCamera()
        visit.stateWhen { it.camera?.failure == CameraFailure.PairAgain }
        link.state.value = PlayerLinkState.NOT_FOUND
        assertNull(visit.stateWhen { it.camera?.link == PlayerLinkState.NOT_FOUND }.camera!!.failure)
        link.state.value = PlayerLinkState.LOOKING
        visit.takeWithMountedCamera()
        dispatcher.scheduler.advanceTimeBy(VisitViewModel.CONNECT_WAIT_MILLIS + 1)
        visit.stateWhen { it.camera?.failure == CameraFailure.NotFound }
        link.state.value = PlayerLinkState.CONNECTED
        assertNull(visit.stateWhen { it.camera?.link == PlayerLinkState.CONNECTED }.camera!!.failure)
    }

    @Test
    fun `a failure the camera gave stays when the link moves on`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        link.failure = CaptureFailed(CaptureFailure.TIMED_OUT)
        val visit = viewModel()
        visit.takeWithMountedCamera()
        visit.stateWhen { it.camera?.failure == CameraFailure.NoReply }
        link.state.value = PlayerLinkState.LOOKING
        assertEquals(
            CameraFailure.NoReply,
            visit.stateWhen { it.camera?.link == PlayerLinkState.LOOKING }.camera!!.failure,
        )
    }

    @Test
    fun `the link runs to the paired camera from start to stop, once`() {
        val visit = viewModel()
        visit.startLink()
        assertTrue(link.runs.isEmpty())
        runBlocking { pairing.pinCamera(PIN) }
        visit.startLink()
        assertEquals(listOf(PIN), link.runs)
        assertEquals(1, link.running)
        visit.stopLink()
        assertEquals(0, link.running)
    }

    @Test
    fun `a Photo from the mounted camera asks for focus on the reading, and a handheld one does not`() {
        runBlocking { pairing.pinCamera(PIN) }
        link.state.value = PlayerLinkState.CONNECTED
        photos.next = board()
        val io = StandardTestDispatcher()
        val visit = VisitViewModel(preferences, pairing, tipJar, Instant.EPOCH, photos, SavedStateHandle(), link, io)
        io.scheduler.advanceUntilIdle()
        visit.takeWithMountedCamera()
        assertEquals(VisitFocus.Reading, visit.stateWhen { it.phase == VisitPhase.Reading }.focus)
        io.scheduler.advanceUntilIdle()
        assertNull(visit.stateWhen { it.phase is VisitPhase.Scored }.focus)
        visit.photoChosen("content://picked/1")
        assertNull(visit.stateWhen { it.phase == VisitPhase.Reading }.focus)
        io.scheduler.advanceUntilIdle()
    }

    private fun board(vararg darts: FoundDart) = PhotoReading(800, 800, Located(BOARD, darts = darts.toList()))

    private class FakePhotos : VisitPhotos {
        val stored = mutableListOf<String>()
        val camera = mutableListOf<String>()
        var next: PhotoReading? = null
        var failPersist = false
        var readFailure: Throwable? = null
        val kept = mutableListOf<Pair<VisitPhase.Shown, List<ShownDart>>>()
        val keptNoBoard = mutableListOf<VisitPhase.NoBoard>()
        var received = 0
        val log = mutableListOf<String>()
        private var made = 0

        override fun newCameraTarget() = "content://camera/${made++}.jpg"

        override suspend fun receive(jpeg: ByteArray): String {
            received++
            return newCameraTarget().also { camera += it }
        }

        override fun keepNoBoard(visit: VisitPhase.NoBoard) {
            keptNoBoard += visit
        }

        override fun cameraTargets() = camera.toList()

        override fun discardCameraTarget(target: String) {
            camera -= target
        }

        override suspend fun persist(source: String): String {
            if (failPersist) throw IOException("not an image")
            if (source.startsWith("content://camera/") && source !in camera) throw IOException("swept")
            return "photos/${made++}.jpg".also { stored += it }
        }

        override fun storedPhotos() = stored.toList()

        override fun delete(photo: String) {
            log += "delete $photo"
            stored -= photo
        }

        override fun resolve(photo: String) = File(photo)

        override suspend fun read(photo: String): PhotoReading? {
            readFailure?.let { throw it }
            return next
        }

        override fun keep(
            visit: VisitPhase.Shown,
            removed: List<ShownDart>,
        ) {
            log += "keep ${visit.photo.path}"
            kept += visit to removed
        }
    }

    private class FakeLink : CameraLink {
        override val state = MutableStateFlow(PlayerLinkState.LOOKING)
        var captures = 0
        var failure: CaptureFailed? = null
        var hold: CompletableDeferred<Unit>? = null
        val runs = mutableListOf<String>()
        var running = 0

        override suspend fun run(pin: String) {
            runs += pin
            running++
            try {
                awaitCancellation()
            } finally {
                running--
            }
        }

        override suspend fun capture(): ReceivedPhoto {
            captures++
            hold?.await()
            failure?.let { throw it }
            return ReceivedPhoto(byteArrayOf(0xFF.toByte(), 0xD8.toByte()), 800, 800, 0)
        }
    }

    private object NoBilling : TipBilling {
        override suspend fun connect() = false

        override suspend fun productDetails(): List<ProductDetails>? = null

        override suspend fun owned() = null

        override suspend fun consume(token: String): BillingResult = error("never connected")

        override fun launch(
            activity: Activity,
            details: ProductDetails,
        ) = Unit
    }

    private companion object {
        val PIN = "AB".repeat(32)

        /** Photo pixels to Board millimetres: the bull at (400, 400), 2 px a millimetre, y flipped. */
        val BOARD = Homography(doubleArrayOf(0.5, 0.0, -200.0, 0.0, -0.5, 200.0, 0.0, 0.0, 1.0))
    }
}
