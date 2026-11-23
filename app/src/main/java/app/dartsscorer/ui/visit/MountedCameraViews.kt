package app.dartsscorer.ui.visit

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.rememberVectorPainter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import app.dartsscorer.R
import app.dartsscorer.link.PlayerLinkState
import app.dartsscorer.theme.Spacing

@Composable
fun MountedCameraActions(
    camera: MountedCameraUi,
    onTake: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(Spacing.tight)) {
        LinkChip(camera.link)
        when (camera.link) {
            PlayerLinkState.NOT_FOUND -> Hint(R.string.visit_camera_not_found_hint)
            PlayerLinkState.PAIR_AGAIN -> Hint(R.string.visit_camera_pair_again_hint)
            else -> Unit
        }
        camera.failure?.takeUnless { it.saidBy(camera.link) }?.let { failure ->
            Text(
                stringResource(failure.message()),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive },
            )
        }
        val taking = stringResource(R.string.visit_taking_photo)
        // Left enabled while capturing, so TalkBack's focus never sits on a control just disabled.
        Button(
            onClick = onTake,
            modifier =
                Modifier.fillMaxWidth().semantics {
                    if (camera.capturing) stateDescription = taking
                },
        ) {
            Text(
                stringResource(
                    if (camera.failure !=
                        null
                    ) {
                        R.string.visit_camera_try_again
                    } else {
                        R.string.visit_take_mounted
                    },
                ),
            )
        }
        if (camera.capturing) {
            Text(
                taking,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
    }
}

@Composable
private fun LinkChip(link: PlayerLinkState) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
        modifier = Modifier.semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
    ) {
        val icon =
            when (link) {
                PlayerLinkState.CONNECTED -> rememberVectorPainter(Icons.Filled.CheckCircle)
                PlayerLinkState.LOOKING -> painterResource(R.drawable.ic_hourglass_empty)
                else -> rememberVectorPainter(Icons.Filled.Warning)
            }
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(stringResource(link.label()), style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun Hint(
    @StringRes text: Int,
) {
    Text(
        stringResource(text),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
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

private fun CameraFailure.saidBy(link: PlayerLinkState): Boolean =
    when (this) {
        CameraFailure.NotFound -> link == PlayerLinkState.NOT_FOUND
        CameraFailure.PairAgain -> link == PlayerLinkState.PAIR_AGAIN
        CameraFailure.Outdated -> link == PlayerLinkState.OUTDATED
        else -> false
    }

@StringRes
private fun CameraFailure.message(): Int =
    when (this) {
        CameraFailure.NoReply -> R.string.visit_camera_no_reply
        CameraFailure.Lost -> R.string.visit_camera_lost
        CameraFailure.NotFound -> R.string.link_not_found
        CameraFailure.PairAgain -> R.string.visit_camera_pair_again_hint
        CameraFailure.Outdated -> R.string.link_outdated
        CameraFailure.Busy -> R.string.visit_camera_busy
        CameraFailure.NotReady -> R.string.visit_camera_not_ready
        CameraFailure.NoPermission -> R.string.visit_camera_no_permission
        CameraFailure.Failed -> R.string.visit_camera_failed
    }
