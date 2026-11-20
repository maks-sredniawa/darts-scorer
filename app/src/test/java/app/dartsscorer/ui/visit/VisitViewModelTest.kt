package app.dartsscorer.ui.visit

import android.app.Activity
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.lifecycle.SavedStateHandle
import app.dartsscorer.data.AppPreferences
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
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
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
 * The ViewModel runs on an unconfined dispatcher unless a test says otherwise, so each call has done
 * its work, up to handing a preference write to DataStore, by the time it returns.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class VisitViewModelTest {
    @get:Rule val folder = TemporaryFolder()

    private val dispatcher = UnconfinedTestDispatcher()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val preferences by lazy {
        AppPreferences(PreferenceDataStoreFactory.create(scope = scope) { folder.newFile("app.preferences_pb") })
    }
    private val tipJar by lazy { TipJar(scope) { NoBilling } }
    private val photos = FakePhotos()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() {
        scope.cancel()
        Dispatchers.resetMain()
    }

    private fun viewModel(saved: SavedStateHandle = SavedStateHandle()) =
        VisitViewModel(preferences, tipJar, Instant.EPOCH, photos, saved, dispatcher)

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
        val visit = VisitViewModel(preferences, tipJar, Instant.EPOCH, photos, saved, io)
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
        val dart = (state.phase as VisitPhase.Scored).darts.single()
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
        val dart = visit.scored().darts.single()
        assertEquals(ShownDart(1, Point(400.0, 194.0), Score(Ring.TREBLE, 20)), dart)
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
        assertEquals(listOf(2), (removed.phase as VisitPhase.Scored).darts.map { it.number })
        assertEquals(VisitFocus.Chip(2), removed.focus)
        assertNull(removed.keypad)
        visit.undoRemove()
        val back = visit.stateWhen { it.removed == null }
        assertEquals(before, back.phase)
        assertEquals(VisitFocus.Chip(1), back.focus)
    }

    @Test
    fun `the last Dart removed sends focus to Add a Dart, and a dismissed snackbar forgets it`() {
        photos.next = board(FoundDart(400.0, 100.0, 0.9, Score(Ring.SINGLE, 20)))
        val visit = viewModel()
        visit.photoChosen("content://picked/1")
        visit.scored()
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
        val dart = visit.scored().darts.single()
        assertEquals(Score(Ring.DOUBLE, 3), dart.score)
        assertEquals(Score(Ring.DOUBLE, 3), Board.score(BOARD.project(dart.at!!)))
        assertTrue(dart.corrected)
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
        assertEquals(1, (state.phase as VisitPhase.Scored).darts.size)
    }

    private fun board(vararg darts: FoundDart) = PhotoReading(800, 800, Located(BOARD, darts = darts.toList()))

    private class FakePhotos : VisitPhotos {
        val stored = mutableListOf<String>()
        val camera = mutableListOf<String>()
        var next: PhotoReading? = null
        var failPersist = false
        var readFailure: Throwable? = null
        private var made = 0

        override fun newCameraTarget() = "content://camera/${made++}.jpg"

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
            stored -= photo
        }

        override fun resolve(photo: String) = File(photo)

        override suspend fun read(photo: String): PhotoReading? {
            readFailure?.let { throw it }
            return next
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
        /** Photo pixels to Board millimetres: the bull at (400, 400), 2 px a millimetre, y flipped. */
        val BOARD = Homography(doubleArrayOf(0.5, 0.0, -200.0, 0.0, -0.5, 200.0, 0.0, 0.0, 1.0))
    }
}
