package je.yw.typelessless.settings

import android.content.Context
import je.yw.typelessless.BuildConfig

/**
 * API keys stored in the app's private SharedPreferences, falling back to the
 * BuildConfig values injected from local.properties (so dev builds work without
 * re-entering keys). Private storage; encrypted-at-rest is a later hardening.
 */
class Keys(context: Context) {

    private val prefs = context.getSharedPreferences("keys", Context.MODE_PRIVATE)

    fun soniox(): String = prefs.getString(SONIOX, "").orEmpty().ifEmpty { BuildConfig.SONIOX_KEY }
    fun anthropic(): String = prefs.getString(ANTHROPIC, "").orEmpty().ifEmpty { BuildConfig.ANTHROPIC_KEY }

    /** What the user actually typed (empty = using the BuildConfig fallback). */
    fun sonioxRaw(): String = prefs.getString(SONIOX, "").orEmpty()
    fun anthropicRaw(): String = prefs.getString(ANTHROPIC, "").orEmpty()

    fun save(soniox: String, anthropic: String) {
        prefs.edit()
            .putString(SONIOX, soniox.trim())
            .putString(ANTHROPIC, anthropic.trim())
            .apply()
    }

    private companion object {
        const val SONIOX = "soniox"
        const val ANTHROPIC = "anthropic"
    }
}
