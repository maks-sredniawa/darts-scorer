package app.dartsscorer.tip

import java.time.Duration
import java.time.Instant

/** Visits scored before the tip is mentioned. */
const val TIP_ASK_AFTER_VISITS = 10

/** How long the app has to have been installed before the tip is mentioned. */
val TIP_ASK_AFTER: Duration = Duration.ofDays(30)

/**
 * Whether the Visit screen should mention the tip — **once per person, to someone who already uses
 * the app** (ADR-0007).
 *
 * [installedAt] is the package's `firstInstallTime`, which a restore onto a new phone does not carry,
 * so a moved install waits its own month. [asked] lives in preferences, which Auto Backup carries
 * (ADR-0005), so a user who answered is not asked again on their next phone.
 */
fun tipAskDue(
    asked: Boolean,
    visits: Int,
    installedAt: Instant,
    now: Instant,
): Boolean =
    !asked &&
        visits >= TIP_ASK_AFTER_VISITS &&
        Duration.between(installedAt, now) >= TIP_ASK_AFTER
