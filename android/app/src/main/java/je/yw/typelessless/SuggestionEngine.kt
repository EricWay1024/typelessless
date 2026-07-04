package je.yw.typelessless

import android.content.Context

/**
 * Lightweight English suggestions: prefix completion + Norvig-style edit-1
 * spelling correction, ranked by a bundled frequency list (words_en.txt, ordered
 * most-frequent first). Load once off the main thread; suggest() is cheap.
 */
class SuggestionEngine {

    data class Result(val candidates: List<String>, val autoCorrect: String?)

    @Volatile private var words: List<String> = emptyList()
    @Volatile private var rank: Map<String, Int> = emptyMap()
    @Volatile private var dict: Set<String> = emptySet()

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

    /** Candidates to display (typed word first) and an optional autocorrect target. */
    fun suggest(typed: String): Result {
        if (typed.isEmpty() || words.isEmpty()) return Result(emptyList(), null)
        val lower = typed.lowercase()
        val inDict = lower in dict
        val comps = complete(lower, 6)
        val corrs = if (inDict) emptyList() else correct(lower, 3)

        val ordered = LinkedHashSet<String>()
        ordered.add(typed) // always keep what you typed
        if (!inDict) for (c in corrs) ordered.add(matchCase(typed, c))
        for (c in comps) ordered.add(matchCase(typed, c))

        val candidates = ordered.take(3).toList()
        val auto = if (!inDict && corrs.isNotEmpty()) matchCase(typed, corrs[0]) else null
        return Result(candidates, auto)
    }

    fun isWord(w: String): Boolean = w.lowercase() in dict

    // --- internals ------------------------------------------------------

    private fun complete(prefix: String, limit: Int): List<String> {
        val res = ArrayList<String>(limit)
        for (w in words) {
            if (w.length > prefix.length && w.startsWith(prefix)) {
                res.add(w)
                if (res.size >= limit) break
            }
        }
        return res
    }

    private fun correct(word: String, limit: Int): List<String> =
        edits1(word)
            .asSequence()
            .filter { it != word && it in dict }
            .sortedBy { rank[it] ?: Int.MAX_VALUE }
            .take(limit)
            .toList()

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
