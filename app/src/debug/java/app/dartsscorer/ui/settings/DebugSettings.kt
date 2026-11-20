package app.dartsscorer.ui.settings

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import app.dartsscorer.R
import app.dartsscorer.scoring.LiteRtModel
import app.dartsscorer.scoring.READ_THREAD_CHOICES
import app.dartsscorer.scoring.readThreads
import app.dartsscorer.scoring.setReadThreads
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.common.SectionHeader
import kotlinx.coroutines.launch

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
    SectionHeader(stringResource(R.string.debug_settings))
    Text(
        stringResource(R.string.debug_read_threads),
        modifier = Modifier.padding(horizontal = Spacing.base),
    )
    Row(modifier = Modifier.padding(horizontal = Spacing.base)) {
        for (choice in READ_THREAD_CHOICES) {
            FilterChip(
                selected = threads == choice,
                onClick = { scope.launch { setReadThreads(context, choice) } },
                label = { Text("$choice") },
                modifier = Modifier.padding(end = Spacing.tight),
            )
        }
    }
}
