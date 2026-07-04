package je.yw.typelessless.pipeline

/** Builds the cached cleanup system prompt, matching the desktop's ClaudeCleaner. */
object Prompts {

    /** global prompt + mode prompt + a vocab-normalization line. */
    fun system(globalPrompt: String, modePrompt: String, vocab: List<String>): String {
        val base = (globalPrompt.trim() + "\n\n" + modePrompt.trim()).trim()
        if (vocab.isEmpty()) return base
        return base + "\n\n" +
            "Preferred spellings for domain terms (normalize to these when clearly intended): " +
            vocab.joinToString(", ") + "."
    }
}
