package app.dartsscorer.ui.common

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.core.content.ContextCompat

/**
 * `startActivity`, reporting failure rather than taking the app down with it.
 *
 * Every hand-off launches something it cannot be sure exists — a mail app or Play. One that is
 * present but not exported to us throws `SecurityException`, which is the same outcome from here as
 * it not being there at all.
 */
internal fun Context.startActivitySafely(intent: Intent): Boolean =
    try {
        startActivity(intent)
        true
    } catch (e: ActivityNotFoundException) {
        false
    } catch (e: SecurityException) {
        false
    }

/** This app's page in the system settings, where a denied permission is allowed again. */
internal fun Context.openAppSettings(): Boolean =
    startActivitySafely(
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
    )

internal fun Context.hasCameraPermission(): Boolean =
    ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
