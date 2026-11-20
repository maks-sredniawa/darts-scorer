package app.dartsscorer.ui.visit

import android.content.ActivityNotFoundException
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.core.net.toUri
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

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture(), viewModel::cameraReturned)
    val picker =
        rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
            viewModel.photoChosen(uri?.toString())
        }
    val takePhoto = {
        try {
            camera.launch(viewModel.cameraTarget().toUri())
        } catch (e: ActivityNotFoundException) {
            viewModel.cameraUnavailable()
        }
    }
    val choosePhoto = {
        try {
            picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        } catch (e: ActivityNotFoundException) {
            viewModel.photoChosen(null)
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_visit)) }) },
    ) { insets ->
        Column(modifier = Modifier.fillMaxSize().padding(insets)) {
            val noticeSpacing = Modifier.padding(start = Spacing.base, end = Spacing.base, top = Spacing.base)
            when (state.notice) {
                VisitNotice.NoCamera ->
                    NoticeBanner(
                        stringResource(R.string.visit_no_camera_title),
                        stringResource(R.string.visit_no_camera_body),
                        noticeSpacing,
                    )
                VisitNotice.Unreadable ->
                    NoticeBanner(
                        stringResource(R.string.visit_unreadable_title),
                        stringResource(R.string.visit_unreadable_body),
                        noticeSpacing,
                    )
                null -> Unit
            }
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState())
                        .padding(Spacing.base),
            ) {
                when (val phase = state.phase) {
                    VisitPhase.Empty -> EmptyVisit(state.showTipAsk, viewModel::answerTipAsk, onOpenSupport)
                    VisitPhase.Reading -> ReadingPhoto()
                    is VisitPhase.NoBoard -> NoBoardFound(phase)
                    is VisitPhase.Scored -> ScoredVisit(phase)
                }
            }
            when (state.phase) {
                VisitPhase.Empty ->
                    Actions(stringResource(R.string.visit_take_photo), takePhoto, choosePhoto)
                VisitPhase.Reading -> Unit
                is VisitPhase.NoBoard ->
                    Actions(stringResource(R.string.visit_take_another), takePhoto, choosePhoto)
                is VisitPhase.Scored ->
                    Actions(stringResource(R.string.visit_next), takePhoto, choosePhoto)
            }
        }
    }
}

@Composable
private fun EmptyVisit(
    showTipAsk: Boolean,
    answerTipAsk: () -> Unit,
    onOpenSupport: () -> Unit,
) {
    if (showTipAsk) {
        TipAskCard(
            onTip = {
                answerTipAsk()
                onOpenSupport()
            },
            onDecline = answerTipAsk,
        )
    }
    Text(
        text = stringResource(R.string.visit_empty_title),
        style = MaterialTheme.typography.headlineSmall,
        modifier = Modifier.padding(top = Spacing.section),
    )
    Text(
        text = stringResource(R.string.visit_empty_body),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = Spacing.tight),
    )
}

@Composable
private fun ReadingPhoto() {
    Column(
        modifier = Modifier.fillMaxWidth().padding(top = Spacing.block),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Spacing.base),
    ) {
        CircularProgressIndicator()
        Text(
            text = stringResource(R.string.visit_reading),
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
        )
    }
}

/** Controls sit in the bottom third, so a Visit is one tap with the phone in one hand. */
@Composable
private fun Actions(
    takeLabel: String,
    onTake: () -> Unit,
    onChoose: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(horizontal = Spacing.base, vertical = Spacing.tight),
        verticalArrangement = Arrangement.spacedBy(Spacing.tight),
    ) {
        Button(onClick = onTake, modifier = Modifier.fillMaxWidth()) { Text(takeLabel) }
        OutlinedButton(onClick = onChoose, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.visit_choose_photo))
        }
    }
}
