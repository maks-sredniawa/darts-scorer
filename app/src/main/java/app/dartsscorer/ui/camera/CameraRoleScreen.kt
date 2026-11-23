package app.dartsscorer.ui.camera

import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.view.Surface
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.annotation.StringRes
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.rememberVectorPainter
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.Observer
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.camera.DimSlot
import app.dartsscorer.link.CameraLinkState
import app.dartsscorer.theme.DarkAppTheme
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras
import app.dartsscorer.ui.common.NoticeBanner
import app.dartsscorer.ui.common.OpenAppSettingsButton
import app.dartsscorer.ui.common.hasCameraPermission
import app.dartsscorer.ui.common.isShortWindow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

private val CONTROL_PANE_WIDTH = 320.dp
private const val RING_OF_SHORTER_SIDE = 0.8f
private val CROSS = 16.dp
private val FOCUS_OUTLINE = 2.dp
private const val DIALOG_SETTLE_MILLIS = 1_500L

/**
 * The Mounted camera's screen (`phase-G.md` §3, and the 2026-11-23 design): the preview and the
 * controls in two panes that never overlap, dimmed after a capture once nobody touches it. Back
 * leaves the app and keeps the role; only *Stop being a camera* ends it.
 */
@Composable
fun CameraRoleScreen(
    onStop: () -> Unit,
    viewModel: CameraRoleViewModel =
        viewModel(factory = CameraRoleViewModel.Factory, extras = appViewModelExtras()),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val activity = LocalActivity.current
    val scope = rememberCoroutineScope()

    BackHandler { activity?.finish() }
    LifecycleStartEffect(viewModel) {
        viewModel.startLink()
        onStopOrDispose { viewModel.stopLink() }
    }
    KeepScreenOn()
    DimmedWindow(state.dimmed)

    var granted by remember { mutableStateOf(context.hasCameraPermission()) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { granted = context.hasCameraPermission() }
    if (granted) {
        val owner = LocalLifecycleOwner.current
        val view = LocalView.current
        DisposableEffect(owner) {
            viewModel.bind(owner, view.display?.rotation ?: Surface.ROTATION_0)
            onDispose { viewModel.unbind() }
        }
        DisplayRotation(viewModel::rotated)
    }
    AssistiveActivity(viewModel::touched)

    val stop: () -> Unit = {
        scope.launch {
            viewModel.stop()
            onStop()
        }
    }

    DarkAppTheme(dynamicColor = state.materialYou) {
        Box(
            modifier =
                Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.surface)
                    .onPreviewKeyEvent {
                        viewModel.touched()
                        false
                    }.pointerInput(Unit) {
                        awaitPointerEventScope {
                            while (true) {
                                val event = awaitPointerEvent(PointerEventPass.Initial)
                                if (event.type == PointerEventType.Press) viewModel.touched()
                            }
                        }
                    },
        ) {
            if (state.dimmed) {
                Dimmed(state.link, state.slot, viewModel::wake)
            } else {
                val controls: @Composable (Modifier) -> Unit = { modifier ->
                    ControlPane(state, granted, viewModel, stop, modifier)
                }
                if (isShortWindow()) {
                    Row(Modifier.fillMaxSize()) {
                        PreviewPane(
                            viewModel,
                            Modifier.weight(1f).fillMaxHeight(),
                            WindowInsets.safeDrawing.only(WindowInsetsSides.Start + WindowInsetsSides.Vertical),
                        )
                        controls(
                            Modifier
                                .width(CONTROL_PANE_WIDTH)
                                .fillMaxHeight()
                                .windowInsetsPadding(
                                    WindowInsets.safeDrawing.only(WindowInsetsSides.End + WindowInsetsSides.Vertical),
                                ),
                        )
                    }
                } else {
                    Column(Modifier.fillMaxSize()) {
                        PreviewPane(
                            viewModel,
                            Modifier.weight(1f).fillMaxWidth(),
                            WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal),
                        )
                        controls(
                            Modifier
                                .fillMaxWidth()
                                .windowInsetsPadding(
                                    WindowInsets.safeDrawing.only(
                                        WindowInsetsSides.Bottom + WindowInsetsSides.Horizontal,
                                    ),
                                ),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PreviewPane(
    viewModel: CameraRoleViewModel,
    modifier: Modifier,
    insets: WindowInsets,
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val description = stringResource(R.string.camera_role_scan_area)
    val preview =
        remember(context) {
            PreviewView(context).apply {
                scaleType = PreviewView.ScaleType.FIT_CENTER
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
            }
        }
    var aspect by remember { mutableStateOf<Float?>(null) }
    DisposableEffect(preview, owner) {
        viewModel.showPreviewOn(preview.surfaceProvider)
        val streaming =
            Observer<PreviewView.StreamState> {
                if (it ==
                    PreviewView.StreamState.STREAMING
                ) {
                    aspect = viewModel.previewAspect()
                }
            }
        preview.previewStreamState.observe(owner, streaming)
        onDispose {
            preview.previewStreamState.removeObserver(streaming)
            viewModel.showPreviewOn(null)
        }
    }
    Box(
        modifier =
            modifier
                .background(MaterialTheme.colorScheme.scrim)
                .windowInsetsPadding(insets)
                .semantics { contentDescription = description },
    ) {
        AndroidView(factory = { preview }, modifier = Modifier.fillMaxSize())
        BoardRing(aspect, Modifier.fillMaxSize())
    }
}

/** Where the Board should sit: a ring on the displayed image, not on the pane around it. */
@Composable
private fun BoardRing(
    aspect: Float?,
    modifier: Modifier,
) {
    val under = MaterialTheme.colorScheme.scrim
    val over = MaterialTheme.colorScheme.onSurface
    Canvas(modifier.clearAndSetSemantics {}) {
        val image = fitted(size, aspect)
        val radius = minOf(image.width, image.height) * RING_OF_SHORTER_SIDE / 2
        drawRing(image.center, radius, under, 4.dp.toPx())
        drawRing(image.center, radius, over, 2.dp.toPx())
    }
}

private fun DrawScope.drawRing(
    centre: Offset,
    radius: Float,
    color: Color,
    width: Float,
) {
    drawCircle(color, radius, centre, style = Stroke(width))
    val arm = CROSS.toPx() / 2
    drawLine(color, centre - Offset(arm, 0f), centre + Offset(arm, 0f), width)
    drawLine(color, centre - Offset(0f, arm), centre + Offset(0f, arm), width)
}

private fun fitted(
    pane: Size,
    aspect: Float?,
): Rect {
    if (aspect == null || pane.height == 0f) return Rect(Offset.Zero, pane)
    val width = minOf(pane.width, pane.height * aspect)
    val height = width / aspect
    return Rect(Offset((pane.width - width) / 2, (pane.height - height) / 2), Size(width, height))
}

@Composable
private fun ControlPane(
    state: CameraRoleUiState,
    granted: Boolean,
    viewModel: CameraRoleViewModel,
    onStop: () -> Unit,
    modifier: Modifier,
) {
    val headingFocus = remember { FocusRequester() }
    var focusedSwaps by remember { mutableIntStateOf(state.pairingSwaps) }
    val window = LocalWindowInfo.current
    LaunchedEffect(state.pairingSwaps) {
        if (state.pairingSwaps != focusedSwaps) {
            if (state.paired == false) {
                // Unpairing is confirmed in a dialog, and TalkBack places its own focus about a second
                // after that window closes, overriding any move made before then.
                snapshotFlow { window.isWindowFocused }.first { it }
                delay(DIALOG_SETTLE_MILLIS)
            }
            headingFocus.requestFocus()
            focusedSwaps = state.pairingSwaps
        }
    }

    Surface(color = MaterialTheme.colorScheme.surface, modifier = modifier) {
        Column(modifier = Modifier.verticalScroll(rememberScrollState()).padding(Spacing.base)) {
            Status(state.link, state.paired.takeIf { state.pairingSwaps > 0 })
            if (!granted) {
                NoticeBanner(
                    stringResource(R.string.camera_denied_title),
                    stringResource(R.string.mounted_camera_denied_body),
                    Modifier.padding(top = Spacing.base),
                    action = { OpenAppSettingsButton() },
                )
            } else if (state.cameraFailed) {
                Text(
                    stringResource(R.string.camera_role_unavailable),
                    color = MaterialTheme.colorScheme.error,
                    modifier =
                        Modifier
                            .padding(top = Spacing.base)
                            .semantics { liveRegion = LiveRegionMode.Assertive },
                )
            }
            Spacer(Modifier.height(Spacing.base))
            when (state.paired) {
                true -> PairedBlock(viewModel::unpair, viewModel::inputActive, headingFocus)
                false -> PairingBlock(state, viewModel, headingFocus)
                null -> Unit
            }
            Spacer(Modifier.height(Spacing.section))
            OutlinedButton(onClick = onStop, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.camera_role_stop))
            }
            DebugCapture(viewModel::capture)
            DebugCameraLink()
        }
    }
}

/** [pairedChange] is set once pairing has changed on this screen, so the live region speaks it. */
@Composable
private fun Status(
    link: CameraLinkState,
    pairedChange: Boolean?,
) {
    val change =
        when (pairedChange) {
            true -> stringResource(R.string.camera_role_paired)
            false -> stringResource(R.string.camera_role_unpaired)
            null -> null
        }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
        modifier =
            Modifier.semantics(mergeDescendants = true) {
                liveRegion = LiveRegionMode.Polite
                if (change != null) stateDescription = change
            },
    ) {
        val icon =
            when (link) {
                CameraLinkState.WAITING -> painterResource(R.drawable.ic_hourglass_empty)
                CameraLinkState.CONNECTED -> rememberVectorPainter(Icons.Filled.CheckCircle)
                CameraLinkState.PAIR_AGAIN, CameraLinkState.OUTDATED -> rememberVectorPainter(Icons.Filled.Warning)
            }
        Icon(icon, contentDescription = null)
        Text(stringResource(link.label()), style = MaterialTheme.typography.titleMedium)
    }
}

@StringRes
private fun CameraLinkState.label(): Int =
    when (this) {
        CameraLinkState.WAITING -> R.string.camera_role_waiting
        CameraLinkState.CONNECTED -> R.string.link_connected
        CameraLinkState.PAIR_AGAIN -> R.string.link_pair_again
        CameraLinkState.OUTDATED -> R.string.link_outdated
    }

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PairingBlock(
    state: CameraRoleUiState,
    viewModel: CameraRoleViewModel,
    headingFocus: FocusRequester,
) {
    val context = LocalContext.current
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    var focused by remember { mutableStateOf(false) }
    val keyboard = WindowInsets.isImeVisible
    LaunchedEffect(focused || keyboard) { viewModel.inputActive(focused || keyboard) }
    // Pairing removes this block with the field still focused, so the screen must not stay held awake.
    DisposableEffect(Unit) { onDispose { viewModel.inputActive(false) } }
    val rejected = stringResource(R.string.camera_role_not_a_code)
    var code by rememberSaveable { mutableStateOf("") }
    val edit = { text: String ->
        code = text
        viewModel.codeChanged()
    }
    val pair = { if (viewModel.pairWithCode(code)) code = "" }

    Text(
        stringResource(R.string.camera_role_scan_title),
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.focusRequester(headingFocus).focusable().semantics { heading() },
    )
    Text(
        stringResource(R.string.camera_role_scan_hint),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = Spacing.hair),
    )
    Row(
        modifier = Modifier.padding(top = Spacing.snug),
        horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = code,
            onValueChange = edit,
            modifier =
                Modifier
                    .weight(1f)
                    .onFocusChanged { focused = it.isFocused }
                    .semantics { if (state.codeRejected) error(rejected) },
            singleLine = true,
            label = { Text(stringResource(R.string.camera_role_paste_label)) },
            isError = state.codeRejected,
            supportingText =
                if (state.codeRejected) {
                    { Text(rejected, Modifier.semantics { liveRegion = LiveRegionMode.Assertive }) }
                } else {
                    null
                },
            keyboardOptions =
                KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters,
                    autoCorrectEnabled = false,
                    keyboardType = KeyboardType.Ascii,
                    imeAction = ImeAction.Done,
                ),
            keyboardActions = KeyboardActions(onDone = { pair() }),
            trailingIcon = {
                IconButton(
                    onClick = {
                        scope.launch {
                            val clip = clipboard.getClipEntry()?.clipData
                            val text = clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(context)
                            if (text != null) edit(text.toString())
                        }
                    },
                ) {
                    Icon(
                        painterResource(R.drawable.ic_content_paste),
                        contentDescription = stringResource(R.string.camera_role_paste),
                    )
                }
            },
        )
        Button(onClick = pair) { Text(stringResource(R.string.camera_role_pair)) }
    }
}

