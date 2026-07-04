package je.yw.typelessless

import android.content.Context

/**
 * English suggestions: prefix completion + Norvig-style edit-1/edit-2 spelling
 * correction + prefix backoff (so it *always* offers the closest word), ranked
 * by a bundled frequency list (words_en.txt, most-frequent first). Plus a few
 * forced fixes (e.g. standalone "i" -> "I"). Load once off the main thread.
 */
class SuggestionEngine {

    data class Result(val candidates: List<String>, val autoCorrect: String?)

    @Volatile private var words: List<String> = emptyList()
    @Volatile private var rank: Map<String, Int> = emptyMap()
    @Volatile private var dict: Set<String> = emptySet()

    private val forced = mapOf("i" to "I", "im" to "I'm", "ive" to "I've", "id" to "I'd", "ill" to "I'll")

    val isReady: Boolean get() = words.isNotEmpty()

    fun load(context: Context) {
        val list = context.assets.open("words_en.txt").bufferedReader().useLines { seq ->
            seq.map { it.trim() }.filter { it.isNotEmpty() }.toList()
        }
        val r = HashMap<String, Int>(list.size * 2)
        for ((i, w) in list.withIndex()) if (w !in r) r[w] = i
        words = list
        rank = r
        dict = r.keys
    }

    fun isWord(w: String): Boolean = w.lowercase() in dict

    /** Candidates to display (typed word first) + an optional autocorrect target. */
    fun suggest(typed: String): Result {
        if (typed.isEmpty() || words.isEmpty()) return Result(emptyList(), null)
        val lower = typed.lowercase()

        // Forced fixes (e.g. standalone "i" -> "I").
        forced[lower]?.let { f ->
            val cands = LinkedHashSet<String>()
            cands.add(f)
            complete(lower, 4).forEach { cands.add(it.replaceFirstChar { c -> c.uppercaseChar() }) }
            return Result(cands.take(3).toList(), f)
        }

        val inDict = lower in dict
        val corr1 = if (inDict) emptyList() else correct(lower, 2, 3) // edit-1, then edit-2 if short
        val comps = complete(lower, 8)

        val pool = LinkedHashSet<String>()
        if (!inDict) corr1.forEach { pool.add(it) }
        comps.forEach { pool.add(it) }
        // Always offer *something*: back off to completions of shorter prefixes.
        var k = lower.length - 1
        while (k >= 2 && pool.size < 4) {
            complete(lower.substring(0, k), 3).forEach { pool.add(it) }
            k--
        }

        val candidates = LinkedHashSet<String>()
        candidates.add(typed) // always keep what you typed
        pool.forEach { candidates.add(matchCase(typed, it)) }

        val auto = if (!inDict && corr1.isNotEmpty()) matchCase(typed, corr1[0]) else null
        return Result(candidates.take(3).toList(), auto)
    }

    // --- internals ------------------------------------------------------

    private fun complete(prefix: String, limit: Int): List<String> {
        if (prefix.isEmpty()) return emptyList()
        val res = ArrayList<String>(limit)
        for (w in words) {
            if (w.length > prefix.length && w.startsWith(prefix)) {
                res.add(w)
                if (res.size >= limit) break
            }
        }
        return res
    }

    /** Best in-dictionary corrections within [maxEdits] edits, ranked by frequency. */
    private fun correct(word: String, maxEdits: Int, limit: Int): List<String> {
        val e1 = edits1(word)
        val valid = LinkedHashSet<String>()
        for (w in e1) if (w != word && w in dict) valid.add(w)
        if (valid.isEmpty() && maxEdits >= 2 && word.length in 2..11) {
            for (w in e1) for (w2 in edits1(w)) if (w2 != word && w2 in dict) valid.add(w2)
        }
        return valid.sortedBy { rank[it] ?: Int.MAX_VALUE }.take(limit)
    }

    private fun edits1(w: String): Set<String> {
        val res = HashSet<String>()
        val letters = "abcdefghijklmnopqrstuvwxyz"
        val n = w.length
        for (i in 0 until n) res.add(w.substring(0, i) + w.substring(i + 1)) // delete
        for (i in 0 until n - 1) {
            res.add(w.substring(0, i) + w[i + 1] + w[i] + w.substring(i + 2)) // transpose
        }
        for (i in 0 until n) for (c in letters) {
            res.add(w.substring(0, i) + c + w.substring(i + 1)) // replace
        }
        for (i in 0..n) for (c in letters) {
            res.add(w.substring(0, i) + c + w.substring(i)) // insert
        }
        return res
    }

    private fun matchCase(typed: String, word: String): String = when {
        typed.length > 1 && typed.all { it.isUpperCase() } -> word.uppercase()
        typed.isNotEmpty() && typed[0].isUpperCase() -> word.replaceFirstChar { it.uppercaseChar() }
        else -> word
    }
}
