package app.dartsscorer.scoring

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.tensorflow.lite.Interpreter
import java.io.Closeable
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel

/**
 * The shipped model (`assets/model/`, phase-1.md §2) on LiteRT's Interpreter, on the CPU. The input
 * size and both heads' shapes are read from the model, so swapping it is a change of file alone.
 * Not thread-safe: one Photo at a time.
 */
class LiteRtModel(
    context: Context,
    threads: Int = DEFAULT_THREADS,
    asset: String = MODEL_ASSET,
) : KeypointModel,
    Closeable {
    private val interpreter = Interpreter(map(context, asset), Interpreter.Options().setNumThreads(threads))
    private val input: ByteBuffer
    private val boardIndex: Int
    private val entryIndex: Int
    private val outputs: Map<Int, ByteBuffer>
    override val inputSize: Int

    init {
        try {
            val shape = interpreter.getInputTensor(0).shape()
            check(shape.size == 4 && shape[0] == 1 && shape[1] == 3 && shape[2] == shape[3]) {
                "the model's input is ${shape.contentToString()}, not 1×3×n×n"
            }
            inputSize = shape[2]
            input = direct(3 * inputSize * inputSize)
            val heads =
                (0 until interpreter.outputTensorCount).associateWith { interpreter.getOutputTensor(it).shape() }
            boardIndex = heads.entries.single { it.value[1] == Decoding.CALIBRATION_CHANNELS + 2 }.key
            entryIndex = heads.entries.single { it.value[1] == 3 }.key
            outputs = heads.mapValues { (_, s) -> direct(s.fold(1) { a, b -> a * b }) }
        } catch (e: Throwable) {
            // The caller never gets an instance to close, so the native interpreter is freed here.
            interpreter.close()
            throw e
        }
    }

    override fun run(input: FloatArray): Heads {
        this.input.rewind()
        this.input.asFloatBuffer().put(input)
        outputs.values.forEach(ByteBuffer::rewind)
        interpreter.runForMultipleInputsOutputs(arrayOf<Any>(this.input), outputs)
        return Heads(tensor(boardIndex), tensor(entryIndex))
    }

    private fun tensor(index: Int): Tensor3 {
        val shape = interpreter.getOutputTensor(index).shape()
        val buffer = outputs.getValue(index)
        buffer.rewind()
        val values = FloatArray(shape[1] * shape[2] * shape[3])
        buffer.asFloatBuffer().get(values)
        return Tensor3(shape[1], shape[2], shape[3], values)
    }

    override fun close() = interpreter.close()

    companion object {
        const val MODEL_ASSET = "model/darts.tflite"

        /** LiteRT's own default is one thread; R2 (phase-1.md Readings) chooses the count on a phone. */
        const val DEFAULT_THREADS = 4

        private fun direct(floats: Int): ByteBuffer =
            ByteBuffer.allocateDirect(4 * floats).order(ByteOrder.nativeOrder())

        /** Memory-mapped, which is why the asset is stored uncompressed (`androidResources.noCompress`). */
        private fun map(
            context: Context,
            asset: String,
        ): MappedByteBuffer =
            context.assets.openFd(asset).use { descriptor ->
                FileInputStream(descriptor.fileDescriptor).use { stream ->
                    stream.channel.map(FileChannel.MapMode.READ_ONLY, descriptor.startOffset, descriptor.declaredLength)
                }
            }
    }
}

/** A Photo written by `MediaFiles`, decoded for [PhotoReader]; null when the file is missing or unreadable. */
fun decodePhoto(file: File): RgbImage? {
    val options = BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.ARGB_8888 }
    val bitmap = BitmapFactory.decodeFile(file.path, options) ?: return null
    return try {
        RgbImage(bitmap.width, bitmap.height, IntArray(bitmap.width * bitmap.height)).also {
            bitmap.getPixels(it.pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        }
    } finally {
        bitmap.recycle()
    }
}
