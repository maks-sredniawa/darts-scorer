package app.dartsscorer.ui.visit

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
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
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.InputMode
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
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
import app.dartsscorer.R
import app.dartsscorer.scoring.Point
import app.dartsscorer.theme.Spacing
import coil3.compose.AsyncImage
import coil3.compose.LocalPlatformContext
import coil3.compose.rememberAsyncImagePainter
import coil3.request.ImageRequest
import kotlinx.coroutines.delay
import java.io.File
import kotlin.math.PI
import kotlin.math.roundToInt
import kotlin.math.sqrt
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
    if (shown is VisitPhase.Scored && shown.darts.isEmpty()) {
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
 * proposes a new Dart while fewer than three are shown.
 */
@Composable
internal fun BoardPhoto(
    result: VisitPhase.Scored,
    onOpenDart: (Int) -> Unit,
    onSpot: (Point) -> Unit,
    beside: Boolean,
    modifier: Modifier = Modifier,
) {
    val description = LocalResources.current.summary(result)
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
    Canvas(
        modifier =
            modifier
                .photoSize(crop.width / crop.height, beside)
                .clipToBounds()
                .pointerInput(Unit) {
                    detectTapGestures { tap ->
                        val shown = latest
                        val scale = size.width / shown.crop.width
                        val hit = TOUCH_TARGET.toPx() / 2
                        val nearest =
                            shown.darts
                                .mapNotNull { dart ->
                                    dart.at?.let {
                                        dart to
                                            (it.screen(shown.crop, scale) - tap).getDistance()
                                    }
                                }.minByOrNull { it.second }
                                ?.takeIf { it.second <= hit }
                        if (nearest != null) {
                            onOpenDart(nearest.first.number)
                        } else {
                            onSpot(Point(shown.crop.left + tap.x / scale, shown.crop.top + tap.y / scale))
                        }
                    }
                }.semantics {
                    contentDescription = description
                    role = Role.Image
                },
    ) {
        val scale = (size.width / crop.width).toFloat()
        withTransform({
            scale(scale, scale, pivot = Offset.Zero)
            translate(-crop.left.toFloat(), -crop.top.toFloat())
        }) {
            with(painter) { draw(Size(result.width.toFloat(), result.height.toFloat())) }
        }
        result.darts.forEach { dart ->
            val at = dart.at ?: return@forEach
            drawMarker(at.screen(crop, scale.toDouble()), dart, measurer, numberStyle, colors)
        }
    }
}

private fun Point.screen(
    crop: Crop,
    scale: Double,
): Offset = Offset(((x - crop.left) * scale).toFloat(), ((y - crop.top) * scale).toFloat())

/**
 * A thin ring with its centre left clear, so the dart tip shows through, and the number in a badge
 * beside it. Light, dark and light bands, so it reads on a dark Board and a light wall. Unsure: the
 * ring dashed and the badge *n?*. Corrected: no ring, only the badge on its place, since the player
 * set the Score: drawn at its bed's centre, or for a Miss where it was or was tapped, so it hides no
 * tip.
 */
private fun DrawScope.drawMarker(
    at: Offset,
    dart: ShownDart,
    measurer: TextMeasurer,
    style: TextStyle,
    colors: ColorScheme,
) {
    val markerDensity = Density(density, fontScale.coerceAtMost(MARKER_MAX_FONT_SCALE))
    val (fill, ink) =
        when {
            dart.corrected -> colors.inverseSurface to colors.inverseOnSurface
            dart.unsure -> colors.tertiaryContainer to colors.onTertiaryContainer
            else -> colors.surfaceContainerLowest to colors.onSurface
        }
    val label = if (dart.unsure && !dart.corrected) "${dart.number}?" else dart.number.toString()
    val text = measurer.measure(label, style.copy(color = ink), density = markerDensity)
    if (dart.corrected) {
        drawBadge(text, inside(at, text), fill, colors.surfaceContainerLowest)
        return
    }
    drawRing(at, dart.unsure, colors)
    drawBadge(text, besideRing(at, text), fill, colors.inverseSurface)
}

private fun DrawScope.drawRing(
    at: Offset,
    dashed: Boolean,
    colors: ColorScheme,
) {
    val light = HAIRLINE.toPx()
    val dark = RING_DARK.toPx()
    val middle = Spacing.tight.toPx() + light + dark / 2
    val dashes = if (dashed) wholeDashes(middle) else null
    drawCircle(colors.surfaceContainerLowest, middle, at, style = Stroke(width = 2 * light + dark, pathEffect = dashes))
    drawCircle(colors.inverseSurface, middle, at, style = Stroke(width = dark, pathEffect = dashes))
}

/** Stretched to a whole number of dashes, so no short one is left where the circle closes. */
private fun DrawScope.wholeDashes(radius: Float): PathEffect {
    val period = (RING_DASH + RING_GAP).toPx()
    val circumference = 2 * PI.toFloat() * radius
    val stretch = circumference / ((circumference / period).roundToInt() * period)
    return PathEffect.dashPathEffect(floatArrayOf(RING_DASH.toPx() * stretch, RING_GAP.toPx() * stretch))
}

private fun DrawScope.ringOuter(): Float = Spacing.tight.toPx() + 2 * HAIRLINE.toPx() + RING_DARK.toPx()

private fun DrawScope.badgeSize(text: TextLayoutResult): Size {
    val height = text.size.height.toFloat()
    return Size(maxOf(height, text.size.width + 2 * Spacing.hair.toPx()), height)
}

/**
 * The badge's rounded end touches the ring at 45° up and to the right, flipped to whichever side
 * stays inside the crop.
 */
private fun DrawScope.besideRing(
    at: Offset,
    text: TextLayoutResult,
): Offset {
    val keyline = HAIRLINE.toPx()
    val badge = badgeSize(text)
    val halfWidth = badge.width / 2 + keyline
    val halfHeight = badge.height / 2 + keyline
    val reach = (ringOuter() + halfHeight) / sqrt(2f)
    val toCentre = reach + halfWidth - halfHeight
    val right = at.x + toCentre + halfWidth <= size.width
    val up = at.y - reach - halfHeight >= 0
    val beside =
        Offset(
            if (right) at.x + toCentre else at.x - toCentre,
            if (up) at.y - reach else at.y + reach,
        )
    return inside(beside, text)
}

private fun DrawScope.inside(
    centre: Offset,
    text: TextLayoutResult,
): Offset {
    val keyline = HAIRLINE.toPx()
    val badge = badgeSize(text)
    val halfWidth = badge.width / 2 + keyline
    val halfHeight = badge.height / 2 + keyline
    return Offset(
        centre.x.coerceAtMost(size.width - halfWidth).coerceAtLeast(halfWidth),
        centre.y.coerceAtMost(size.height - halfHeight).coerceAtLeast(halfHeight),
    )
}

private fun DrawScope.drawBadge(
    text: TextLayoutResult,
    centre: Offset,
    fill: Color,
    keyline: Color,
) {
    val line = HAIRLINE.toPx()
    val badge = badgeSize(text)
    val outer = Size(badge.width + 2 * line, badge.height + 2 * line)
    drawRoundRect(
        keyline,
        topLeft = centre - Offset(outer.width / 2, outer.height / 2),
        size = outer,
        cornerRadius = CornerRadius(outer.height / 2),
    )
    drawRoundRect(
        fill,
        topLeft = centre - Offset(badge.width / 2, badge.height / 2),
        size = badge,
        cornerRadius = CornerRadius(badge.height / 2),
    )
    drawText(text, topLeft = centre - Offset(text.size.width / 2f, text.size.height / 2f))
}