@Composable
private fun PairedBlock(
    onUnpair: () -> Unit,
    holdAwake: (Boolean) -> Unit,
    headingFocus: FocusRequester,
) {
    var confirming by rememberSaveable { mutableStateOf(false) }
    // The dialog is a window of its own, so touches in it never reach the screen's idle timer.
    DisposableEffect(confirming) {
        if (confirming) holdAwake(true)
        onDispose { if (confirming) holdAwake(false) }
    }
    Text(
        stringResource(R.string.camera_role_fit),
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.focusRequester(headingFocus).focusable().semantics { heading() },
    )
    Text(
        stringResource(R.string.camera_role_charger),
        style = MaterialTheme.typography.bodyMedium,
        modifier = Modifier.padding(top = Spacing.hair),
    )
    TextButton(
        onClick = { confirming = true },
        colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
        modifier = Modifier.padding(top = Spacing.tight),
    ) {
        Text(stringResource(R.string.camera_role_unpair))
    }
    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.camera_role_unpair_title)) },
            text = { Text(stringResource(R.string.camera_role_unpair_body)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirming = false
                        onUnpair()
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) {
                    Text(stringResource(R.string.camera_role_unpair))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }
}

/** Only the status line, moving between slots so an OLED panel does not burn in; a touch wakes it. */
@Composable
private fun Dimmed(
    link: CameraLinkState,
    slot: DimSlot,
    onWake: () -> Unit,
) {
    val interactions = remember { MutableInteractionSource() }
    val focused by interactions.collectIsFocusedAsState()
    val outline = MaterialTheme.colorScheme.primary
    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.scrim)
                .clickable(
                    interactionSource = interactions,
                    indication = null,
                    onClickLabel = stringResource(R.string.camera_role_show_preview),
                    role = Role.Button,
                    onClick = onWake,
                ).windowInsetsPadding(WindowInsets.safeDrawing)
                .then(if (focused) Modifier.border(FOCUS_OUTLINE, outline) else Modifier)
                .padding(Spacing.base),
    ) {
        Text(
            stringResource(link.label()),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier =
                Modifier
                    .align(BiasAlignment(slot.horizontalBias, slot.verticalBias))
                    .semantics { liveRegion = LiveRegionMode.Polite },
        )
    }
}

