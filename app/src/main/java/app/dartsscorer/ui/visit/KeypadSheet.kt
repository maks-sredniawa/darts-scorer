package app.dartsscorer.ui.visit

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.dartsscorer.R
import app.dartsscorer.scoring.Ring
import app.dartsscorer.theme.Spacing

/** Below this a window is too short to stack the keypad's two groups, and they sit side by side. */
internal val SHORT_WINDOW = 480.dp

@Composable
internal fun isShortWindow(): Boolean {
    val height = LocalWindowInfo.current.containerSize.height
    return with(LocalDensity.current) { height.toDp() } < SHORT_WINDOW
}

/** phase-1.md §3's keypad: the ring row and the beds as two labelled groups, the live Score, *Done*. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun KeypadSheet(
    keypad: Keypad,
    onRing: (Ring) -> Unit,
    onNumber: (Int) -> Unit,
    onOther: (Ring) -> Unit,
    onDone: () -> Unit,
    onRemove: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    val short = isShortWindow()
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        sheetMaxWidth = if (short) Dp.Unspecified else 640.dp,
        dragHandle = { DragHandle() },
    ) {
        val content = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = Spacing.base)
        if (short) {
            Row(modifier = content, horizontalArrangement = Arrangement.spacedBy(Spacing.section)) {
                Column(modifier = Modifier.weight(2f), verticalArrangement = Arrangement.spacedBy(Spacing.base)) {
                    Header(keypad)
                    RingGroup(keypad, onRing)
                    Actions(keypad, onDone, onRemove)
                }
                Column(modifier = Modifier.weight(3f)) { BedGroup(keypad, onNumber, onOther) }
            }
        } else {
            Column(modifier = content, verticalArrangement = Arrangement.spacedBy(Spacing.base)) {
                Header(keypad)
                RingGroup(keypad, onRing)
                BedGroup(keypad, onNumber, onOther)
                Actions(keypad, onDone, onRemove)
            }
        }
    }
}

/**
 * Material's handle, drawn without its semantics: as the sheet's first node it would take TalkBack's
 * focus when the sheet opens, where §3 puts it on the sheet's title. Back still closes the sheet.
 */
@Composable
private fun DragHandle() {
    Surface(
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        shape = MaterialTheme.shapes.extraLarge,
        modifier = Modifier.padding(vertical = Spacing.base),
    ) {
        Box(Modifier.size(width = HANDLE_WIDTH, height = Spacing.hair))
    }
}

private val HANDLE_WIDTH = 32.dp

/** Which Dart, and the Score the keys make so far, read out as it changes. */
@Composable
private fun Header(keypad: Keypad) {
    val resources = LocalResources.current
    val score = keypad.score
    val shown = score?.let { stringResource(R.string.keypad_score, resources.shortName(it), it.value) }
    val spoken =
        score?.let {
            stringResource(
                R.string.keypad_score_description,
                resources.spokenName(it),
                resources.getQuantityString(R.plurals.visit_points, it.value, it.value),
            )
        }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            text =
                keypad.dart?.let { stringResource(R.string.keypad_title_dart, it) }
                    ?: stringResource(R.string.keypad_title_new),
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.weight(1f).semantics { heading() }.focusOnArrival(keypad.dart ?: NEW_DART),
        )
        Text(
            text = shown ?: stringResource(R.string.keypad_pick_number),
            style = if (shown != null) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodyLarge,
            color =
                if (shown !=
                    null
                ) {
                    MaterialTheme.colorScheme.onSurface
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            modifier =
                Modifier.padding(start = Spacing.base).semantics {
                    liveRegion = LiveRegionMode.Polite
                    spoken?.let { contentDescription = it }
                },
        )
    }
}

private const val NEW_DART = "new"

@Composable
private fun GroupLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(bottom = Spacing.tight),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RingGroup(
    keypad: Keypad,
    onRing: (Ring) -> Unit,
) {
    val labels =
        mapOf(
            Ring.SINGLE to stringResource(R.string.keypad_single),
            Ring.DOUBLE to stringResource(R.string.keypad_double),
            Ring.TREBLE to stringResource(R.string.keypad_treble),
        )
    Column {
        GroupLabel(stringResource(R.string.keypad_ring))
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            Keypad.RING_ROW.forEachIndexed { i, ring ->
                SegmentedButton(
                    selected = keypad.other == null && keypad.ring == ring,
                    onClick = { onRing(ring) },
                    shape = SegmentedButtonDefaults.itemShape(i, Keypad.RING_ROW.size),
                    modifier = Modifier.heightIn(min = TOUCH_TARGET),
                ) {
                    Text(labels.getValue(ring), maxLines = 1)
                }
            }
        }
    }
}

/** 1–20 in numeric order, five to a row, then the Bulls and *Miss*: one group, one pick. */
@Composable
private fun BedGroup(
    keypad: Keypad,
    onNumber: (Int) -> Unit,
    onOther: (Ring) -> Unit,
) {
    val others =
        mapOf(
            Ring.OUTER_BULL to stringResource(R.string.keypad_outer_bull),
            Ring.BULL to stringResource(R.string.keypad_bull),
            Ring.MISS to stringResource(R.string.keypad_miss),
        )
    Column {
        GroupLabel(stringResource(R.string.keypad_number))
        Column(modifier = Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(Spacing.tight)) {
            (1..20).chunked(KEYS_PER_ROW).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(Spacing.tight)) {
                    row.forEach { number ->
                        Key(
                            label = number.toString(),
                            selected = keypad.other == null && keypad.number == number,
                            onClick = { onNumber(number) },
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.tight)) {
                Keypad.OTHERS.forEach { other ->
                    Key(
                        label = others.getValue(other),
                        selected = keypad.other == other,
                        onClick = { onOther(other) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

private const val KEYS_PER_ROW = 5

/** A check and a fill when selected, an outline when not: never tint alone. */
@Composable
private fun Key(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.small
    Surface(
        shape = shape,
        color = if (selected) colors.secondaryContainer else colors.surfaceContainerLow,
        contentColor = if (selected) colors.onSecondaryContainer else colors.onSurface,
        border = if (selected) null else BorderStroke(1.dp, colors.outlineVariant),
        modifier =
            modifier
                .heightIn(min = TOUCH_TARGET)
                .clip(shape)
                .selectable(selected = selected, onClick = onClick, role = Role.RadioButton),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = Spacing.hair),
            horizontalArrangement = Arrangement.spacedBy(Spacing.hair, Alignment.CenterHorizontally),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(CHECK))
            }
            Text(text = label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}

private val CHECK = 18.dp

@Composable
private fun Actions(
    keypad: Keypad,
    onDone: () -> Unit,
    onRemove: (Int) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(bottom = Spacing.base),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        keypad.dart?.let { dart ->
            TextButton(onClick = { onRemove(dart) }, modifier = Modifier.heightIn(min = TOUCH_TARGET)) {
                Text(stringResource(R.string.visit_remove_dart))
            }
        }
        Spacer(Modifier.weight(1f))
        Button(onClick = onDone, enabled = keypad.score != null, modifier = Modifier.heightIn(min = TOUCH_TARGET)) {
            Text(stringResource(R.string.keypad_done))
        }
    }
}
