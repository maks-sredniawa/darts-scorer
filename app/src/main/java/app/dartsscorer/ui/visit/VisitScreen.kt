package app.dartsscorer.ui.visit

import android.Manifest
import android.content.ActivityNotFoundException
import androidx.activity.compose.LocalActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityCompat
import androidx.core.net.toUri
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras
import app.dartsscorer.ui.common.NoticeBanner
import app.dartsscorer.ui.common.OpenAppSettingsButton
import app.dartsscorer.ui.common.hasCameraPermission
import app.dartsscorer.ui.common.isShortWindow

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitScreen(
    onOpenSupport: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: VisitViewModel =
        viewModel(factory = VisitViewModel.Factory, extras = appViewModelExtras()),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LifecycleEventEffect(Lifecycle.Event.ON_STOP) { viewModel.keepShown() }
    LifecycleStartEffect(viewModel) {
        viewModel.startLink()
        onStopOrDispose { viewModel.stopLink() }
    }

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture(), viewModel::cameraReturned)
    val picker =
        rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
            viewModel.photoChosen(uri?.toString())
        }
    val openCamera = {
        try {
            camera.launch(viewModel.cameraTarget().toUri())
        } catch (e: ActivityNotFoundException) {
            viewModel.cameraUnavailable()
        }
    }
    // Declaring CAMERA for the Mounted camera makes the system camera intent need it too (phase-G.md D5).
    val askCamera =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            viewModel.cameraPermissionAnswered(granted)
            if (granted) openCamera()
        }
    val context = LocalContext.current
    val activity = LocalActivity.current
    val takePhoto = {
        if (context.hasCameraPermission()) {
            openCamera()
        } else {
            val explain =
                activity?.let {
                    ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
                } ?: false
            viewModel.cameraNotAllowed(explain)
        }
    }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { if (context.hasCameraPermission()) viewModel.cameraAllowed() }
    if (state.cameraRationale) {
        CameraRationale(
            onContinue = {
                viewModel.cameraRationaleClosed()
                askCamera.launch(Manifest.permission.CAMERA)
            },
            onDismiss = viewModel::cameraRationaleClosed,
        )
    }
    val choosePhoto = {
        try {
            picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        } catch (e: ActivityNotFoundException) {
            viewModel.photoChosen(null)
        }
    }

    val snackbar = remember { SnackbarHostState() }
    val density = LocalDensity.current
    var snackbarHeight by remember { mutableStateOf(0.dp) }
    val resources = LocalResources.current
    val removedMessage =
        state.removed?.let {
            stringResource(R.string.visit_removed, it.number, resources.spokenName(it.score))
        }
    val undo = stringResource(R.string.visit_undo)
    // No timer to adjust (WCAG 2.2.1): the snackbar stays until Undo, its dismiss action or the
    // Visit's next change, which clears `removed` and so cancels this effect.
    LaunchedEffect(state.removed) {
        if (removedMessage == null) return@LaunchedEffect
        val result =
            snackbar.showSnackbar(
                removedMessage,
                actionLabel = undo,
                withDismissAction = true,
                duration = SnackbarDuration.Indefinite,
            )
        if (result == SnackbarResult.ActionPerformed) viewModel.undoRemove() else viewModel.removalSettled()
    }

    val phase = state.phase
    val photo: (@Composable (beside: Boolean) -> Unit)? =
        when (phase) {
            is VisitPhase.Scored -> { beside ->
                BoardPhoto(
                    phase,
                    viewModel::openDart,
                    viewModel::addDartAt,
                    viewModel::moveDart,
                    beside,
                )
            }
            is VisitPhase.NoBoard -> { beside -> WholePhoto(phase.photo, phase.width, phase.height, beside) }
            is VisitPhase.Entered -> { beside -> WholePhoto(phase.photo, phase.width, phase.height, beside) }
            else -> null
        }
    // Beside the Photo in a short window the title would only take height from it; the rail's
    // selected tab already says where the player is.
    val photoBeside = photo != null && isShortWindow()
    Scaffold(
        modifier = modifier,
        topBar = { if (!photoBeside) TopAppBar(title = { Text(stringResource(R.string.tab_visit)) }) },
        // The snackbar has no timer, so the screen makes room for it rather than hide the buttons under it.
        snackbarHost = {
            SnackbarHost(snackbar, Modifier.onSizeChanged { snackbarHeight = with(density) { it.height.toDp() } })
        },
    ) { insets ->
        val notice: @Composable () -> Unit = { Notice(state.notice) }
        val details: @Composable ColumnScope.() -> Unit = {
            when (phase) {
                VisitPhase.Empty -> EmptyVisit(state.showTipAsk, viewModel::answerTipAsk, onOpenSupport)
                VisitPhase.Reading -> ReadingPhoto(state.focus == VisitFocus.Reading, viewModel::focusPlaced)
                is VisitPhase.NoBoard -> NoBoardBanner(phase)
                is VisitPhase.Shown ->
                    ShownDetails(
                        phase,
                        state.focus,
                        onOpenDart = viewModel::openDart,
                        onRemoveDart = viewModel::removeDart,
                        onAddDart = viewModel::addDart,
                        onFocusPlaced = viewModel::focusPlaced,
                    )
            }
        }
        val mounted = state.camera?.let { MountedAction(it, viewModel::takeWithMountedCamera) }
        val actions: @Composable () -> Unit = {
            when (phase) {
                VisitPhase.Empty -> Actions(stringResource(R.string.visit_take_photo), takePhoto, choosePhoto, mounted)
                VisitPhase.Reading -> Unit
                is VisitPhase.NoBoard ->
                    Actions(
                        stringResource(R.string.visit_take_another),
                        takePhoto,
                        choosePhoto,
                        mounted,
                        EnterScoreAction(
                            viewModel::addDart,
                            state.focus == VisitFocus.EnterScore,
                            viewModel::focusPlaced,
                        ),
                    )
                // With a Mounted camera paired, Next Visit would be a guess at which camera: the
                // player taps the one they want (phase-G.md §5).
                is VisitPhase.Shown ->
                    Actions(
                        stringResource(if (mounted == null) R.string.visit_next else R.string.visit_take_photo),
                        takePhoto,
                        choosePhoto,
                        mounted,
                    )
            }
        }
        if (photo != null && photoBeside) {
            Row(modifier = Modifier.fillMaxSize().padding(insets)) {
                Box(modifier = Modifier.fillMaxHeight().padding(Spacing.base), contentAlignment = Alignment.Center) {
                    photo(true)
                }
                Column(modifier = Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState())) {
                    notice()
                    Column(modifier = Modifier.fillMaxWidth().padding(Spacing.base), content = details)
                    Spacer(Modifier.weight(1f))
                    actions()
                    Spacer(Modifier.height(snackbarHeight))
                }
            }
        } else {
            // fillMaxSize's minimum height reaches the scrolled Column, so the Spacer's weight keeps the
            // buttons at the bottom whenever everything fits, and everything scrolls when it does not.
            Column(modifier = Modifier.fillMaxSize().padding(insets).verticalScroll(rememberScrollState())) {
                notice()
                Column(modifier = Modifier.fillMaxWidth().padding(Spacing.base)) {
                    if (phase is VisitPhase.NoBoard) NoBoardBanner(phase)
                    if (photo != null) {
                        Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { photo(false) }
                    }
                    if (phase !is VisitPhase.NoBoard) {
                        Column(
                            modifier = if (photo != null) Modifier.padding(top = Spacing.base) else Modifier,
                            content = details,
                        )
                    }
                }
                Spacer(Modifier.weight(1f))
                actions()
                Spacer(Modifier.height(snackbarHeight))
            }
        }
    }

    state.keypad?.let { keypad ->
        KeypadSheet(
            keypad,
            onRing = viewModel::pickRing,
            onNumber = viewModel::pickNumber,
            onBullOrMiss = viewModel::pickBullOrMiss,
            onDone = viewModel::commitKeypad,
            onRemove = viewModel::removeDart,
            onBackToReading = viewModel::backToReading,
            onDismiss = viewModel::dismissKeypad,
        )
    }
}

