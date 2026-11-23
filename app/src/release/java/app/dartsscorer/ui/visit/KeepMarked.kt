package app.dartsscorer.ui.visit

import android.content.Context

@Suppress("UNUSED_PARAMETER")
fun keepMarked(
    context: Context,
    visit: VisitPhase.Shown,
    removed: List<ShownDart>,
) = Unit

@Suppress("UNUSED_PARAMETER")
fun keepMarkedNoBoard(
    context: Context,
    visit: VisitPhase.NoBoard,
) = Unit
