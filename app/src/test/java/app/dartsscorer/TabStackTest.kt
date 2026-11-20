package app.dartsscorer

import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.junit.Assert.assertEquals
import org.junit.Test

class TabStackTest {
    @Test
    fun `Settings sits on Visit, so the Visit outlives it and Back returns there`() {
        val stack = NavBackStack<NavKey>(Visit)
        stack.showTopLevel(TopLevelDestination.SettingsTab)
        assertEquals(listOf(Visit, Settings), stack.toList())
        assertEquals(TopLevelDestination.SettingsTab, stack.currentTab())
        stack.showTopLevel(TopLevelDestination.VisitTab)
        assertEquals(listOf<NavKey>(Visit), stack.toList())
    }

    @Test
    fun `tapping between tabs never deepens the stack`() {
        val stack = NavBackStack<NavKey>(Visit)
        repeat(6) {
            stack.showTopLevel(TopLevelDestination.SettingsTab)
            stack.showTopLevel(TopLevelDestination.VisitTab)
        }
        stack.showTopLevel(TopLevelDestination.SettingsTab)
        assertEquals(listOf(Visit, Settings), stack.toList())
    }

    @Test
    fun `a detail screen keeps its tab lit, and a tab tap leaves it`() {
        val stack = NavBackStack<NavKey>(Visit, Settings, Licences)
        assertEquals(TopLevelDestination.SettingsTab, stack.currentTab())
        stack.showTopLevel(TopLevelDestination.SettingsTab)
        assertEquals(listOf(Visit, Settings), stack.toList())
        assertEquals(TopLevelDestination.VisitTab, NavBackStack<NavKey>(Visit, Support).currentTab())
    }
}
