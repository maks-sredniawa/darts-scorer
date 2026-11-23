package app.dartsscorer.camera

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * `phase-G.md`, *Tests*: the store is under `noBackupFilesDir`, never under `filesDir`, whose
 * `datastore/` both backup rule files include whole. Fails toward a restored phone coming back in the
 * camera role with stale pins.
 */
class PairingStoreTest {
    @get:Rule val folder = TemporaryFolder()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val dataStore by lazy {
        PreferenceDataStoreFactory.create(scope = scope) { folder.newFile("pairing.preferences_pb") }
    }
    private val store by lazy { PairingStore(dataStore) }

    @After fun tearDown() = scope.cancel()

    @Test
    fun `the store file is under noBackupFilesDir and outside the backed-up datastore folder`() {
        val app = File("/data/user/0/com.maksforge.dartsscorer")
        val noBackup = File(app, "no_backup")
        val filesDir = File(app, "files")
        val file = pairingStoreFile(noBackup)
        assertEquals(noBackup, file.parentFile)
        assertFalse(file.path.startsWith(filesDir.path + File.separator))
    }

    @Test
    fun `the role is stored by enum name and defaults to the Player's phone`() =
        runBlocking {
            assertEquals(PhoneRole.PLAYER, store.role.first())
            store.setRole(PhoneRole.MOUNTED_CAMERA)
            assertEquals(PhoneRole.MOUNTED_CAMERA, store.role.first())
            assertEquals("MOUNTED_CAMERA", dataStore.data.first()[PairingStore.Keys.ROLE])
        }

    @Test
    fun `an unknown stored role reads as the Player's phone`() =
        runBlocking {
            dataStore.edit { it[PairingStore.Keys.ROLE] = "SOMETHING_LATER" }
            assertEquals(PhoneRole.PLAYER, store.role.first())
        }

    @Test
    fun `a pin is the payload's fingerprint, and unpairing clears it`() =
        runBlocking {
            val payload = PairingPayload(PairingPayload.VERSION, "AB".repeat(32), "CD".repeat(16))
            assertNull(store.playerPin.first())
            store.pinPlayer(payload)
            assertEquals(payload.fingerprint, store.playerPin.first())
            store.unpairPlayer()
            assertNull(store.playerPin.first())
        }

    @Test
    fun `the camera ask is remembered`() =
        runBlocking {
            assertFalse(store.cameraAsked.first())
            store.markCameraAsked()
            assertTrue(store.cameraAsked.first())
        }

    @Test
    fun `the Player's phone pins cameras as a list, and unpairing clears it`() =
        runBlocking {
            assertEquals(emptySet<String>(), store.cameraPins.first())
            store.pinCamera("AB".repeat(32))
            assertEquals(setOf("AB".repeat(32)), store.cameraPins.first())
            store.unpairCameras()
            assertEquals(emptySet<String>(), store.cameraPins.first())
        }
}
