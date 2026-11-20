package app.dartsscorer.scoring

import android.content.Context
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf

@Suppress("UNUSED_PARAMETER")
fun readThreads(context: Context): Flow<Int> = flowOf(LiteRtModel.DEFAULT_THREADS)
