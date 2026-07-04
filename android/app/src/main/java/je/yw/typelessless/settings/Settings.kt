package je.yw.typelessless.settings

/** A dictation mode: a name and its cleanup prompt. Mirrors the desktop Mode. */
data class Mode(
    val name: String,
    val prompt: String,
    val useLlm: Boolean = true,
)

/** An app→mode routing rule: if the focused app's package contains [match], use [mode]. */
data class Rule(
    val match: String,
    val mode: String,
)

/** The full editable settings, mirroring the desktop settings.json schema. */
data class AppSettings(
    val globalPrompt: String,
    val vocab: List<String>,
    val defaultMode: String,
    val modes: List<Mode>,
    val rules: List<Rule>,
) {
    fun modeByName(name: String): Mode? = modes.firstOrNull { it.name == name }

    /** Mode for a focused app package: first matching rule, else the default. */
    fun pickMode(pkg: String?): String {
        if (pkg != null) {
            for (r in rules) {
                if (r.match.isNotEmpty() && pkg.contains(r.match, ignoreCase = true)) return r.mode
            }
        }
        return defaultMode
    }
}
