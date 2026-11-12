package app.dartsscorer

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.data.ThemeMode
import app.dartsscorer.theme.applyThemeMode
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

/** Holds the one [AppContainer] for the process, and the preferences the first window needs. */
class MainApplication : Application() {
    /**
     * The scope for work that outlives any screen. `SupervisorJob` so one failed child does not
     * cancel its siblings — the closest JS analogue is `Promise.allSettled` semantics rather than
     * `Promise.all`.
     */
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** The preference store, read before the first window exists to choose the theme. */
    lateinit var preferences: AppPreferences
        private set

    /**
     * The theme mode as it was on disk at process start, so the very first composition paints in the
     * right palette rather than flashing light and repainting.
     */
    var startupThemeMode: ThemeMode = ThemeMode.SYSTEM
        private set

    val container: AppContainer by lazy { AppContainer(this, preferences, applicationScope) }

    override fun onCreate() {
        super.onCreate()

        preferences = AppPreferences(preferencesStore)

        // A blocking read, deliberately and exactly once. Everything else about DataStore is a Flow,
        // but this value has to be known before the first window is created — a Flow collected in a
        // composition arrives a frame later, which is a visible light flash for a user who chose
        // dark. One small file read at process start is the cheaper of the two costs.
        startupThemeMode = runBlocking { preferences.themeModeNow() }
        applyThemeMode(startupThemeMode)

        settleTipsOnEveryForeground()
    }

    /**
     * Play refunds a purchase nobody acknowledged within three days, so a tip that cleared while the
     * app was closed — or was paid just before a process death — is consumed the next time the user
     * opens the app, whichever screen that is (ADR-0007). On *start*, not at process creation: a
     * broadcast starts the process too, and binding Play for those wakes it for nobody.
     */
    private fun settleTipsOnEveryForeground() {
        // Kotlin note: an `object :` expression is an anonymous class instance — the listener object
        // JS would pass inline. Added on the main thread, which `ProcessLifecycleOwner` requires.
        ProcessLifecycleOwner.get().lifecycle.addObserver(
            object : DefaultLifecycleObserver {
                override fun onStart(owner: LifecycleOwner) {
                    applicationScope.launch { container.tipJar.settlePending() }
                }
            },
        )
    }
}
