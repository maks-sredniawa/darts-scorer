package app.dartsscorer.ui.visit

import android.animation.ValueAnimator
import android.os.SystemClock
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.lerp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.InputMode
import androidx.compose.ui.input.pointer.AwaitPointerEventScope
import androidx.compose.ui.input.pointer.PointerInputChange
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalInputModeManager
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.toSize
import app.dartsscorer.R
import app.dartsscorer.scoring.Point
import app.dartsscorer.scoring.Score
import app.dartsscorer.theme.Spacing
import coil3.compose.AsyncImage
import coil3.compose.LocalPlatformContext
import coil3.compose.rememberAsyncImagePainter
import coil3.request.ImageRequest
import kotlinx.coroutines.delay
import java.io.File
import kotlin.math.PI
import kotlin.math.roundToInt
import coil3.size.Size as CoilSize

/**
 * Takes focus once per [arrival], so TalkBack lands on it rather than where it last was. A result
 * arrives while the Picker or the camera still has the window, and TalkBack puts its own focus on the
 * first node once the window is back, so the request waits for both.
 */
@Composable
internal fun Modifier.focusOnArrival(arrival: Any): Modifier {
    val focus = remember { FocusRequester() }
    var placed by remember(arrival) { mutableStateOf(false) }
    val windowFocused = LocalWindowInfo.current.isWindowFocused
    LaunchedEffect(arrival, windowFocused) {
        if (windowFocused && !placed) {
            delay(WINDOW_SETTLE_MS)
            placed = focus.requestFocus()
        }
    }
    return focusRequester(focus).focusableWithRing()
}

@Composable
internal fun Modifier.focusableWithRing(): Modifier {
    val interactions = remember { MutableInteractionSource() }
    val focused by interactions.collectIsFocusedAsState()
    val keyboard = LocalInputModeManager.current.inputMode == InputMode.Keyboard
    val ring =
        if (focused && keyboard) {
            Modifier.border(FOCUS_RING, MaterialTheme.colorScheme.onSurface, MaterialTheme.shapes.medium)
        } else {
            Modifier
        }
    return focusable(interactionSource = interactions).then(ring)
}

@Composable
internal fun Modifier.takesFocusWhen(
    requested: Boolean,
    onPlaced: () -> Unit,
): Modifier {
    val focus = remember { FocusRequester() }
    val windowFocused = LocalWindowInfo.current.isWindowFocused
    LaunchedEffect(requested, windowFocused) {
        if (requested && windowFocused) {
            delay(WINDOW_SETTLE_MS)
            focus.requestFocus()
            onPlaced()
        }
    }
    return focusRequester(focus).focusableInTouchMode()
}

/**
 * A button is focusable only outside touch mode, so focus could not be moved back to it after the
 * sheet closes, and TalkBack follows that focus (phase-1.md §3, *Focus*).
 */
internal fun Modifier.focusableInTouchMode(): Modifier = focusProperties { canFocus = true }

private val FOCUS_RING = 3.dp

internal const val WINDOW_SETTLE_MS = 600L

private const val MARKER_MAX_FONT_SCALE = 1.3f

private val HAIRLINE = 1.dp

private val RING_DARK = 1.5.dp

private val RING_DASH = 4.dp

private val RING_GAP = 3.dp

internal val TOUCH_TARGET = 48.dp

private const val GHOST_ALPHA = 0.45f

private val LIFT = TOUCH_TARGET * 1.5f

private const val LIFT_MS = 120L

private const val FRAME_MS = 16L

/**
 * Above the Score: at most two fifths of the window high, so the Score and the chips sit under the
 * Photo rather than below the fold. [beside] the Score, on a short window: the full height, at most
 * half the window wide.
 */
@Composable
private fun Modifier.photoSize(
    aspect: Double,
    beside: Boolean,
): Modifier {
    val window = LocalWindowInfo.current.containerSize
    return with(LocalDensity.current) {
        if (beside) {
            widthIn(max = (window.width / 2).toDp()).fillMaxHeight().aspectRatio(aspect.toFloat(), true)
        } else {
            heightIn(max = (window.height * 2 / 5).toDp()).aspectRatio(aspect.toFloat())
        }
    }
}

