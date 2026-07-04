package je.yw.typelessless.pipeline

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log

/**
 * Captures 16 kHz mono PCM16 from the mic and delivers ~100 ms chunks to a
 * callback on a background thread. Requires RECORD_AUDIO to already be granted.
 */
class AudioCapture(private val sampleRate: Int = 16000) {

    @Volatile private var running = false
    private var thread: Thread? = null

    /** Start capture. onPcm(buf, len) is called repeatedly; buf is reused. */
    fun start(onPcm: (ByteArray, Int) -> Unit, onError: (Throwable) -> Unit) {
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufSize = maxOf(minBuf, sampleRate * 2) // >= 1 s of headroom

        val recorder = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufSize,
            )
        } catch (e: Throwable) {
            onError(e)
            return
        }

        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            onError(IllegalStateException("AudioRecord failed to initialize"))
            return
        }

        running = true
        thread = Thread {
            val buf = ByteArray(3200) // 100 ms @ 16 kHz mono 16-bit
            try {
                recorder.startRecording()
                while (running) {
                    val n = recorder.read(buf, 0, buf.size)
                    if (n > 0) onPcm(buf, n)
                }
            } catch (e: Throwable) {
                Log.e("typelessless", "capture error", e)
                onError(e)
            } finally {
                try { recorder.stop() } catch (_: Throwable) {}
                recorder.release()
            }
        }.also { it.start() }
    }

    fun stop() {
        running = false
        thread?.join(600)
        thread = null
    }
}
