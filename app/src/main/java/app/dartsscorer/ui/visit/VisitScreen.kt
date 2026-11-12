package app.dartsscorer.ui.visit

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitScreen(
    onOpenSupport: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: VisitViewModel =
        viewModel(factory = VisitViewModel.Factory, extras = appViewModelExtras()),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        modifier = modifier,
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_visit)) }) },
    ) { insets ->
        Column(modifier = Modifier.fillMaxSize().padding(insets).padding(Spacing.base)) {
            if (state.showTipAsk) {
                TipAskCard(
                    onTip = {
                        viewModel.answerTipAsk()
                        onOpenSupport()
                    },
                    onDecline = viewModel::answerTipAsk,
                )
            }
        }
    }
}