/** A 180° turn changes the display's rotation without a configuration change, so nothing recomposes. */
@Composable
private fun DisplayRotation(onRotation: (Int) -> Unit) {
    val view = LocalView.current
    val current by rememberUpdatedState(onRotation)
    DisposableEffect(view) {
        val displays = view.context.getSystemService(DisplayManager::class.java)
        val listener =
            object : DisplayManager.DisplayListener {
                override fun onDisplayChanged(displayId: Int) {
                    val display = view.display ?: return
                    if (display.displayId == displayId) current(display.rotation)
                }

                override fun onDisplayAdded(displayId: Int) = Unit

                override fun onDisplayRemoved(displayId: Int) = Unit
            }
        displays.registerDisplayListener(listener, Handler(Looper.getMainLooper()))
        onDispose { displays.unregisterDisplayListener(listener) }
    }
}

/**
 * TalkBack, switch access and the like act without raw touches, so the idle timer also counts the
 * accessibility events they cause, which bubble up through the Compose view's parent.
 */
@Composable
private fun AssistiveActivity(onActivity: () -> Unit) {
    val view = LocalView.current
    val current by rememberUpdatedState(onActivity)
    DisposableEffect(view) {
        val parent = view.parent as? ViewGroup
        parent?.setAccessibilityDelegate(
            object : View.AccessibilityDelegate() {
                override fun onRequestSendAccessibilityEvent(
                    host: ViewGroup,
                    child: View,
                    event: AccessibilityEvent,
                ): Boolean {
                    if (event.eventType and USER_ACCESSIBILITY_EVENTS != 0) current()
                    return super.onRequestSendAccessibilityEvent(host, child, event)
                }
            },
        )
        onDispose { parent?.setAccessibilityDelegate(null) }
    }
}

