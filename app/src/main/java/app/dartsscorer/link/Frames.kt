package app.dartsscorer.link

import app.dartsscorer.camera.PhoneRole
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.IOException

/** The link's protocol version. A peer on another one gets *Update Darts Scorer on both phones*. */
const val LINK_VERSION = 1

/** A declared length over this is refused before anything is allocated (ADR-0009, decision 3). */
const val MAX_FRAME_BYTES = 16 * 1024 * 1024

class FrameException(
    message: String,
) : IOException(message)

/** Why a Mounted camera answered a `CAPTURE` without a Photo. Sent by name. */
enum class CaptureError {
    NOT_READY,
    PERMISSION,
    BUSY,
    FAILED,
    UNKNOWN,
}

/**
 * A frame is a 4-byte length, a 1-byte type and that many bytes of body (ADR-0009, decision 3).
 * [Hello]'s first field is always the protocol version, so a phone on another version is still read
 * as [ForeignHello] and told so, rather than dropped as garbage.
 */
sealed interface Frame {
    class Hello(
        val role: PhoneRole,
        val appVersion: String,
        /** Sent by the Player's phone in pairing mode only. */
        val nonce: ByteArray? = null,
        /** The Mounted camera's answer to [nonce]: [pairingProof]. */
        val proof: ByteArray? = null,
    ) : Frame

    class ForeignHello(
        val version: Int,
    ) : Frame

    data object Ping : Frame

    data object Pong : Frame

    data class Capture(
        val requestId: Int,
    ) : Frame

    class Photo(
        val requestId: Int,
        val takenAt: Long,
        val width: Int,
        val height: Int,
        val jpeg: ByteArray,
    ) : Frame

    data class Error(
        val requestId: Int,
        val code: CaptureError,
    ) : Frame
}

private const val HELLO = 1
private const val PING = 2
private const val PONG = 3
private const val CAPTURE = 4
private const val PHOTO = 5
private const val ERROR = 6

/** Reads one frame. A truncated frame throws `EOFException`; an oversized or unknown one [FrameException]. */
fun DataInputStream.readFrame(): Frame {
    val length = readInt()
    if (length < 0 || length > MAX_FRAME_BYTES) throw FrameException("Frame of $length bytes refused")
    val type = readUnsignedByte()
    val body = ByteArray(length).also { readFully(it) }
    val input = DataInputStream(ByteArrayInputStream(body))
    return when (type) {
        HELLO -> input.readHello()
        PING -> Frame.Ping
        PONG -> Frame.Pong
        CAPTURE -> Frame.Capture(input.readInt())
        PHOTO -> {
            val requestId = input.readInt()
            val takenAt = input.readLong()
            val width = input.readInt()
            val height = input.readInt()
            Frame.Photo(requestId, takenAt, width, height, input.readBytes())
        }
        ERROR -> {
            val requestId = input.readInt()
            val name = input.readUTF()
            Frame.Error(requestId, CaptureError.entries.firstOrNull { it.name == name } ?: CaptureError.UNKNOWN)
        }
        else -> throw FrameException("Unknown frame type $type")
    }
}

fun DataOutputStream.writeFrame(frame: Frame) {
    val body = ByteArrayOutputStream()
    val type =
        DataOutputStream(body).use { out ->
            when (frame) {
                is Frame.Hello -> {
                    out.writeInt(LINK_VERSION)
                    out.writeUTF(frame.role.name)
                    out.writeUTF(frame.appVersion)
                    out.writeOptional(frame.nonce)
                    out.writeOptional(frame.proof)
                    HELLO
                }
                is Frame.ForeignHello -> throw IllegalArgumentException("A foreign HELLO is only ever read")
                Frame.Ping -> PING
                Frame.Pong -> PONG
                is Frame.Capture -> {
                    out.writeInt(frame.requestId)
                    CAPTURE
                }
                is Frame.Photo -> {
                    out.writeInt(frame.requestId)
                    out.writeLong(frame.takenAt)
                    out.writeInt(frame.width)
                    out.writeInt(frame.height)
                    out.write(frame.jpeg)
                    PHOTO
                }
                is Frame.Error -> {
                    out.writeInt(frame.requestId)
                    out.writeUTF(frame.code.name)
                    ERROR
                }
            }
        }
    writeInt(body.size())
    writeByte(type)
    body.writeTo(this)
    flush()
}

private fun DataInputStream.readHello(): Frame {
    val version = readInt()
    if (version != LINK_VERSION) return Frame.ForeignHello(version)
    val roleName = readUTF()
    val role = PhoneRole.entries.firstOrNull { it.name == roleName } ?: throw FrameException("Unknown role $roleName")
    return Frame.Hello(role, readUTF(), readOptional(), readOptional())
}

private const val MAX_FIELD_BYTES = 64

private fun DataOutputStream.writeOptional(bytes: ByteArray?) {
    writeByte(bytes?.size ?: 0)
    if (bytes != null) write(bytes)
}

private fun DataInputStream.readOptional(): ByteArray? {
    val size = readUnsignedByte()
    if (size > MAX_FIELD_BYTES) throw FrameException("Field of $size bytes refused")
    return if (size == 0) null else ByteArray(size).also { readFully(it) }
}
