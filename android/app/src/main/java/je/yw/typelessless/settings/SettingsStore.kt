package je.yw.typelessless.settings

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Loads/saves the editable settings as JSON in the app's private storage,
 * seeded on first run from the bundled defaults.json (itself copied from the
 * repo's shared/defaults.json). Normalizes exactly like the desktop settings.py.
 */
class SettingsStore(private val context: Context) {

    private val file = File(context.filesDir, "settings.json")

    fun load(): AppSettings {
        if (file.exists()) {
            runCatching { return normalize(parse(file.readText())) }
        }
        // First run (or corrupt): seed from bundled defaults and persist.
        val seeded = normalize(parse(readAsset()))
        write(seeded)
        return seeded
    }

    fun save(s: AppSettings): AppSettings {
        val n = normalize(s)
        write(n)
        return n
    }

    fun resetToDefaults(): AppSettings = save(normalize(parse(readAsset())))

    // --- json <-> model -------------------------------------------------

    private fun readAsset(): String =
        context.assets.open("defaults.json").bufferedReader().use { it.readText() }

    private fun parse(text: String): AppSettings {
        val o = JSONObject(text)
        val modes = ArrayList<Mode>()
        o.optJSONArray("modes")?.let { arr ->
            for (i in 0 until arr.length()) {
                val m = arr.getJSONObject(i)
                modes.add(Mode(m.optString("name"), m.optString("prompt"), m.optBoolean("use_llm", true)))
            }
        }
        val vocab = ArrayList<String>()
        o.optJSONArray("vocab")?.let { arr ->
            for (i in 0 until arr.length()) vocab.add(arr.optString(i))
        }
        val rules = ArrayList<Rule>()
        o.optJSONArray("rules")?.let { arr ->
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                rules.add(Rule(r.optString("match"), r.optString("mode")))
            }
        }
        return AppSettings(
            globalPrompt = o.optString("global_prompt"),
            vocab = vocab,
            defaultMode = o.optString("default_mode"),
            modes = modes,
            rules = rules,
        )
    }

    private fun toJson(s: AppSettings): String {
        val modes = JSONArray()
        for (m in s.modes) {
            modes.put(JSONObject().put("name", m.name).put("prompt", m.prompt).put("use_llm", m.useLlm))
        }
        val rules = JSONArray()
        for (r in s.rules) rules.put(JSONObject().put("match", r.match).put("mode", r.mode))
        return JSONObject()
            .put("global_prompt", s.globalPrompt)
            .put("vocab", JSONArray(s.vocab))
            .put("default_mode", s.defaultMode)
            .put("modes", modes)
            .put("rules", rules)
            .toString(2)
    }

    private fun write(s: AppSettings) {
        runCatching { file.writeText(toJson(s)) }
    }

    /** Dedupe modes, ensure default_mode is valid, drop rules to unknown modes. */
    private fun normalize(s: AppSettings): AppSettings {
        val seen = LinkedHashSet<String>()
        val modes = ArrayList<Mode>()
        for (m in s.modes) {
            val name = m.name.trim()
            if (name.isEmpty() || !seen.add(name)) continue
            modes.add(Mode(name, m.prompt, m.useLlm))
        }
        if (modes.isEmpty()) modes.add(Mode("working", "", true))
        val names = modes.map { it.name }.toSet()

        var default = s.defaultMode.trim()
        if (default !in names) default = modes.first().name

        val rules = s.rules
            .map { Rule(it.match.trim(), it.mode.trim()) }
            .filter { it.match.isNotEmpty() && it.mode in names }

        val vocab = s.vocab.map { it.trim() }.filter { it.isNotEmpty() }

        return AppSettings(s.globalPrompt, vocab, default, modes, rules)
    }
}
