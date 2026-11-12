package app.dartsscorer.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.dartsscorer.R
import app.dartsscorer.data.ThemeMode
import app.dartsscorer.theme.Spacing
import app.dartsscorer.ui.appViewModelExtras
import app.dartsscorer.ui.common.LinkRow
import app.dartsscorer.ui.common.LinkTarget
import app.dartsscorer.ui.common.SectionHeader
import app.dartsscorer.ui.common.SwitchRow
import app.dartsscorer.ui.support.SupportRequest
import app.dartsscorer.ui.support.hintRes
import app.dartsscorer.ui.support.sendSupportMail
import app.dartsscorer.ui.support.titleRes

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onOpenLicences: () -> Unit,
    onOpenSupport: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: SettingsViewModel =
        viewModel(factory = SettingsViewModel.Factory, extras = appViewModelExtras()),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    Scaffold(
        modifier = modifier,
        topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_settings)) }) },
    ) { insets ->
        Column(modifier = Modifier.padding(insets).verticalScroll(rememberScrollState())) {
            SectionHeader(stringResource(R.string.settings_appearance))

            Row(modifier = Modifier.padding(horizontal = Spacing.base)) {
                for (mode in ThemeMode.entries) {
                    FilterChip(
                        selected = state.themeMode == mode,
                        onClick = { viewModel.setThemeMode(mode) },
                        label = { Text(stringResource(mode.labelRes())) },
                        modifier = Modifier.padding(end = Spacing.tight),
                    )
                }
            }

            SwitchRow(
                title = stringResource(R.string.settings_material_you),
                subtitle = stringResource(R.string.settings_material_you_hint),
                checked = state.materialYou,
                onChange = viewModel::setMaterialYou,
            )

            SectionHeader(stringResource(R.string.settings_language))
            LanguageRow()
            // The channel that stands in for a native read-through (docs/translator-brief.md §8),
            // beside the picker because that is where somebody is standing the moment a translation
            // reads wrong. Its wording lives with the other two requests, in ui/support/.
            LinkRow(
                title = stringResource(SupportRequest.Language.titleRes()),
                subtitle = stringResource(SupportRequest.Language.hintRes()),
                target = LinkTarget.Outside,
                onClick = { context.sendSupportMail(SupportRequest.Language) },
            )

            SectionHeader(stringResource(R.string.settings_data))
            RestoreDefaultsRow(onRestore = viewModel::restoreDefaults)

            SectionHeader(stringResource(R.string.settings_about))
            LinkRow(stringResource(R.string.settings_support), LinkTarget.Inside, onClick = onOpenSupport)
            LinkRow(stringResource(R.string.settings_licences), LinkTarget.Inside, onClick = onOpenLicences)

            // The developer-only section. In a release build this composable is a no-op that
            // renders nothing — see `src/release/…/DebugSettings.kt`. It is a source-set seam
            // rather than an `if (BuildConfig.DEBUG)` because with `isMinifyEnabled = false` a
            // statically-false branch is still compiled into the AAB, and its strings are still
            // inside the translation gate. A hide is not a strip.
            DebugSettings()
        }
    }
}

@Composable
private fun LanguageRow() {
    // Read on every composition rather than held in state: `setAppLanguage` recreates the Activity,
    // so this composable is rebuilt from scratch and the fresh read is always correct.
    val current = currentAppLanguage()
    Row(modifier = Modifier.padding(horizontal = Spacing.base)) {
        FilterChip(
            selected = current == null,
            onClick = { setAppLanguage(null) },
            label = { Text(stringResource(R.string.settings_language_system)) },
            modifier = Modifier.padding(end = Spacing.tight),
        )
        for (language in AppLanguage.entries) {
            FilterChip(
                selected = current == language,
                onClick = { setAppLanguage(language) },
                label = { Text(stringResource(language.labelRes)) },
                modifier = Modifier.padding(end = Spacing.tight),
            )
        }
    }
}

/**
 * *Restore to default*, behind a confirmation because nothing brings the old values back. What it
 * resets and what it keeps is `AppPreferences.Keys.SETTINGS` and `KEPT`.
 */
@Composable
private fun RestoreDefaultsRow(onRestore: () -> Unit) {
    var confirming by rememberSaveable { mutableStateOf(false) }

    LinkRow(
        title = stringResource(R.string.settings_restore),
        subtitle = stringResource(R.string.settings_restore_hint),
        target = LinkTarget.Here,
        onClick = { confirming = true },
    )

    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.settings_restore_confirm_title)) },
            text = { Text(stringResource(R.string.settings_restore_confirm_body)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirming = false
                        onRestore()
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) {
                    Text(stringResource(R.string.settings_restore_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }
}

private fun ThemeMode.labelRes(): Int =
    when (this) {
        ThemeMode.SYSTEM -> R.string.settings_theme_system
        ThemeMode.LIGHT -> R.string.settings_theme_light
        ThemeMode.DARK -> R.string.settings_theme_dark
    }
