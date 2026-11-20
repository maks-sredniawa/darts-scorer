package app.dartsscorer.ui.visit

import android.app.Activity
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.lifecycle.SavedStateHandle
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.scoring.FoundDart
import app.dartsscorer.scoring.Homography
import app.dartsscorer.scoring.Located
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
        assertEquals(listOf(100.0, 300.0, 500.0), phase.darts.map { it.y })
        assertEquals(listOf(1, 2, 3), phase.darts.map { it.number })
        assertEquals(listOf(true, false, false), phase.darts.map { it.unsure })
        assertEquals(75, phase.total)
        assertEquals(Crop(0.0, 0.0, 800.0, 800.0), phase.crop)
    }

    private fun board() = PhotoReading(800, 800, Located(BOARD))

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