/** A banner for what came back wrong: a shape and a title as well as its colour. */
@Composable
internal fun NoticeBanner(
    title: String,
    body: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        shape = MaterialTheme.shapes.medium,
        modifier =
            modifier
                .fillMaxWidth()
                .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
    ) {
        Row(modifier = Modifier.padding(Spacing.base), horizontalArrangement = Arrangement.spacedBy(Spacing.snug)) {
            Icon(Icons.Filled.Warning, contentDescription = null)
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.hair)) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                Text(text = body, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
internal fun NoBoardBanner(result: VisitPhase.NoBoard) {
    NoticeBanner(
        title = stringResource(R.string.visit_no_board_title),
        body = stringResource(R.string.visit_no_board_hint),
        modifier = Modifier.padding(bottom = Spacing.base).focusOnArrival(result),
    )
}

/** The whole Photo, with no markers: no Board was found on it. */
@Composable
internal fun WholePhoto(
    photo: File,
    width: Int,
    height: Int,
    beside: Boolean,
    modifier: Modifier = Modifier,
) {
    AsyncImage(
        model = photo,
        contentDescription = null,
        contentScale = ContentScale.Fit,
        modifier = modifier.photoSize(width.toDouble() / height, beside),
    )
}

/**
 * The Score heading, the *Check* lines, a chip per Dart and *Add a Dart*. The heading takes focus
 * when a new result arrives; [focus] moves it to a chip or *Add a Dart* once the sheet has closed.
 */
@Composable
internal fun ShownDetails(
    shown: VisitPhase.Shown,
    focus: VisitFocus?,
    onOpenDart: (Int) -> Unit,
    onRemoveDart: (Int) -> Unit,
    onAddDart: () -> Unit,
    onFocusPlaced: () -> Unit,
) {
    val resources = LocalResources.current
    val chips = remember { mutableMapOf<Int, FocusRequester>() }
    val addDart = remember { FocusRequester() }
    val windowFocused = LocalWindowInfo.current.isWindowFocused
    LaunchedEffect(focus, windowFocused) {
        if (focus != null && windowFocused) {
            delay(WINDOW_SETTLE_MS)
            val target =
                when (focus) {
                    is VisitFocus.Chip -> chips[focus.number]
                    VisitFocus.AddDart -> addDart.takeIf { Correction.canAdd(shown.darts) }
                    VisitFocus.EnterScore -> null
                }
            target?.requestFocus()
            onFocusPlaced()
        }
    }

    val heading =
        Modifier.semantics(mergeDescendants = true) {
            heading()
            liveRegion = LiveRegionMode.Polite
            contentDescription = resources.summary(shown)
        }
    Column(
        modifier =
            if (shown is VisitPhase.Scored) heading.focusOnArrival(shown.photo) else heading.focusableWithRing(),
    ) {
        Text(
            text = stringResource(R.string.visit_score_label),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = shown.darts.total.toString(), style = MaterialTheme.typography.displayLarge)
    }
    if (shown is VisitPhase.Entered) {
        Text(
            text = stringResource(R.string.visit_entered_by_hand),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    shown.darts.filter { it.unsure }.forEach { dart ->
        Text(
            text = stringResource(R.string.visit_check_dart, dart.number),
            style = MaterialTheme.typography.bodyLarge,
        )
    }
    if (shown is VisitPhase.Scored && shown.darts.all { it.filled }) {
        Text(
            text = stringResource(R.string.visit_no_darts),
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
        )
    }
    FlowRow(
        modifier = Modifier.padding(top = Spacing.base),
        horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
        verticalArrangement = Arrangement.spacedBy(Spacing.tight),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        shown.darts.forEach { dart ->
            DartChip(
                dart,
                onOpen = { onOpenDart(dart.number) },
                onRemove = { onRemoveDart(dart.number) },
                modifier =
                    Modifier
                        .focusRequester(
                            chips.getOrPut(dart.number) { FocusRequester() },
                        ).focusableInTouchMode(),
            )
        }
        if (Correction.canAdd(shown.darts)) {
            AddDartButton(onAddDart, Modifier.focusRequester(addDart).focusableInTouchMode())
        }
    }
}

/**
 * Filled when sure, outlined with *Check* when unsure: shape and text, never colour alone. A button
 * that opens the keypad, with *Remove Dart* as TalkBack's custom action.
 */
@Composable
private fun DartChip(
    dart: ShownDart,
    onOpen: () -> Unit,
    onRemove: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val resources = LocalResources.current
    val description = resources.chipDescription(dart)
    val removeLabel = stringResource(R.string.visit_remove_dart)
    Surface(
        onClick = onOpen,
        shape = MaterialTheme.shapes.small,
        color = if (dart.unsure) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.secondaryContainer,
        border = if (dart.unsure) BorderStroke(1.dp, MaterialTheme.colorScheme.outline) else null,
        modifier =
            modifier.semantics(mergeDescendants = true) {
                role = Role.Button
                contentDescription = description
                customActions = listOf(CustomAccessibilityAction(removeLabel) { onRemove().let { true } })
            },
    ) {
        Row(
            modifier = Modifier.padding(horizontal = Spacing.snug, vertical = Spacing.tight),
            horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = resources.chipText(dart), style = MaterialTheme.typography.labelLarge)
            if (dart.unsure) {
                Text(
                    text = stringResource(R.string.visit_chip_check),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

/** No container, so it reads as an action beside the Darts' chips rather than as a Dart. */
@Composable
private fun AddDartButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    TextButton(onClick = onClick, modifier = modifier.heightIn(min = TOUCH_TARGET)) {
        Icon(Icons.Filled.Add, contentDescription = null)
        Text(stringResource(R.string.visit_add_dart), modifier = Modifier.padding(start = Spacing.tight))
    }
}

/**
 * The Photo cropped to the Board, one node for TalkBack; its markers are not focusable, since the
 * chips are the path that needs no precise tap. A tap on a marker opens its Dart, a tap elsewhere
 * proposes a new Dart while fewer than three are shown, and a long press on a marker drags its ring
 * onto the Entry point.
 */
@Composable
internal fun BoardPhoto(
    result: VisitPhase.Scored,
    onOpenDart: (Int) -> Unit,
    onSpot: (Point) -> Unit,
    onMoveDart: (Int, Point, Boolean) -> Unit,
    beside: Boolean,
    modifier: Modifier = Modifier,
) {
    val resources = LocalResources.current
    val description = resources.summary(result)
    val painter =
        rememberAsyncImagePainter(
            ImageRequest
                .Builder(LocalPlatformContext.current)
                .data(result.photo)
                .size(CoilSize.ORIGINAL)
                .build(),
        )
    val measurer = rememberTextMeasurer()
    val numberStyle = MaterialTheme.typography.labelMedium
    val colors = MaterialTheme.colorScheme
    val crop = result.crop
    val latest by rememberUpdatedState(result)
    var zoom by remember(result.photo) { mutableStateOf(PhotoZoom()) }
    var box by remember { mutableStateOf(Size.Zero) }
    val zoomed by remember(result.photo) { derivedStateOf { zoom.zoom > PhotoZoom.MIN_ZOOM } }
    val zoomable by remember(result.photo) { derivedStateOf { zoom.zoom < PhotoZoom.MAX_ZOOM } }
    val actions = photoActions(zoomable, zoomed) { zoom = it(zoom, box) }
    var dragging by remember(result.photo) { mutableStateOf<Int?>(null) }
    var lifted by remember(result.photo) { mutableStateOf<Offset?>(null) }
    val liftMillis = remember { if (ValueAnimator.areAnimatorsEnabled()) LIFT_MS else 0L }
    val scoreLabel: (Score) -> String = { resources.shortName(it) }
    val density = LocalDensity.current
    val haptics = LocalHapticFeedback.current
    val move by rememberUpdatedState(onMoveDart)
    val ring =
        remember(result.photo, density, measurer, numberStyle) {
            object : RingDrag {
                var onRead = false

                override fun hit(at: Offset): Int? {
                    val markers = shownMarkers()
                    return markers.map { it.spot }.hitBy(at, with(density) { TOUCH_TARGET.toPx() } / 2)?.let {
                        markers[it].dart.number
                    }
                }

                override fun bounds(): Rect {
                    val shown = latest
                    val view = zoom.clampedTo(box)
                    val scale = box.width / shown.crop.width
                    val toPhoto = shown.toBoard.inverse()
                    val rim = BOARD_RIM.map { view.toScreen(toPhoto.project(it).screen(shown.crop, scale)) }
                    val rimBox = Rect(rim.minOf { it.x }, rim.minOf { it.y }, rim.maxOf { it.x }, rim.maxOf { it.y })
                    return insideRim(Rect(Offset.Zero, box), rimBox, density.ringOuter())
                }

                override fun ringAt(dart: Int): Offset? =
                    shownMarkers().firstOrNull { it.dart.number == dart }?.spot?.at

                private fun shownMarkers() =
                    density.markers(latest, box, zoom.clampedTo(box), measurer, numberStyle, null, scoreLabel)

                override fun hold(dart: Int) {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    onRead = false
                    dragging = dart
                }

                override fun lift(ringAt: Offset) {
                    lifted = ringAt
                }

                override fun drag(
                    dart: Int,
                    ringAt: Offset,
                ) {
                    lifted = null
                    val shown = latest
                    val crop = shown.crop
                    val view = zoom.clampedTo(box)
                    val scale = box.width / crop.width
                    val base = view.toBase(ringAt)
                    val point =
                        Point(
                            (crop.left + base.x / scale).coerceIn(crop.left, crop.right),
                            (crop.top + base.y / scale).coerceIn(crop.top, crop.bottom),
                        )
                    val held = shown.darts.firstOrNull { it.number == dart } ?: return
                    val screen = view.toScreen(point.screen(crop, scale))
                    val nearRead =
                        held.read?.let {
                            (screen - view.toScreen(it.at.screen(crop, scale))).getDistance() <= density.ringOuter()
                        } == true
                    val snaps = Correction.snapsBack(held, point, shown.toBoard, nearRead)
                    if (snaps && !onRead) haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                    move(dart, point, nearRead)
                    onRead = snaps
                }

                override fun release() {
                    dragging = null
                    lifted = null
                }
            }
        }
    Canvas(
        modifier =
            modifier
                .photoSize(crop.width / crop.height, beside)
                .clipToBounds()
                .onSizeChanged { box = it.toSize() }
                .pointerInput(measurer, numberStyle, result.photo) {
                    detectTapGestures(onDoubleTap = { at -> zoom = zoom.toggled(at, size.toSize()) }) { tap ->
                        val shown = latest
                        val view = zoom.clampedTo(size.toSize())
                        val markers = markers(shown, size.toSize(), view, measurer, numberStyle, null, scoreLabel)
                        val hit = markers.map { it.spot }.hitBy(tap, TOUCH_TARGET.toPx() / 2)
                        if (hit != null) {
                            onOpenDart(markers[hit].dart.number)
                        } else {
                            val scale = size.width / shown.crop.width
                            val base = view.toBase(tap)
                            onSpot(Point(shown.crop.left + base.x / scale, shown.crop.top + base.y / scale))
                        }
                    }
                }.zoomGestures(result.photo, { zoom }, { zoom = it }, ring, liftMillis)
                .semantics {
                    contentDescription = description
                    role = Role.Image
                    customActions = actions
                },
    ) {
        val view = zoom.clampedTo(size)
        val scale = (size.width / crop.width).toFloat()
        withTransform({
            translate(view.pan.x, view.pan.y)
            scale(view.zoom * scale, view.zoom * scale, pivot = Offset.Zero)
            translate(-crop.left.toFloat(), -crop.top.toFloat())
        }) {
            with(painter) { draw(Size(result.width.toFloat(), result.height.toFloat())) }
        }
        val scaled = scale.toDouble()
        result.darts
            .firstOrNull { it.number == dragging }
            ?.read
            ?.let { read -> view.toScreen(read.at.screen(crop, scaled)) to read.unsure }
            ?.let { (at, unsure) -> drawRing(at, unsure, colors, GHOST_ALPHA) }
        markers(
            result,
            size,
            view,
            measurer,
            numberStyle,
            dragging,
            scoreLabel,
            lifted,
        ).forEach { drawMarker(it, colors) }
    }
}

/** A marker's ring held and dragged; [lift] and [drag]'s point is where the ring is drawn. */
private interface RingDrag {
    fun hit(at: Offset): Int?

    fun ringAt(dart: Int): Offset?

    /** Where a held ring's centre may go: the Photo, inset by up to a ring's radius but never past the Board's rim. */
    fun bounds(): Rect

    fun hold(dart: Int)

    /** Before the finger has moved past touch slop: the ring is drawn there, and the Dart is not moved. */
    fun lift(ringAt: Offset)

    fun drag(
        dart: Int,
        ringAt: Offset,
    )

    fun release()
}

/**
 * Pinch, and a one-finger drag once zoomed in. A drag is consumed only while it moves the Photo, so
 * at 1× or at a pan edge it falls through to the scroll around the Photo; a consumed move also
 * cancels the tap, so a pan never adds a Dart. A finger held still on a marker for a long press
 * takes the gesture instead and drags its [ring].
 */
private fun Modifier.zoomGestures(
    photo: File,
    current: () -> PhotoZoom,
    onZoom: (PhotoZoom) -> Unit,
    ring: RingDrag,
    liftMillis: Long,
): Modifier =
    pointerInput(photo) {
        awaitEachGesture {
            val down = awaitFirstDown(requireUnconsumed = false)
            val held = ring.hit(down.position)
            val longPressAt = down.uptimeMillis + viewConfiguration.longPressTimeoutMillis
            var last = down.uptimeMillis
            var travel = 0f
            do {
                val waiting = held != null && travel <= viewConfiguration.touchSlop
                val event =
                    if (waiting) {
                        withTimeoutOrNull(maxOf(longPressAt - last, 0L)) { awaitPointerEvent() }
                    } else {
                        awaitPointerEvent()
                    }
                if (event == null) {
                    held?.let { dragRing(down, it, ring, Offset(0f, -LIFT.toPx()), liftMillis) }
                    return@awaitEachGesture
                }
                last = event.changes.first().uptimeMillis
                val box = size.toSize()
                val now = current().clampedTo(box)
                val move = event.calculatePan()
                val next =
                    if (event.changes.count { it.pressed } >= 2) {
                        travel = Float.POSITIVE_INFINITY
                        event.changes.forEach { it.consume() }
                        now.zoomedAbout(event.calculateCentroid(), event.calculateZoom(), box).panned(move, box)
                    } else {
                        travel += move.getDistance()
                        if (travel > viewConfiguration.touchSlop) now.panned(move, box) else now
                    }
                if (next != now) {
                    onZoom(next)
                    event.changes.forEach { it.consume() }
                }
            } while (event.changes.any { it.pressed })
        }
    }

/** Every change is consumed, the lift included, so the hold is neither a tap, a pan nor a scroll. */
private suspend fun AwaitPointerEventScope.dragRing(
    down: PointerInputChange,
    dart: Int,
    ring: RingDrag,
    lift: Offset,
    liftMillis: Long,
) {
    val grab = (ring.ringAt(dart) ?: down.position) - down.position
    ring.hold(dart)
    val held = SystemClock.uptimeMillis()
    var finger = down.position
    var travel = 0f

    fun offsetNow() = liftOffset(grab, lift, SystemClock.uptimeMillis() - held, liftMillis)

    fun place(offset: Offset) {
        val at = keptInside(finger + offset, ring.bounds())
        if (travel > viewConfiguration.touchSlop) ring.drag(dart, at) else ring.lift(at)
    }
    try {
        while (true) {
            val offset = offsetNow()
            place(offset)
            val rising = offset != lift
            val event =
                (if (rising) withTimeoutOrNull(FRAME_MS) { awaitPointerEvent() } else awaitPointerEvent()) ?: continue
            event.changes.forEach { it.consume() }
            val change = event.changes.firstOrNull { it.id == down.id } ?: break
            finger = change.position
            travel = maxOf(travel, (finger - down.position).getDistance())
            if (!change.pressed) {
                place(offsetNow())
                break
            }
        }
    } finally {
        ring.release()
    }
}

internal fun insideRim(
    box: Rect,
    rim: Rect,
    inset: Float,
): Rect {
    fun gap(distance: Float) = distance.coerceIn(0f, inset)
    return Rect(
        box.left + gap(rim.left - box.left),
        box.top + gap(rim.top - box.top),
        box.right - gap(box.right - rim.right),
        box.bottom - gap(box.bottom - rim.bottom),
    )
}

internal fun keptInside(
    at: Offset,
    bounds: Rect,
): Offset = Offset(at.x.coerceIn(bounds.left, bounds.right), at.y.coerceIn(bounds.top, bounds.bottom))

internal fun liftOffset(
    grab: Offset,
    lift: Offset,
    elapsedMillis: Long,
    liftMillis: Long,
): Offset = if (elapsedMillis >= liftMillis) lift else lerp(grab, lift, elapsedMillis.toFloat() / liftMillis)

@Composable
private fun photoActions(
    zoomable: Boolean,
    zoomed: Boolean,
    onChange: ((PhotoZoom, Size) -> PhotoZoom) -> Unit,
): List<CustomAccessibilityAction> {
    fun action(
        label: String,
        change: (PhotoZoom, Size) -> PhotoZoom,
    ) = CustomAccessibilityAction(label) {
        onChange(change)
        true
    }

    fun move(
        label: String,
        direction: Offset,
    ) = action(label) { zoom, box -> zoom.viewMoved(direction, box) }
    return buildList {
        if (zoomable) {
            add(
                action(stringResource(R.string.visit_photo_zoom_in)) { zoom, box -> zoom.zoomStepped(true, box) },
            )
        }
        if (zoomed) {
            add(action(stringResource(R.string.visit_photo_zoom_out)) { zoom, box -> zoom.zoomStepped(false, box) })
            add(move(stringResource(R.string.visit_photo_move_left), Offset(-1f, 0f)))
            add(move(stringResource(R.string.visit_photo_move_right), Offset(1f, 0f)))
            add(move(stringResource(R.string.visit_photo_move_up), Offset(0f, -1f)))
            add(move(stringResource(R.string.visit_photo_move_down), Offset(0f, 1f)))
        }
    }
}

private fun Point.screen(
    crop: Crop,
    scale: Double,
): Offset = Offset(((x - crop.left) * scale).toFloat(), ((y - crop.top) * scale).toFloat())

private class Marker(
    val dart: ShownDart,
    val text: TextLayoutResult,
    val spot: MarkerSpot,
    val dragging: Boolean,
)

private fun Density.ringOuter(): Float = Spacing.tight.toPx() + 2 * HAIRLINE.toPx() + RING_DARK.toPx()

private fun Density.markers(
    shown: VisitPhase.Scored,
    canvas: Size,
    zoom: PhotoZoom,
    measurer: TextMeasurer,
    style: TextStyle,
    dragging: Int?,
    scoreLabel: (Score) -> String,
    lifted: Offset? = null,
): List<Marker> {
    val markerDensity = Density(density, fontScale.coerceAtMost(MARKER_MAX_FONT_SCALE))
    val scale = canvas.width / shown.crop.width
    val keyline = HAIRLINE.toPx()
    val ringOuter = ringOuter()
    val box = Rect(Offset.Zero, canvas)
    return shown.darts.mapNotNull { dart ->
        val held = dart.number == dragging
        val at =
            (if (held) lifted else null)
                ?: dart.at?.let { zoom.toScreen(it.screen(shown.crop, scale)) }
                ?: return@mapNotNull null
        if (!held && !box.contains(at)) return@mapNotNull null
        val label =
            when {
                held -> scoreLabel(dart.score)
                dart.unsure && !dart.corrected -> "${dart.number}?"
                else -> dart.number.toString()
            }
        val text = measurer.measure(label, style, density = markerDensity)
        val height = text.size.height.toFloat()
        val outer = Size(maxOf(height, text.size.width + 2 * Spacing.hair.toPx()) + 2 * keyline, height + 2 * keyline)
        val badge =
            if (dart.badgeAlone && !held) badgeOn(at, outer, canvas) else badgeBeside(at, outer, ringOuter, canvas)
        Marker(dart, text, MarkerSpot(at, badge), held)
    }
}

private val ShownDart.badgeAlone: Boolean get() = corrected && !moved

/** Drawn as `docs/phase-1.md` §3 describes it, and a corrected one as §4's *The corrected marker*. */
private fun DrawScope.drawMarker(
    marker: Marker,
    colors: ColorScheme,
) {
    val dart = marker.dart
    val at = marker.spot.at
    when {
        marker.dragging || dart.moved -> {
            drawRing(at, false, colors)
            if (marker.dragging) drawCrosshair(at, colors)
            drawBadge(marker, colors.inverseSurface, colors.inverseOnSurface, colors.surfaceContainerLowest)
        }
        dart.corrected ->
            drawBadge(
                marker,
                colors.inverseSurface,
                colors.inverseOnSurface,
                colors.surfaceContainerLowest,
            )
        dart.unsure -> {
            drawRing(at, true, colors)
            drawBadge(marker, colors.tertiaryContainer, colors.onTertiaryContainer, colors.inverseSurface)
        }
        else -> {
            drawRing(at, false, colors)
            drawBadge(marker, colors.surfaceContainerLowest, colors.onSurface, colors.inverseSurface)
        }
    }
}

private fun DrawScope.drawRing(
    at: Offset,
    dashed: Boolean,
    colors: ColorScheme,
    alpha: Float = 1f,
) {
    val light = HAIRLINE.toPx()
    val dark = RING_DARK.toPx()
    val middle = Spacing.tight.toPx() + light + dark / 2
    val dashes = if (dashed) wholeDashes(middle) else null
    drawCircle(
        colors.surfaceContainerLowest,
        middle,
        at,
        alpha,
        style = Stroke(width = 2 * light + dark, pathEffect = dashes),
    )
    drawCircle(colors.inverseSurface, middle, at, alpha, style = Stroke(width = dark, pathEffect = dashes))
}

/** Keylines first, so no arm's keyline cuts another's ink. */
private fun DrawScope.drawCrosshair(
    at: Offset,
    colors: ColorScheme,
) {
    val ink = RING_DARK.toPx()
    val outer = ringOuter()
    val strokes =
        listOf(Offset(1f, 0f), Offset(-1f, 0f), Offset(0f, 1f), Offset(0f, -1f)).flatMap { arm ->
            listOf(
                at + arm * outer to at + arm * (outer + Spacing.section.toPx()),
                at + arm * Spacing.hair.toPx() to at + arm * Spacing.tight.toPx(),
            )
        }
    strokes.forEach { (from, to) -> drawLine(colors.surfaceContainerLowest, from, to, ink + 2 * HAIRLINE.toPx()) }
    strokes.forEach { (from, to) -> drawLine(colors.inverseSurface, from, to, ink) }
}

/** Stretched to a whole number of dashes, so no short one is left where the circle closes. */
private fun DrawScope.wholeDashes(radius: Float): PathEffect {
    val period = (RING_DASH + RING_GAP).toPx()
    val circumference = 2 * PI.toFloat() * radius
    val stretch = circumference / ((circumference / period).roundToInt() * period)
    return PathEffect.dashPathEffect(floatArrayOf(RING_DASH.toPx() * stretch, RING_GAP.toPx() * stretch))
}

private fun DrawScope.drawBadge(
    marker: Marker,
    fill: Color,
    ink: Color,
    keyline: Color,
) {
    val outer = marker.spot.badge
    val badge = outer.deflate(HAIRLINE.toPx())
    drawRoundRect(keyline, topLeft = outer.topLeft, size = outer.size, cornerRadius = CornerRadius(outer.height / 2))
    drawRoundRect(fill, topLeft = badge.topLeft, size = badge.size, cornerRadius = CornerRadius(badge.height / 2))
    val text = marker.text.size
    drawText(marker.text, ink, topLeft = outer.center - Offset(text.width / 2f, text.height / 2f))
}
