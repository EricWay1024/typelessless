package je.yw.typelessless

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import je.yw.typelessless.settings.AppSettings
import je.yw.typelessless.settings.Keys
import je.yw.typelessless.settings.Mode
import je.yw.typelessless.settings.Rule
import je.yw.typelessless.settings.SettingsStore

/**
 * Native settings form mirroring the desktop's web Settings UI: API keys, global
 * prompt, per-mode prompts (add/remove), vocabulary, default mode, and app→mode
 * routing rules. Saving normalizes via SettingsStore, exactly like the desktop.
 */
class SettingsActivity : Activity() {

    private class ModeRow(val card: View, val name: EditText, val prompt: EditText)

    private lateinit var store: SettingsStore
    private lateinit var keys: Keys

    private lateinit var sonioxEdit: EditText
    private lateinit var anthropicEdit: EditText
    private lateinit var defaultEdit: EditText
    private lateinit var vocabEdit: EditText
    private lateinit var globalEdit: EditText
    private lateinit var rulesEdit: EditText
    private lateinit var modesContainer: LinearLayout
    private val modeRows = mutableListOf<ModeRow>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SettingsStore(this)
        keys = Keys(this)
        val s = store.load()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(40))
        }

        root.addView(TextView(this).apply {
            text = "typelessless settings"
            textSize = 24f
            setTypeface(typeface, Typeface.BOLD)
        })

        header(root, "API keys")
        sonioxEdit = singleLine(keys.sonioxRaw(), "Soniox key" + fallbackHint(keys.sonioxRaw()))
        root.addView(sonioxEdit)
        anthropicEdit = singleLine(keys.anthropicRaw(), "Anthropic key" + fallbackHint(keys.anthropicRaw()))
        root.addView(anthropicEdit)

        header(root, "Default mode")
        defaultEdit = singleLine(s.defaultMode, "e.g. working")
        root.addView(defaultEdit)

        header(root, "Vocabulary (one term per line)")
        vocabEdit = multiLine(s.vocab.joinToString("\n"), 3)
        root.addView(vocabEdit)

        header(root, "Global prompt (prepended to every mode)")
        globalEdit = multiLine(s.globalPrompt, 5)
        root.addView(globalEdit)

        header(root, "Modes")
        modesContainer = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(modesContainer)
        for (m in s.modes) addModeCard(m.name, m.prompt)
        root.addView(Button(this).apply {
            text = "+ Add mode"
            setOnClickListener { addModeCard("", "") }
        })

        header(root, "App → mode rules (one per line:  pattern = mode)")
        root.addView(TextView(this).apply {
            text = "Matches the focused app's package, e.g.  com.google.android.gm = working"
            textSize = 12f
            setTextColor(Color.GRAY)
        })
        rulesEdit = multiLine(s.rules.joinToString("\n") { "${it.match} = ${it.mode}" }, 3)
        root.addView(rulesEdit)

        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(24), 0, 0)
        }
        buttons.addView(Button(this).apply {
            text = "Save"
            setOnClickListener { save() }
        })
        buttons.addView(Button(this).apply {
            text = "Reset to defaults"
            setOnClickListener { resetToDefaults() }
        })
        root.addView(buttons)

        setContentView(
            ScrollView(this).apply {
                addView(
                    root,
                    ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                    ),
                )
            },
        )
    }

    // --- save / reset ---------------------------------------------------

    private fun save() {
        keys.save(sonioxEdit.text.toString(), anthropicEdit.text.toString())

        val modes = modeRows
            .map { Mode(it.name.text.toString().trim(), it.prompt.text.toString(), true) }
            .filter { it.name.isNotEmpty() }

        val vocab = vocabEdit.text.toString().split("\n")
        val rules = rulesEdit.text.toString().split("\n").mapNotNull { line ->
            val i = line.indexOf('=')
            if (i < 0) return@mapNotNull null
            val match = line.substring(0, i).trim()
            val mode = line.substring(i + 1).trim()
            if (match.isEmpty() || mode.isEmpty()) null else Rule(match, mode)
        }

        val saved = store.save(
            AppSettings(
                globalPrompt = globalEdit.text.toString(),
                vocab = vocab,
                defaultMode = defaultEdit.text.toString().trim(),
                modes = modes,
                rules = rules,
            ),
        )
        Toast.makeText(this, "Saved (${saved.modes.size} modes, default: ${saved.defaultMode})", Toast.LENGTH_SHORT).show()
        finish()
    }

    private fun resetToDefaults() {
        store.resetToDefaults()
        keys.save("", "")
        Toast.makeText(this, "Reset to defaults", Toast.LENGTH_SHORT).show()
        recreate()
    }

    // --- mode cards -----------------------------------------------------

    private fun addModeCard(name: String, prompt: String) {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(12), dp(12), dp(12))
            setBackgroundColor(Color.parseColor("#14808080"))
        }
        (card.layoutParams as? LinearLayout.LayoutParams
            ?: LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )).also {
            it.topMargin = dp(8)
            card.layoutParams = it
        }

        val nameEdit = singleLine(name, "mode name")
        val promptEdit = multiLine(prompt, 4)

        val headerRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        headerRow.addView(nameEdit, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val row = ModeRow(card, nameEdit, promptEdit)
        headerRow.addView(Button(this).apply {
            text = "Delete"
            setOnClickListener {
                modesContainer.removeView(card)
                modeRows.remove(row)
            }
        })

        card.addView(headerRow)
        card.addView(promptEdit)
        modesContainer.addView(card)
        modeRows.add(row)
    }

    // --- view helpers ---------------------------------------------------

    private fun header(parent: LinearLayout, title: String) {
        parent.addView(TextView(this).apply {
            text = title
            textSize = 15f
            setTypeface(typeface, Typeface.BOLD)
            setPadding(0, dp(22), 0, dp(6))
        })
    }

    private fun singleLine(value: String, hint: String): EditText =
        EditText(this).apply {
            setText(value)
            this.hint = hint
            inputType = InputType.TYPE_CLASS_TEXT
            textSize = 14f
        }

    private fun multiLine(value: String, minLines: Int): EditText =
        EditText(this).apply {
            setText(value)
            inputType = InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            gravity = Gravity.TOP or Gravity.START
            setMinLines(minLines)
            isVerticalScrollBarEnabled = true
            textSize = 14f
        }

    private fun fallbackHint(raw: String): String =
        if (raw.isEmpty()) "  (using built-in dev key)" else ""

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
}
