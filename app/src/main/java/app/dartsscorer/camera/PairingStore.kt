package app.dartsscorer.camera

import android.util.Log
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.io.File

/** What this phone is to the Mounted camera feature. Stored by name (ADR-0009, decision 9). */
enum class PhoneRole {
    PLAYER,
    MOUNTED_CAMERA,
}

/**
 * Where the pairing store lives: `noBackupFilesDir`, never under `filesDir`, whose `datastore/` both
 * backup rule files include whole (ADR-0009, decision 4).
 */
fun pairingStoreFile(noBackupFilesDir: File): File = File(noBackupFilesDir, "pairing.preferences_pb")

/**
 * The role, the pins and the camera ask: what belongs to this phone and must not come back on another
 * one from a backup. A restored phone starts unpaired, since its Keystore key did not travel with it,
 * and a runtime grant never travels, so neither does the record of having asked for one.
 */
class PairingStore(
    private val store: DataStore<Preferences>,
) {
    internal object Keys {
        val ROLE = stringPreferencesKey("role")
        val PLAYER_PIN = stringPreferencesKey("player_pin")
        val CAMERA_ASKED = booleanPreferencesKey("camera_asked")
    }

    val role: Flow<PhoneRole> =
        store.data.map { prefs ->
            prefs[Keys.ROLE]?.let { name -> runCatching { enumValueOf<PhoneRole>(name) }.getOrNull() }
                ?: PhoneRole.PLAYER
        }

    /** On a Mounted camera, the fingerprint of the Player's phone it answers, or null while unpaired. */
    val playerPin: Flow<String?> = store.data.map { it[Keys.PLAYER_PIN] }

    /** Whether the handheld *Take a Photo* has asked for `CAMERA` on this phone (`phase-G.md` D5). */
    val cameraAsked: Flow<Boolean> = store.data.map { it[Keys.CAMERA_ASKED] ?: false }

    suspend fun setRole(role: PhoneRole) {
        store.edit { it[Keys.ROLE] = role.name }
    }

    suspend fun pinPlayer(payload: PairingPayload) {
        store.edit { it[Keys.PLAYER_PIN] = payload.fingerprint }
        Log.i(TAG, "Pinned the Player's phone ${payload.fingerprint}")
    }

    suspend fun unpairPlayer() {
        store.edit { it.remove(Keys.PLAYER_PIN) }
        Log.i(TAG, "Unpaired the Player's phone")
    }

    suspend fun markCameraAsked() {
        store.edit { it[Keys.CAMERA_ASKED] = true }
    }

    companion object {
        const val TAG = "MountedCamera"
    }
}
