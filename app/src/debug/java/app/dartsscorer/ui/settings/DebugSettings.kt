package app.dartsscorer.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.isTraversalGroup
import androidx.compose.ui.semantics.semantics
import app.dartsscorer.R
import app.dartsscorer.scoring.LiteRtModel
import app.dartsscorer.scoring.READ_THREAD_CHOICES
import app.dartsscorer.scoring.readThreads
import app.dartsscorer.scoring.setReadThreads
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.common.SectionHeader
import app.dartsscorer.ui.visit.markedVisits
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The developer-only section of Settings. **This file exists only in the debug source set** — see
 * the release half for why that is a source set and not a `BuildConfig.DEBUG` branch.
 */
@Composable
fun DebugSettings() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val threadsFlow = remember(context) { readThreads(context) }
    val threads by threadsFlow.collectAsState(initial = LiteRtModel.DEFAULT_THREADS)
    val marked by produceState(0, context) { value = withContext(Dispatchers.IO) { markedVisits(context) } }
    SectionHeader(stringResource(R.string.debug_settings))
    Column(
        modifier = Modifier.padding(horizontal = Spacing.base).semantics { isTraversalGroup = true },
    ) {
        Text(
            stringResource(R.string.debug_read_threads),
            modifier = Modifier.semantics { heading() },
        )
        Row(modifier = Modifier.selectableGroup()) {
            for (choice in READ_THREAD_CHOICES) {
                val description = pluralStringResource(R.plurals.debug_read_threads_choice, choice, choice)
                FilterChip(
                    selected = threads == choice,
                    onClick = { scope.launch { setReadThreads(context, choice) } },
                    label = { Text("$choice") },
                    modifier =
                        Modifier.padding(end = Spacing.tight).semantics {
                            contentDescription = description
                        },
                )
            }
        }
        Text(
            pluralStringResource(R.plurals.debug_marked_visits, marked, marked),
            modifier = Modifier.padding(top = Spacing.base),
        )
    }
}
