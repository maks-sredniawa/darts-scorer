package app.dartsscorer.scoring

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val READ_THREAD_CHOICES = listOf(1, 2, 4, 6)

fun readThreads(context: Context): Flow<Int> =
    context.applicationContext.debugStore.data
        .map { it[KEY] ?: LiteRtModel.DEFAULT_THREADS }

suspend fun setReadThreads(
    context: Context,
    threads: Int,
) {
    context.applicationContext.debugStore.edit { it[KEY] = threads }
}

private val Context.debugStore by preferencesDataStore(name = "debug")

private val KEY = intPreferencesKey("read_threads")
