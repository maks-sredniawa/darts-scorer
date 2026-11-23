package app.dartsscorer.ui.camera

import android.content.ClipData
import android.content.ClipDescription
import android.content.Intent
import android.os.Build
import android.os.PersistableBundle
import androidx.annotation.StringRes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.graphics.vector.rememberVectorPainter
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.link.PlayerLinkState
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras
import app.dartsscorer.ui.common.DetailScaffold
import app.dartsscorer.ui.common.SectionHeader
import app.dartsscorer.ui.common.startActivitySafely
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.common.BitMatrix
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import kotlinx.coroutines.launch

private val QR_MAX = 280.dp

/** *Add a mounted camera*, on the Player's phone (`phase-G.md` §4 and its 2026-11-23 design). */
@Composable
fun AddMountedCameraScreen(
    onBack: () -> Unit,
    viewModel: AddMountedCameraViewModel =
        viewModel(factory = AddMountedCameraViewModel.Factory, extras = appViewModelExtras()),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LifecycleStartEffect(viewModel) {
        viewModel.start()
        onStopOrDispose { viewModel.stop() }
    }
    DetailScaffold(title = stringResource(R.string.mounted_camera_add), onBack = onBack) { modifier ->
        Column(modifier.verticalScroll(rememberScrollState())) {
            if (state.paired) SectionHeader(stringResource(R.string.add_camera_paired_header))
            // One node in both states, so pairing is announced as a change of this live region.
            LinkStatus(state)
            if (state.paired) {
                PairedActions(state.link, viewModel::unpair)
            } else {
                state.code?.let { PairingCode(it) }
            }
            DebugPlayerLink(viewModel::capture)
        }
    }
}

@Composable
private fun LinkStatus(state: AddMountedCameraUiState) {
    val icon: Painter
    val title: String
    val subtitle: String?
    when {
        state.paired -> {
            icon = painterResource(R.drawable.ic_videocam)
            title = stringResource(R.string.settings_mounted_camera)
            subtitle =
                stringResource(
                    if (state.justPaired && state.link == PlayerLinkState.LOOKING) {
                        R.string.add_camera_just_paired
                    } else {
                        state.link.label()
                    },
                )
        }
        state.link == PlayerLinkState.OUTDATED -> {
            icon = rememberVectorPainter(Icons.Filled.Warning)
            title = stringResource(R.string.link_outdated)
            subtitle = null
        }
        else -> {
            icon = painterResource(R.drawable.ic_hourglass_empty)
            title = stringResource(R.string.add_camera_waiting)
            subtitle = null
        }
    }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.base),
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(horizontal = Spacing.base, vertical = Spacing.snug)
                .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
    ) {
        val connected = state.paired && state.link == PlayerLinkState.CONNECTED
        Icon(
            if (connected) rememberVectorPainter(Icons.Filled.CheckCircle) else icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Column(verticalArrangement = Arrangement.spacedBy(Spacing.hair)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            if (subtitle != null) {
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@StringRes
private fun PlayerLinkState.label(): Int =
    when (this) {
        PlayerLinkState.LOOKING -> R.string.link_looking
        PlayerLinkState.CONNECTED -> R.string.link_connected
        PlayerLinkState.NOT_FOUND -> R.string.link_not_found
        PlayerLinkState.PAIR_AGAIN -> R.string.link_pair_again
        PlayerLinkState.OUTDATED -> R.string.link_outdated
    }

@Composable
private fun PairingCode(code: String) {
    val context = LocalContext.current
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    var copied by rememberSaveable { mutableStateOf(false) }
    Column(
        modifier = Modifier.padding(horizontal = Spacing.base),
        verticalArrangement = Arrangement.spacedBy(Spacing.tight),
    ) {
        Text(stringResource(R.string.add_camera_step_1), style = MaterialTheme.typography.bodyLarge)
        Text(stringResource(R.string.add_camera_step_2), style = MaterialTheme.typography.bodyLarge)
        Qr(code, Modifier.padding(vertical = Spacing.base))
        val label = stringResource(R.string.add_camera_copy)
        OutlinedButton(
            onClick = {
                val clip =
                    ClipData.newPlainText(label, code).apply {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            description.extras =
                                PersistableBundle().apply { putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true) }
                        }
                    }
                scope.launch { clipboard.setClipEntry(ClipEntry(clip)) }
                copied = true
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Icon(painterResource(R.drawable.ic_content_copy), contentDescription = null)
            Text(label, Modifier.padding(start = Spacing.tight))
        }
        OutlinedButton(
            onClick = {
                val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, code)
                context.startActivitySafely(Intent.createChooser(send, null))
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Icon(Icons.Filled.Share, contentDescription = null)
            Text(stringResource(R.string.add_camera_share), Modifier.padding(start = Spacing.tight))
        }
        // From Android 13 the system shows its own confirmation of a copy.
        if (copied && Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            Text(
                stringResource(R.string.add_camera_copied),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
        Text(
            stringResource(R.string.add_camera_caption),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = Spacing.tight),
        )
    }
}

/** Dark modules on a light ground in either theme, so every scanner reads it. */
@Composable
private fun Qr(
    code: String,
    modifier: Modifier = Modifier,
) {
    val matrix = remember(code) { qrMatrix(code) }
    val colors = MaterialTheme.colorScheme
    val dark = colors.surface.luminance() < 0.5f
    val ground = if (dark) colors.inverseSurface else colors.surface
    val modules = if (dark) colors.inverseOnSurface else colors.onSurface
    val description = stringResource(R.string.add_camera_qr_description)
    BoxWithConstraints(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        val side = minOf(maxWidth, QR_MAX)
        Surface(shape = MaterialTheme.shapes.medium, color = ground) {
            Box(Modifier.padding(Spacing.base)) {
                Canvas(
                    Modifier.size(side).semantics {
                        contentDescription = description
                        role = Role.Image
                    },
                ) {
                    val cell = size.width / matrix.width
                    for (y in 0 until matrix.height) {
                        for (x in 0 until matrix.width) {
                            if (matrix[x, y]) {
                                drawRect(modules, Offset(x * cell, y * cell), Size(cell + 0.5f, cell + 0.5f))
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun qrMatrix(code: String): BitMatrix =
    QRCodeWriter().encode(
        code,
        BarcodeFormat.QR_CODE,
        0,
        0,
        mapOf(EncodeHintType.MARGIN to 0, EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M),
    )

@Composable
private fun PairedActions(
    link: PlayerLinkState,
    onUnpair: () -> Unit,
) {
    var confirming by rememberSaveable { mutableStateOf(false) }
    Column(Modifier.padding(horizontal = Spacing.base)) {
        if (link == PlayerLinkState.PAIR_AGAIN) {
            // The camera already dropped this phone, so there is nothing left to confirm.
            Button(onClick = onUnpair, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.link_pair_again))
            }
        } else {
            TextButton(
                onClick = { confirming = true },
                colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
            ) {
                Text(stringResource(R.string.camera_role_unpair))
            }
        }
    }
    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.camera_role_unpair_title)) },
            text = { Text(stringResource(R.string.mounted_camera_unpair_body)) },
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
