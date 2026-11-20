package app.dartsscorer.ui.visit

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.InputMode
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalInputModeManager
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import app.dartsscorer.R
import app.dartsscorer.theme.Spacing
import coil3.compose.AsyncImage
import coil3.compose.LocalPlatformContext
import coil3.compose.rememberAsyncImagePainter
import coil3.request.ImageRequest
import kotlinx.coroutines.delay
import coil3.size.Size as CoilSize

/**
 * Takes focus once per [arrival], so TalkBack lands on it rather than where it last was. A result
 * arrives while the Picker or the camera still has the window, and TalkBack puts its own focus on the
 * first node once the window is back, so the request waits for both.
 */
@Composable
private fun Modifier.focusOnArrival(arrival: Any): Modifier {
    val focus = remember { FocusRequester() }
    val interactions = remember { MutableInteractionSource() }
    val focused by interactions.collectIsFocusedAsState()
    val keyboard = LocalInputModeManager.current.inputMode == InputMode.Keyboard
    var placed by remember(arrival) { mutableStateOf(false) }
    val windowFocused = LocalWindowInfo.current.isWindowFocused
    LaunchedEffect(arrival, windowFocused) {
        if (windowFocused && !placed) {
            delay(WINDOW_SETTLE_MS)
            placed = focus.requestFocus()
        }
    }
    val ring =
        if (focused && keyboard) {
            Modifier.border(FOCUS_RING, MaterialTheme.colorScheme.onSurface, MaterialTheme.shapes.medium)
        } else {
            Modifier
        }
    return focusRequester(focus).focusable(interactionSource = interactions).then(ring)
}

private val FOCUS_RING = 3.dp

private const val WINDOW_SETTLE_MS = 600L

private const val MARKER_MAX_FONT_SCALE = 1.3f

/** At most two fifths of the window high, so the Score and the chips sit beside the Photo rather than under the fold. */
@Composable
private fun Modifier.photoSize(aspect: Double): Modifier {
    val window = LocalWindowInfo.current.containerSize
    val maxHeight = with(LocalDensity.current) { (window.height * 2 / 5).toDp() }
    return heightIn(max = maxHeight).aspectRatio(aspect.toFloat())
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
internal fun NoBoardFound(result: VisitPhase.NoBoard) {
    NoticeBanner(
        title = stringResource(R.string.visit_no_board_title),
        body = stringResource(R.string.visit_no_board_hint),
        modifier = Modifier.padding(bottom = Spacing.base).focusOnArrival(result),
    )
    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        AsyncImage(
            model = result.photo,
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier.photoSize(result.width.toDouble() / result.height),
        )
    }
}

@Composable
internal fun ScoredVisit(result: VisitPhase.Scored) {
    val summary = LocalResources.current.summary(result)

    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        BoardPhoto(result, summary)
    }
    Column(
        modifier =
            Modifier
                .padding(top = Spacing.base)
                .focusOnArrival(result)
                .semantics(mergeDescendants = true) {
                    heading()
                    liveRegion = LiveRegionMode.Polite
                    contentDescription = summary
                },
    ) {
        Text(
            text = stringResource(R.string.visit_score_label),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = result.total.toString(), style = MaterialTheme.typography.displayLarge)
    }
    result.darts.filter { it.unsure }.forEach { dart ->
        Text(
            text = stringResource(R.string.visit_check_dart, dart.number),
            style = MaterialTheme.typography.bodyLarge,
        )
    }
    if (result.darts.isEmpty()) {
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
    ) {
        result.darts.forEach { DartChip(it) }
    }
}

/**
 * Filled when sure, outlined with *Check* when unsure: shape and text, never colour alone. Not a
 * button yet; checkpoint C opens the keypad from it.
 */
@Composable
private fun DartChip(dart: ShownDart) {
    val resources = LocalResources.current
    val description = resources.chipDescription(dart)
    Surface(
        shape = MaterialTheme.shapes.small,
        color = if (dart.unsure) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.secondaryContainer,
        border = if (dart.unsure) BorderStroke(1.dp, MaterialTheme.colorScheme.outline) else null,
        modifier = Modifier.semantics(mergeDescendants = true) { contentDescription = description },
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

/** The Photo cropped to the Board, one node for TalkBack; its markers are not focusable. */
@Composable
private fun BoardPhoto(
    result: VisitPhase.Scored,
    description: String,
) {
    val painter =
        rememberAsyncImagePainter(
            ImageRequest
                .Builder(LocalPlatformContext.current)
                .data(result.photo)
                .size(CoilSize.ORIGINAL)
                .build(),
        )
    val measurer = rememberTextMeasurer()
    val numberStyle = MaterialTheme.typography.labelLarge
    val colors = MaterialTheme.colorScheme
    val crop = result.crop
    Canvas(
        modifier =
            Modifier
                .photoSize(crop.width / crop.height)
                .clipToBounds()
                .semantics {
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
            val at = Offset(((dart.x - crop.left) * scale).toFloat(), ((dart.y - crop.top) * scale).toFloat())
            drawMarker(at, dart, measurer, numberStyle, colors)
        }
    }
}

/**
 * A light disc inside a dark keyline inside a light one, so the number reads on any part of a Photo.
 * The roles are a light and a dark pair in either theme. Unsure: the dark keyline dashed and a *?* badge.
 */
private fun DrawScope.drawMarker(
    at: Offset,
    dart: ShownDart,
    measurer: TextMeasurer,
    style: TextStyle,
    colors: ColorScheme,
) {
    val keyline = 2.dp.toPx()
    val markerDensity = Density(density, fontScale.coerceAtMost(MARKER_MAX_FONT_SCALE))
    val number = measurer.measure(dart.number.toString(), style.copy(color = colors.onSurface), density = markerDensity)
    val radius = maxOf(number.size.width, number.size.height) / 2f + Spacing.hair.toPx()
    drawCircle(colors.surfaceContainerLowest, radius + 2 * keyline, at)
    drawCircle(
        colors.inverseSurface,
        radius + keyline / 2,
        at,
        style =
            Stroke(
                width = keyline,
                pathEffect =
                    if (dart.unsure) PathEffect.dashPathEffect(floatArrayOf(2 * keyline, 1.5f * keyline)) else null,
            ),
    )
    drawText(number, topLeft = at - Offset(number.size.width / 2f, number.size.height / 2f))
    if (dart.unsure) {
        val mark = measurer.measure("?", style.copy(color = colors.onTertiaryContainer), density = markerDensity)
        val badge = maxOf(mark.size.width, mark.size.height) / 2f + keyline / 2
        val centre = at + Offset(radius + keyline, -(radius + keyline))
        drawCircle(colors.inverseSurface, badge + keyline / 2, centre)
        drawCircle(colors.tertiaryContainer, badge, centre)
        drawText(mark, topLeft = centre - Offset(mark.size.width / 2f, mark.size.height / 2f))
    }
}
