package je.yw.typelessless.pipeline

import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

data class Wav(
    val pcm: ByteArray,
    val sampleRate: Int,
    val channels: Int,
    val bitsPerSample: Int,
)

/** Minimal RIFF/WAVE reader for PCM files. Enough for our 16 kHz mono s16le assets. */
object WavReader {
    fun read(input: InputStream): Wav {
        val bytes = input.readBytes()
        require(bytes.size > 44) { "WAV too small (${bytes.size} bytes)" }
        require(tag(bytes, 0) == "RIFF") { "not a RIFF file" }
        require(tag(bytes, 8) == "WAVE") { "not a WAVE file" }

        val bb = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        var sampleRate = 16000
        var channels = 1
        var bits = 16
        var pcm: ByteArray? = null

        var pos = 12
        while (pos + 8 <= bytes.size) {
            val id = tag(bytes, pos)
            val size = bb.getInt(pos + 4)
            val body = pos + 8
            when (id) {
                "fmt " -> {
                    channels = bb.getShort(body + 2).toInt()
                    sampleRate = bb.getInt(body + 4)
                    bits = bb.getShort(body + 14).toInt()
                }
                "data" -> {
                    val end = minOf(body + size, bytes.size)
                    pcm = bytes.copyOfRange(body, end)
                }
            }
            // Chunks are word-aligned: skip an extra byte if size is odd.
            pos = body + size + (size and 1)
        }

        return Wav(pcm ?: ByteArray(0), sampleRate, channels, bits)
    }

    private fun tag(b: ByteArray, off: Int): String = String(b, off, 4, Charsets.US_ASCII)
}
