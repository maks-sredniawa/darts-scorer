package app.dartsscorer

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.media.MediaFiles
import app.dartsscorer.tip.TipJar
import kotlinx.coroutines.CoroutineScope
import java.time.Instant

/**
 * `internal` rather than private: [MainApplication] holds the one [AppPreferences] over this store
 * and hands it to the container, because the theme has to read a preference before the first window
 * exists.
 *
 * Kotlin note: `by preferencesDataStore(...)` is a property delegate on `Context` — it creates the
 * store once per process and hands the same instance to every caller. Creating a second DataStore
 * over the same file throws, so this must stay the only one.
 */
internal val Context.preferencesStore: DataStore<Preferences> by preferencesDataStore(name = "app_preferences")

/**
 * Manual dependency injection — deliberately not Hilt.
 *
 * At the size a single-developer app reaches, constructing things by hand is clearer than a
 * generated graph: the whole object graph is this file, you can read it top to bottom, and there is
 * no annotation processor round trip in every build. Migrating to Hilt later is mechanical, because
 * everything here is already constructor injection.
 *
 * The rule that makes it work: **nothing constructs its own dependencies.** A ViewModel takes what
 * it needs from here, and only this file calls a constructor.
 * The moment a class reaches for a singleton instead, it stops being testable without a device.
 *
 * Lives at the package root with the app shell: like `Navigation.kt`, it describes how the app hangs
 * together rather than belonging to any one screen.
 */
class AppContainer(
    context: Context,
    val preferences: AppPreferences,
    @Suppress("unused") private val applicationScope: CoroutineScope,
) {
    private val appContext = context.applicationContext

    val media by lazy { MediaFiles(appContext) }

    /**
     * The tip (ADR-0007). Here rather than in a `ViewModel` because a purchase can finish after the
     * screen that opened Play's sheet is gone, and it still has to be consumed — see [TipJar].
     */
    val tipJar = TipJar(appContext, applicationScope)

    /** When this package was first installed on this phone — the tip ask's clock, not a restore's. */
    val installedAt: Instant by lazy {
        val packageManager = appContext.packageManager
        val info =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                packageManager.getPackageInfo(appContext.packageName, PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                packageManager.getPackageInfo(appContext.packageName, 0)
            }
        Instant.ofEpochMilli(info.firstInstallTime)
    }
}