private const val USER_ACCESSIBILITY_EVENTS =
    AccessibilityEvent.TYPE_VIEW_CLICKED or
        AccessibilityEvent.TYPE_VIEW_LONG_CLICKED or
        AccessibilityEvent.TYPE_VIEW_FOCUSED or
        AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED or
        AccessibilityEvent.TYPE_VIEW_HOVER_ENTER or
        AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED or
        AccessibilityEvent.TYPE_VIEW_SCROLLED

@Composable
private fun KeepScreenOn() {
    val activity = LocalActivity.current ?: return
    DisposableEffect(activity) {
        activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        onDispose { activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
    }
}

/** The window's half of dimming: its lowest brightness and no system bars (ADR-0009, decision 10). */
@Composable
private fun DimmedWindow(dimmed: Boolean) {
    val activity = LocalActivity.current ?: return
    val view = LocalView.current
    DisposableEffect(activity, view, dimmed) {
        val window = activity.window
        val bars = WindowCompat.getInsetsController(window, view)
        if (dimmed) {
            window.attributes =
                window.attributes.apply { screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_OFF }
            bars.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            bars.hide(WindowInsetsCompat.Type.systemBars())
        }
        onDispose {
            if (dimmed) {
                window.attributes =
                    window.attributes.apply { screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE }
                bars.show(WindowInsetsCompat.Type.systemBars())
            }
        }
    }
}
