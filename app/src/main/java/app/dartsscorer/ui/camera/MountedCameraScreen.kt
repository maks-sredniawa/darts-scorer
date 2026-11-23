package app.dartsscorer.ui.camera

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras
import app.dartsscorer.ui.common.DetailScaffold
import app.dartsscorer.ui.common.LinkRow
import app.dartsscorer.ui.common.LinkTarget
import app.dartsscorer.ui.common.NoticeBanner
import app.dartsscorer.ui.common.OpenAppSettingsButton
import app.dartsscorer.ui.common.hasCameraPermission

/** Settings' *Mounted camera*: which of the two phones this one is (ADR-0009, decision 9). */
@Composable
fun MountedCameraScreen(
    onBack: () -> Unit,
    onAddCamera: () -> Unit,
    onUseAsCamera: () -> Unit,
    viewModel: MountedCameraViewModel =
        viewModel(factory = MountedCameraViewModel.Factory, extras = appViewModelExtras()),
) {
    val context = LocalContext.current
    val state by viewModel.state.collectAsStateWithLifecycle()
    var denied by rememberSaveable { mutableStateOf(false) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { if (context.hasCameraPermission()) denied = false }
    val askCamera =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            denied = !granted
            if (granted) onUseAsCamera()
        }

    DetailScaffold(title = stringResource(R.string.settings_mounted_camera), onBack = onBack) { modifier ->
        Column(modifier.verticalScroll(rememberScrollState())) {
            Text(
                stringResource(R.string.mounted_camera_intro),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = Spacing.base),
            )
            if (denied) {
                NoticeBanner(
                    stringResource(R.string.camera_denied_title),
                    stringResource(R.string.mounted_camera_denied_body),
                    Modifier.padding(start = Spacing.base, end = Spacing.base, top = Spacing.base),
                    action = { OpenAppSettingsButton() },
                )
            }
            Spacer(Modifier.height(Spacing.section))
            LinkRow(
                title = stringResource(R.string.mounted_camera_add),
                subtitle =
                    stringResource(
                        if (state.cameraPaired) {
                            R.string.mounted_camera_add_paired
                        } else {
                            R.string.mounted_camera_add_hint
                        },
                    ),
                target = LinkTarget.Inside,
                onClick = onAddCamera,
            )
            LinkRow(
                title = stringResource(R.string.mounted_camera_use),
                subtitle = stringResource(R.string.mounted_camera_use_hint),
                target = LinkTarget.Inside,
                onClick = {
                    if (context.hasCameraPermission()) onUseAsCamera() else askCamera.launch(Manifest.permission.CAMERA)
                },
            )
        }
    }
}
