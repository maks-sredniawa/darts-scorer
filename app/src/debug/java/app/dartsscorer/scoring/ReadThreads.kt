package app.dartsscorer.scoring

import android.content.Context
import androidx.core.content.edit

/** R2's thread counts (phase-1.md Readings), picked in Settings' debug section. */
val READ_THREAD_CHOICES = listOf(1, 2, 4, 6)

fun readThreads(context: Context): Int = prefs(context).getInt(KEY, LiteRtModel.DEFAULT_THREADS)

fun setReadThreads(
    context: Context,
    threads: Int,
) = prefs(context).edit { putInt(KEY, threads) }

private fun prefs(context: Context) = context.getSharedPreferences("debug", Context.MODE_PRIVATE)

private const val KEY = "read_threads"
