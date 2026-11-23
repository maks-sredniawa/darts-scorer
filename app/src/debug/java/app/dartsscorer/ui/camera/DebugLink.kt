package app.dartsscorer.ui.camera

import android.util.Log
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import app.dartsscorer.R
import app.dartsscorer.link.LINK_TAG
import app.dartsscorer.link.LinkDebug
import app.dartsscorer.link.ReceivedPhoto
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.common.SwitchRow
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.InetSocketAddress

/** R2's switch: skip the `MulticastLock` on the next advertisement (`phase-G.md` §4). */
@Composable
fun DebugCameraLink() {
    val skip by LinkDebug.skipMulticastLock.collectAsState()
    SwitchRow(
        title = stringResource(R.string.debug_skip_multicast_lock),
        subtitle = stringResource(R.string.debug_skip_multicast_lock_hint),
        checked = skip,
        onChange = { LinkDebug.skipMulticastLock.value = it },
    )
}

/** An address instead of NSD, and a capture whose JPEG is logged rather than scored. */
@Composable
fun DebugPlayerLink(capture: suspend () -> ReceivedPhoto) {
    val scope = rememberCoroutineScope()
    val target by LinkDebug.target.collectAsState()
    var address by rememberSaveable { mutableStateOf(target?.let { "${it.hostString}:${it.port}" } ?: "") }
    Column(
        modifier = Modifier.padding(horizontal = Spacing.base, vertical = Spacing.base),
        verticalArrangement = Arrangement.spacedBy(Spacing.tight),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(Spacing.tight),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = address,
                onValueChange = { address = it },
                label = { Text(stringResource(R.string.debug_link_address)) },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            OutlinedButton(
                onClick = {
                    scope.launch {
                        LinkDebug.target.value =
                            withContext(
                                Dispatchers.IO,
                            ) { parseTarget(address) }
                    }
                },
            ) {
                Text(stringResource(R.string.debug_link_address_use))
            }
        }
        OutlinedButton(
            onClick = {
                scope.launch {
                    try {
                        val photo = capture()
                        val jpeg =
                            photo.jpeg.size > 2 && photo.jpeg[0] == 0xFF.toByte() && photo.jpeg[1] == 0xD8.toByte()
                        Log.i(
                            LINK_TAG,
                            "Received a Photo of ${photo.jpeg.size} bytes, ${photo.width}x${photo.height}, JPEG=$jpeg",
                        )
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        Log.w(LINK_TAG, "The capture failed: $e")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.debug_link_capture))
        }
    }
}

/** Blocking: a host name is looked up here. */
private fun parseTarget(text: String): InetSocketAddress? {
    val host = text.substringBeforeLast(':', "").trim()
    val port = text.substringAfterLast(':', "").trim().toIntOrNull() ?: return null
    if (host.isEmpty()) return null
    return InetSocketAddress(host, port)
}
