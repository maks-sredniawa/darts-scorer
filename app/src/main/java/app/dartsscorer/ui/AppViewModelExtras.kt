package app.dartsscorer.ui

import android.app.Application
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.HasDefaultViewModelProviderFactory
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.MutableCreationExtras
import androidx.lifecycle.viewmodel.compose.LocalViewModelStoreOwner

/**
 * The `CreationExtras` a ViewModel factory needs inside a navigation entry.
 *
 * Nav3 hands every back-stack entry its own `ViewModelStoreOwner` (see `appEntryDecorators` in
 * `Navigation.kt`) — that is what makes a ViewModel die with the screen that owns it. Its default
 * extras carry the saved-state keys `createSavedStateHandle()` reads, but not `APPLICATION_KEY`, and
 * every factory here reads that key to reach `AppContainer`. Without it `this[APPLICATION_KEY]` is
 * null and the cast in the initializer throws the moment the screen opens.
 *
 * So a screen inside a navigation entry passes this: `viewModel(factory = …, extras = …)`: the
 * entry's own extras with the application added. Composables outside `NavDisplay` resolve to the
 * Activity and need nothing.
 */
@Composable
fun appViewModelExtras(): CreationExtras {
    val application = LocalContext.current.applicationContext as Application
    val owner = LocalViewModelStoreOwner.current
    // Kotlin note: `remember(keys)` is useMemo — rebuilt only when the application or the entry's
    // owner changes, so the extras are allocated once per screen.
    return remember(application, owner) {
        val defaults = (owner as? HasDefaultViewModelProviderFactory)?.defaultViewModelCreationExtras
        MutableCreationExtras(defaults ?: CreationExtras.Empty).apply { set(APPLICATION_KEY, application) }
    }
}
