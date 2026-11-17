package app.dartsscorer.m2spike

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import kotlin.math.abs
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.tensorflow.lite.Interpreter

@RunWith(AndroidJUnit4::class)
class RfDetrOnDeviceTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets

    private fun direct(name: String): ByteBuffer {
        val bytes = assets.open("m2spike/$name").use { it.readBytes() }
        return ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).put(bytes).apply { rewind() }
    }

    private fun mapped(name: String): ByteBuffer = assets.openFd("m2spike/$name").use { fd ->
        FileInputStream(fd.fileDescriptor).channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
    }

    private fun floats(name: String): FloatArray {
        val buffer = direct(name).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun run(model: String, tolerance: Float?) {
        val options = Interpreter.Options().setNumThreads(4)
        Interpreter(mapped(model), options).use { interpreter ->
            val shapes = (0 until interpreter.outputTensorCount).map { interpreter.getOutputTensor(it).shape().toList() }
            val outputs = shapes.indices.associateWith { i ->
                ByteBuffer.allocateDirect(shapes[i].fold(4) { a, b -> a * b }).order(ByteOrder.nativeOrder())
            }
            val input = direct("rfdetr_input.bin")
            interpreter.runForMultipleInputsOutputs(arrayOf(input), outputs)

            fun maxDiff(prefix: String) = listOf("dets", "labels", "keypoints").associateWith { name ->
                val expected = floats("${prefix}_$name.bin")
                val index = shapes.indexOfFirst { it.fold(1) { a, b -> a * b } == expected.size }
                val actual = outputs.getValue(index).apply { rewind() }.asFloatBuffer()
                var max = 0f
                for (i in expected.indices) max = maxOf(max, abs(actual.get(i) - expected[i]))
                max
            }
            val vsPyTorch = maxDiff("rfdetr")
            val vsHostTflite = maxDiff("rfdetr_host")

            val times = (1..10).map {
                input.rewind()
                outputs.values.forEach { it.rewind() }
                val start = System.nanoTime()
                interpreter.runForMultipleInputsOutputs(arrayOf(input), outputs)
                (System.nanoTime() - start) / 1e6
            }.sorted()
            Log.i("M2SPIKE", "$model threads=4 outputs=$shapes vsPyTorch=$vsPyTorch vsHostTflite=$vsHostTflite medianMs=${times[5]} minMs=${times.first()}")
            if (tolerance != null) {
                val dets = vsHostTflite.getValue("dets")
                assertTrue("$model boxes differ from the host LiteRT run by $dets", dets < tolerance)
            }
        }
    }

    @Test fun fp32() = run("rfdetr_fp32.tflite", 1e-3f)

    @Test fun fp16() = run("rfdetr_fp16.tflite", null)

    @Test fun int8() = run("rfdetr_int8.tflite", null)
}
