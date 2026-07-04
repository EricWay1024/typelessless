package je.yw.typelessless.pipeline

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONArray
import org.json.JSONObject
import java.util.ArrayDeque
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * A live Soniox realtime STT session — the Kotlin twin of the desktop's
 * SonioxSession. Open it, feed() PCM16 as the mic produces it, then finish() to
 * send the end-of-stream marker and get the concatenated final transcript.
 *
 * feed() may be called before the socket finishes opening; early audio is
 * buffered and flushed once the config frame has been sent.
 */
class SonioxSession internal constructor(
    client: OkHttpClient,
    configJson: String,
    private val onPartial: ((String) -> Unit)?,
) {
    private val finals = StringBuilder()
    private val error = arrayOfNulls<String>(1)
    private val done = CountDownLatch(1)
    private val messages = intArrayOf(0)

    private val lock = Any()
    private var opened = false
    private var endRequested = false
    private val pending = ArrayDeque<ByteString>()

    private val ws: WebSocket

    init {
        val request = Request.Builder().url(SonioxClient.WS_URL).build()
        ws = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(configJson)
                synchronized(lock) {
                    opened = true
                    while (pending.isNotEmpty()) webSocket.send(pending.removeFirst())
                    if (endRequested) webSocket.send("")
                }
                Log.i(TAG, "ws open (${response.code})")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                messages[0]++
                val res = JSONObject(text)
                if (!res.isNull("error_code")) {
                    error[0] = "${res.opt("error_code")}: ${res.optString("error_message")}"
                    Log.e(TAG, "soniox error: ${error[0]}")
                    done.countDown()
                    return
                }
                val nonfinal = StringBuilder()
                val toks = res.optJSONArray("tokens")
                if (toks != null) {
                    for (i in 0 until toks.length()) {
                        val t = toks.getJSONObject(i)
                        val txt = t.optString("text")
                        if (txt.isEmpty()) continue
                        if (t.optBoolean("is_final")) finals.append(txt) else nonfinal.append(txt)
                    }
                }
                onPartial?.invoke(finals.toString() + nonfinal.toString())
                if (res.optBoolean("finished")) {
                    Log.i(TAG, "soniox finished: ${messages[0]} msgs, ${finals.length} final chars")
                    done.countDown()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                error[0] = "${t.javaClass.simpleName}: ${t.message} (http=${response?.code})"
                Log.e(TAG, "ws failure: ${error[0]}", t)
                done.countDown()
            }

            // Soniox closes the stream when done; complete the close so we don't
            // hang, and treat it as end-of-transcript (mirrors the Python client).
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "ws closing: $code '$reason' (finals=${finals.length})")
                webSocket.close(1000, null)
                done.countDown()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                done.countDown()
            }
        })
    }

    /** Feed one chunk of PCM16 mono. Safe to call from the capture thread. */
    fun feed(pcm: ByteArray, len: Int) {
        val bs = pcm.toByteString(0, len) // copies, so the caller may reuse pcm
        synchronized(lock) {
            if (opened) ws.send(bs) else pending.add(bs)
        }
    }

    /** Signal end-of-stream and block until Soniox returns the final transcript. */
    fun finish(timeoutSeconds: Long = 20L): String {
        synchronized(lock) {
            if (opened) ws.send("") else endRequested = true
        }
        val finished = done.await(timeoutSeconds, TimeUnit.SECONDS)
        ws.close(1000, null)
        error[0]?.let { throw RuntimeException("Soniox error: $it") }
        if (!finished) {
            throw RuntimeException("Soniox timed out (msgs=${messages[0]}, finals=${finals.length})")
        }
        return finals.toString().trim()
    }

    fun cancel() {
        ws.cancel()
        done.countDown()
    }

    companion object {
        private const val TAG = "typelessless"
    }
}

/**
 * Opens Soniox sessions. Same config as the desktop's stt/soniox.py:
 * pcm_s16le @ sampleRate, language hints, and vocab as context.terms.
 */
class SonioxClient(
    private val apiKey: String,
    private val model: String = "stt-rt-v5",
    private val sampleRate: Int = 16000,
    private val languageHints: List<String> = listOf("en", "zh"),
    private val vocab: List<String> = emptyList(),
) {
    // No pingInterval: Soniox doesn't answer WS pings (it would drop us), and we
    // stream audio continuously anyway, so the connection never goes idle.
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // keep the socket open while streaming
        .build()

    private fun configJson(): String = JSONObject().apply {
        put("api_key", apiKey)
        put("model", model)
        put("language_hints", JSONArray(languageHints))
        put("enable_language_identification", true)
        put("audio_format", "pcm_s16le")
        put("sample_rate", sampleRate)
        put("num_channels", 1)
        if (vocab.isNotEmpty()) {
            put("context", JSONObject().put("terms", JSONArray(vocab)))
        }
    }.toString()

    fun open(onPartial: ((String) -> Unit)? = null): SonioxSession {
        require(apiKey.isNotEmpty()) { "Missing Soniox API key" }
        return SonioxSession(client, configJson(), onPartial)
    }

    /** Convenience for the headless file test: burst a full buffer through a session. */
    fun transcribe(pcm: ByteArray, onPartial: ((String) -> Unit)? = null): String {
        val session = open(onPartial)
        session.feed(pcm, pcm.size)
        val audioSeconds = pcm.size / (2 * sampleRate) // realtime STT ~ audio-duration pace
        return session.finish(audioSeconds + 30L)
    }

    companion object {
        const val WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
    }
}
