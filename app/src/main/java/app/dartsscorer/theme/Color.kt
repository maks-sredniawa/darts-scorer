package app.dartsscorer.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

// GENERATED — do not hand-edit individual roles.
//
// Both schemes are derived from four brand seeds by Material's tonal palette
// construction (CAM16/HCT): the seeds are the judgement, the ~36 roles are
// arithmetic. Hand-picking a role breaks the fixed tonal relationship it holds
// with the rest of its family, and the failure shows up as a contrast bug on one
// screen out of thirty rather than as a visible mistake here.
//
//   primary   #8A6500  — brand: filled buttons, FAB, selected tab
//   secondary #6E6552  — quiet containers: chips, tonal buttons, selected segment
//   tertiary  #3F6E8C  — accents and caution markers, used sparingly
//   neutral   #E4E2DE  — seeds every surface, so it decides warm or cool overall
//
// Error stays M3 baseline (hue 25, chroma 84): a safety signal, not a brand choice.
//
// To change the palette, edit the seeds in scripts/gen_scheme.py and re-run it.
// Colours come from MaterialTheme, never literals, and dynamic colour defaults
// off (ADR-0006) so this file is what a user actually sees.

private val AppLightColors =
    lightColorScheme(
        primary = Color(0xFF7B5900),
        onPrimary = Color(0xFFFFFFFF),
        primaryContainer = Color(0xFFFFDE9C),
        onPrimaryContainer = Color(0xFF261900),
        inversePrimary = Color(0xFFEFC05D),
        secondary = Color(0xFF665D4B),
        onSecondary = Color(0xFFFFFFFF),
        secondaryContainer = Color(0xFFEEE1C9),
        onSecondaryContainer = Color(0xFF211B0C),
        tertiary = Color(0xFF336381),
        onTertiary = Color(0xFFFFFFFF),
        tertiaryContainer = Color(0xFFC6E7FF),
        onTertiaryContainer = Color(0xFF001E2F),
        error = Color(0xFFBA1B1B),
        onError = Color(0xFFFFFFFF),
        errorContainer = Color(0xFFFFDAD4),
        onErrorContainer = Color(0xFF410001),
        background = Color(0xFFFBF9F5),
        onBackground = Color(0xFF1B1C19),
        surface = Color(0xFFFBF9F5),
        onSurface = Color(0xFF1B1C19),
        surfaceVariant = Color(0xFFE0E4D6),
        onSurfaceVariant = Color(0xFF44483E),
        surfaceDim = Color(0xFFDCDAD6),
        surfaceBright = Color(0xFFFBF9F5),
        surfaceContainerLowest = Color(0xFFFFFFFF),
        surfaceContainerLow = Color(0xFFF6F3EF),
        surfaceContainer = Color(0xFFF0EEEA),
        surfaceContainerHigh = Color(0xFFEAE8E4),
        surfaceContainerHighest = Color(0xFFE4E2DE),
        inverseSurface = Color(0xFF30302E),
        inverseOnSurface = Color(0xFFF2F0EC),
        outline = Color(0xFF74796D),
        outlineVariant = Color(0xFFC4C8BB),
        scrim = Color(0xFF000000),
    )

private val AppDarkColors =
    darkColorScheme(
        primary = Color(0xFFEFC05D),
        onPrimary = Color(0xFF412D00),
        primaryContainer = Color(0xFF5D4200),
        onPrimaryContainer = Color(0xFFFFDE9C),
        inversePrimary = Color(0xFF7B5900),
        secondary = Color(0xFFD1C5AE),
        onSecondary = Color(0xFF373020),
        secondaryContainer = Color(0xFF4E4634),
        onSecondaryContainer = Color(0xFFEEE1C9),
        tertiary = Color(0xFF9ECCEE),
        onTertiary = Color(0xFF00344D),
        tertiaryContainer = Color(0xFF164B67),
        onTertiaryContainer = Color(0xFFC6E7FF),
        error = Color(0xFFFFB4A9),
        onError = Color(0xFF680003),
        errorContainer = Color(0xFF930006),
        onErrorContainer = Color(0xFFFFDAD4),
        background = Color(0xFF131411),
        onBackground = Color(0xFFE4E2DE),
        surface = Color(0xFF131411),
        onSurface = Color(0xFFE4E2DE),
        surfaceVariant = Color(0xFF44483E),
        onSurfaceVariant = Color(0xFFC4C8BB),
        surfaceDim = Color(0xFF131411),
        surfaceBright = Color(0xFF393937),
        surfaceContainerLowest = Color(0xFF0E0F0C),
        surfaceContainerLow = Color(0xFF1B1C19),
        surfaceContainer = Color(0xFF1F201D),
        surfaceContainerHigh = Color(0xFF2A2A28),
        surfaceContainerHighest = Color(0xFF353533),
        inverseSurface = Color(0xFFE4E2DE),
        inverseOnSurface = Color(0xFF30302E),
        outline = Color(0xFF8E9286),
        outlineVariant = Color(0xFF44483E),
        scrim = Color(0xFF000000),
    )

internal val LightColors = AppLightColors
internal val DarkColors = AppDarkColors
