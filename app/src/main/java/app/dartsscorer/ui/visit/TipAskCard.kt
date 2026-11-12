package app.dartsscorer.ui.visit

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import app.dartsscorer.R
import app.dartsscorer.theme.Spacing

/**
 * The one time the app mentions the tip unasked (ADR-0007). Either button answers it for good, and
 * nothing here says what a tip buys, because it buys nothing.
 */
@Composable
internal fun TipAskCard(
    onTip: () -> Unit,
    onDecline: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth().padding(bottom = Spacing.tight)) {
        Column(modifier = Modifier.padding(Spacing.base)) {
            Text(stringResource(R.string.visit_tip_ask_title), style = MaterialTheme.typography.titleMedium)
            Text(
                text = stringResource(R.string.visit_tip_ask_body),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = Spacing.hair),
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
                modifier = Modifier.padding(top = Spacing.tight),
            ) {
                TextButton(onClick = onTip) { Text(stringResource(R.string.visit_tip_ask_accept)) }
                TextButton(onClick = onDecline) { Text(stringResource(R.string.visit_tip_ask_decline)) }
            }
        }
    }
}
