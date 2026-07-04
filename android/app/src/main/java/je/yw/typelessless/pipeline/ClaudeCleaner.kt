package je.yw.typelessless.pipeline

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Cleanup via Claude — the Kotlin twin of cleanup/claude.py. A single
 * /v1/messages POST with a cached system prompt (mode prompt + vocab line) and
 * the transcript as the user turn. Raw OkHttp keeps the APK small; the request
 * shape matches the desktop byte-for-byte. Call it off the main thread.
 */
class ClaudeCleaner(
    private val apiKey: String,
    private val model: String = "claude-haiku-4-5",
) {
    private val client = OkHttpClient.Builder()
        .callTimeout(60, TimeUnit.SECONDS)
        .build()

    fun clean(text: String, systemPrompt: String): String {
        val t = text.trim()
        if (t.isEmpty()) return ""
        require(apiKey.isNotEmpty()) { "Missing Anthropic API key" }

        val system = JSONArray().put(
            JSONObject()
                .put("type", "text")
                .put("text", systemPrompt)
                .put("cache_control", JSONObject().put("type", "ephemeral")),
        )
        // Wrap the transcript so the model treats it strictly as data, not as
        // instructions addressed to it (see the global prompt's <transcript> rule).
        val messages = JSONArray().put(
            JSONObject().put("role", "user").put("content", "<transcript>\n$t\n</transcript>"),
        )
        val body = JSONObject()
            .put("model", model)
            .put("max_tokens", 2048)
            .put("temperature", 0) // cleanup is a deterministic transform; curbs no-translate drift
            .put("system", system)
            .put("messages", messages)
            .toString()
            .toRequestBody("application/json".toMediaType())

        val req = Request.Builder()
            .url("https://api.anthropic.com/v1/messages")
            .header("x-api-key", apiKey)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .post(body)
            .build()

        client.newCall(req).execute().use { resp ->
            val respBody = resp.body?.string() ?: ""
            if (!resp.isSuccessful) throw RuntimeException("Claude HTTP ${resp.code}: $respBody")
            val content = JSONObject(respBody).optJSONArray("content") ?: return t
            val sb = StringBuilder()
            for (i in 0 until content.length()) {
                val block = content.getJSONObject(i)
                if (block.optString("type") == "text") sb.append(block.optString("text"))
            }
            return sb.toString().trim().ifEmpty { t }
        }
    }
}
