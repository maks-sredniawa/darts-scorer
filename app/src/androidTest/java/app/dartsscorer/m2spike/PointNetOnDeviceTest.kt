package app.dartsscorer.m2spike

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.tensorflow.lite.Interpreter

@RunWith(AndroidJUnit4::class)
class PointNetOnDeviceTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets

    private fun direct(name: String): ByteBuffer {
        val bytes = assets.open("m2spike/$name").use { it.readBytes() }
        return ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).put(bytes).apply { rewind() }
    }

    private fun floats(name: String): FloatArray {
        val buffer = direct(name).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun run(model: String, threads: Int) {
        val options = Interpreter.Options().setNumThreads(threads)
        Interpreter(direct(model), options).use { interpreter ->
            val shapes = (0 until interpreter.outputTensorCount).map { interpreter.getOutputTensor(it).shape().toList() }
            val heatIndex = shapes.indexOfFirst { 81 in it }
            val outputs = shapes.associate { shape ->
                shapes.indexOf(shape) to ByteBuffer.allocateDirect(shape.fold(4) { a, b -> a * b }).order(ByteOrder.nativeOrder())
            }
            val input = direct("input.bin")
            interpreter.runForMultipleInputsOutputs(arrayOf(input), outputs)
            val heat = outputs.getValue(heatIndex).apply { rewind() }.asFloatBuffer()
            val expected = floats("heat.bin")
            var worst = 0f
            for (i in expected.indices) worst = maxOf(worst, abs(heat.get(i) - expected[i]))

            val times = (1..10).map {
                input.rewind()
                outputs.values.forEach { it.rewind() }
                val start = System.nanoTime()
                interpreter.runForMultipleInputsOutputs(arrayOf(input), outputs)
                (System.nanoTime() - start) / 1e6
            }.sorted()
            Log.i("M2SPIKE", "$model threads=$threads outputs=$shapes maxHeatDiff=$worst medianMs=${times[5]} minMs=${times.first()}")
            assertTrue("$model differs from PyTorch by $worst", worst < 0.02f)
        }
    }

    @Test fun fp32() = run("pointnet_fp32.tflite", 4)

    @Test fun fp16() = run("pointnet_fp16.tflite", 4)
}
