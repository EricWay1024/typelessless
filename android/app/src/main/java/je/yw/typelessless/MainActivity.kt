package je.yw.typelessless

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import je.yw.typelessless.pipeline.ClaudeCleaner
import je.yw.typelessless.pipeline.Prompts
import je.yw.typelessless.pipeline.SonioxClient
import je.yw.typelessless.pipeline.WavReader
import je.yw.typelessless.settings.Keys
import je.yw.typelessless.settings.SettingsStore

/**
 * Launcher / home screen: enable and switch the keyboard, open Settings, and a
 * dev-only pipeline test (bundled WAV → Soniox → Claude) shown on screen and in
 * logcat.
 */
class MainActivity : Activity() {

    private lateinit var result: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Test/launcher screen: keep the display on while it's open (handy on the test phone).
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(64, 110, 64, 64)
        }

        root.addView(TextView(this).apply {
            text = "typelessless"
            textSize = 30f
        })
        root.addView(TextView(this).apply {
            text = "voice dictation keyboard"
            textSize = 14f
            setPadding(0, 16, 0, 40)
        })

        val testField = EditText(this).apply {
            hint = "type / dictate here to test the keyboard"
            textSize = 16f
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES or
                android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
        }
        root.addView(testField)
        // Bring the keyboard up on launch (handy for testing the QWERTY).
        testField.requestFocus()
        testField.post {
            (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager)
                .showSoftInput(testField, InputMethodManager.SHOW_IMPLICIT)
        }

        root.addView(button("Enable keyboard in Settings") {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        })
        root.addView(button("Choose / switch keyboard") {
            imm().showInputMethodPicker()
        })
        root.addView(button("⚙  Settings (modes, prompts, keys, vocab)") {
            startActivity(Intent(this, SettingsActivity::class.java))
        })
        root.addView(button("Run pipeline test (WAV → Soniox → Claude)") {
            runPipelineTest()
        })

        result = TextView(this).apply {
            textSize = 13f
            setPadding(0, 40, 0, 0)
            setTextIsSelectable(true)
        }
        root.addView(result)

        // Headless trigger for dev: `adb shell am start -n .../.MainActivity --ez autotest true`
        if (intent?.getBooleanExtra("autotest", false) == true) runPipelineTest()

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

    private fun runPipelineTest() {
        result.text = "Running… reading WAV, streaming to Soniox, cleaning with Claude."
        Thread {
            try {
                val s = SettingsStore(this).load()
                val keys = Keys(this)
                val modeName = intent?.getStringExtra("mode") ?: s.defaultMode
                val mode = s.modeByName(modeName) ?: s.modes.first()

                val wav = assets.open("test16k.wav").use { WavReader.read(it) }
                val t0 = System.currentTimeMillis()
                val transcript = SonioxClient(apiKey = keys.soniox(), vocab = s.vocab)
                    .transcribe(wav.pcm)
                val t1 = System.currentTimeMillis()
                val cleaned = if (!mode.useLlm || keys.anthropic().isEmpty()) {
                    transcript // passthrough (e.g. chatting) — no LLM
                } else {
                    ClaudeCleaner(keys.anthropic())
                        .clean(transcript, Prompts.system(s.globalPrompt, mode.prompt, s.vocab))
                }
                val t2 = System.currentTimeMillis()

                val msg = buildString {
                    append("mode: ${mode.name}\n")
                    append("WAV: ${wav.sampleRate} Hz, ${wav.channels} ch, ${wav.pcm.size} bytes\n\n")
                    append("── STT  (${t1 - t0} ms) ──\n$transcript\n\n")
                    append("── CLEANED  (${t2 - t1} ms) ──\n$cleaned")
                }
                Log.i(TAG, msg)
                runOnUiThread { result.text = msg }
            } catch (e: Throwable) {
                Log.e(TAG, "pipeline test failed", e)
                runOnUiThread { result.text = "ERROR: ${e.javaClass.simpleName}: ${e.message}" }
            }
        }.start()
    }

    private fun button(label: String, onClick: () -> Unit) =
        Button(this).apply {
            text = label
            setOnClickListener { onClick() }
        }

    private fun imm() = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager

    private companion object {
        const val TAG = "typelessless"
    }
}