@Composable
private fun Notice(notice: VisitNotice?) {
    val spacing = Modifier.padding(start = Spacing.base, end = Spacing.base, top = Spacing.base)
    when (notice) {
        VisitNotice.NoCamera ->
            NoticeBanner(
                stringResource(R.string.visit_no_camera_title),
                stringResource(R.string.visit_no_camera_body),
                spacing,
            )
        VisitNotice.CameraDenied ->
            NoticeBanner(
                stringResource(R.string.camera_denied_title),
                stringResource(R.string.visit_camera_denied_body),
                spacing,
                action = { OpenAppSettingsButton() },
            )
        VisitNotice.Unreadable ->
            NoticeBanner(
                stringResource(R.string.visit_unreadable_title),
                stringResource(R.string.visit_unreadable_body),
                spacing,
            )
        null -> Unit
    }
}

@Composable
private fun CameraRationale(
    onContinue: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        text = { Text(stringResource(R.string.visit_camera_rationale)) },
        confirmButton = { TextButton(onClick = onContinue) { Text(stringResource(R.string.visit_camera_continue)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.visit_camera_not_now)) } },
    )
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
        modifier = Modifier.padding(top = Spacing.section).semantics { heading() },
    )
    Text(
        text = stringResource(R.string.visit_empty_body),
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = Spacing.tight),
    )
}

@Composable
private fun ReadingPhoto(
    focusRequested: Boolean,
    onFocusPlaced: () -> Unit,
) {
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
            modifier =
                Modifier.semantics { liveRegion = LiveRegionMode.Polite }.takesFocusWhen(focusRequested, onFocusPlaced),
        )
    }
}

@Composable
private fun Actions(
    takeLabel: String,
    onTake: () -> Unit,
    onChoose: () -> Unit,
    mounted: MountedAction?,
    enterScore: EnterScoreAction? = null,
) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(horizontal = Spacing.base, vertical = Spacing.tight),
        verticalArrangement = Arrangement.spacedBy(Spacing.tight),
    ) {
        if (mounted != null) {
            MountedCameraActions(mounted.camera, mounted.onTake)
            OutlinedButton(onClick = onTake, modifier = Modifier.fillMaxWidth()) { Text(takeLabel) }
        } else {
            Button(onClick = onTake, modifier = Modifier.fillMaxWidth()) { Text(takeLabel) }
        }
        OutlinedButton(onClick = onChoose, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.visit_choose_photo))
        }
        enterScore?.let {
            OutlinedButton(
                onClick = it.onClick,
                modifier = Modifier.fillMaxWidth().takesFocusWhen(it.focusRequested, it.onFocusPlaced),
            ) {
                Text(stringResource(R.string.visit_enter_score))
            }
        }
    }
}

private class MountedAction(
    val camera: MountedCameraUi,
    val onTake: () -> Unit,
)

private class EnterScoreAction(
    val onClick: () -> Unit,
    val focusRequested: Boolean,
    val onFocusPlaced: () -> Unit,
)
