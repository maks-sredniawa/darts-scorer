package app.dartsscorer.ui.visit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import app.dartsscorer.MainApplication
import app.dartsscorer.data.AppPreferences
import app.dartsscorer.tip.TipJar
import app.dartsscorer.tip.tipAskDue
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.Instant

data class VisitUiState(
    /** False wherever Play will not sell a tip: nothing is asked for that cannot be bought. */
    val showTipAsk: Boolean = false,
)

class VisitViewModel(
    private val preferences: AppPreferences,
    tipJar: TipJar,
    installedAt: Instant,
) : ViewModel() {
    val state: StateFlow<VisitUiState> =
        combine(preferences.tipAsked, preferences.visitsScored, tipJar.offers) { asked, visits, offers ->
            VisitUiState(showTipAsk = offers.isNotEmpty() && tipAskDue(asked, visits, installedAt, Instant.now()))
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), VisitUiState())

    init {
        // Prices are queried only once the ask could be due, saving a product query on every other
        // start. The binding itself happens on every foreground anyway, to settle tips.
        viewModelScope.launch {
            val due =
                tipAskDue(preferences.tipAsked.first(), preferences.visitsScored.first(), installedAt, Instant.now())
            if (due) tipJar.refresh()
        }
    }

    fun answerTipAsk() {
        viewModelScope.launch { preferences.markTipAsked() }
    }

    companion object {
        val Factory: ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val app = this[APPLICATION_KEY] as MainApplication
                    VisitViewModel(
                        app.container.preferences,
                        app.container.tipJar,
                        app.container.installedAt,
                    )
                }
            }
    }
}
