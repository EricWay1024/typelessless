package je.yw.typelessless

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.inputmethodservice.InputMethodService
import android.inputmethodservice.Keyboard
import android.inputmethodservice.KeyboardView
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.text.TextUtils
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import je.yw.typelessless.pipeline.AudioCapture
import je.yw.typelessless.pipeline.ClaudeCleaner
import je.yw.typelessless.pipeline.Prompts
import je.yw.typelessless.pipeline.SonioxClient
import je.yw.typelessless.pipeline.SonioxSession
import je.yw.typelessless.settings.AppSettings
import je.yw.typelessless.settings.Keys
import je.yw.typelessless.settings.SettingsStore
import java.util.concurrent.Executors

/**
 * The typelessless keyboard: a QWERTY (with long-press numbers/symbols) plus a
 * dictation bar. Tap 🎤 to dictate — the keyboard area shows the live transcript,
 * and on stop the cleaned text is inserted. Mode auto-selects by focused app.
 */
class TypelesslessImeService : InputMethodService(), KeyboardView.OnKeyboardActionListener {

    private enum class State { IDLE, RECORDING, PROCESSING }

    // dictation UI
    private lateinit var status: TextView
    private lateinit var scroller: ScrollView
    private lateinit var mic: ImageView
    private lateinit var modeChip: Button

    // typing UI
    private lateinit var keyboardView: LatinKeyboardView
    private lateinit var qwerty: Keyboard
    private lateinit var symbols: Keyboard
    private var symbolsShown = false
    private var shifted = false
    private var capsLock = false
    private var lastShiftTime = 0L
    private var lastSpaceTime = 0L

    // suggestions / composing
    private val suggest = SuggestionEngine()
    private val composing = StringBuilder()
    private var currentSuggestion: SuggestionEngine.Result? = null
    private lateinit var controlsRow: LinearLayout
    private lateinit var suggestionRow: LinearLayout
    private val candViews = ArrayList<TextView>(3)

    private val main = Handler(Looper.getMainLooper())
    private val work = Executors.newSingleThreadExecutor()

    private lateinit var store: SettingsStore
    private lateinit var keys: Keys
    private lateinit var settings: AppSettings
    private var activeMode: String = "working"

    private var state = State.IDLE
    private var capture: AudioCapture? = null
    private var session: SonioxSession? = null

    override fun onCreate() {
        super.onCreate()
        store = SettingsStore(this)
        keys = Keys(this)
        settings = store.load()
        activeMode = settings.defaultMode
        qwerty = Keyboard(this, R.xml.qwerty)
        symbols = Keyboard(this, R.xml.symbols)
        Thread { runCatching { suggest.load(applicationContext) } }.start()
    }

    override fun onCreateInputView(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BG)
        }

        // --- top strip: controls (mode · mic · 🌐 · ⚙), swapped for word suggestions while typing ---
        controlsRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10), dp(4), dp(10), dp(4))
        }
        modeChip = Button(this).apply {
            text = activeMode
            textSize = 13f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = GradientDrawable().apply {
                cornerRadius = dp(16).toFloat()
                setColor(Color.parseColor("#3A3A3C"))
            }
            minWidth = 0
            minimumWidth = 0
            setPadding(dp(18), dp(6), dp(18), dp(6))
            setOnClickListener { cycleMode() }
        }
        controlsRow.addView(modeChip)
        controlsRow.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f)) // spacer
        mic = iconView(R.drawable.ic_mic) { onMicTap() }
        controlsRow.addView(mic)
        controlsRow.addView(
            iconView(R.drawable.ic_language) {
                if (!switchToPreviousImeCompat()) imm().showInputMethodPicker()
            }.apply { setOnLongClickListener { imm().showInputMethodPicker(); true } },
        )
        controlsRow.addView(iconView(R.drawable.ic_settings) { openSettings() })

        suggestionRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            visibility = View.GONE
            setPadding(dp(6), dp(2), dp(6), dp(2))
        }
        for (i in 0 until 3) {
            val tv = TextView(this).apply {
                gravity = Gravity.CENTER
                setTextColor(Color.parseColor("#CCCCCC"))
                textSize = 15f
                maxLines = 1
                ellipsize = TextUtils.TruncateAt.END
                setPadding(dp(6), dp(10), dp(6), dp(10))
                isClickable = true
                setOnClickListener { onCandidate(i) }
            }
            candViews.add(tv)
            suggestionRow.addView(tv, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        }

        val topStrip = FrameLayout(this)
        topStrip.addView(controlsRow)
        topStrip.addView(suggestionRow)
        root.addView(topStrip)

        // --- content: keyboard, swapped for the transcript while recording ---
        val content = FrameLayout(this)

        keyboardView = (layoutInflater.inflate(R.layout.keyboard_view, content, false) as LatinKeyboardView).apply {
            keyboard = qwerty
            isPreviewEnabled = false
            setOnKeyboardActionListener(this@TypelesslessImeService)
            onLongPressChar = { c -> currentInputConnection?.commitText(c.toString(), 1) }
        }
        content.addView(keyboardView)

        status = TextView(this).apply {
            text = ""
            setTextColor(Color.WHITE)
            textSize = 17f
            setLineSpacing(0f, 1.12f)
            gravity = Gravity.TOP
            setPadding(dp(14), dp(10), dp(14), dp(10))
        }
        scroller = ScrollView(this).apply {
            visibility = View.GONE
            addView(status)
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                qwerty.height, // match the keyboard's height so nothing jumps
            )
        }
        content.addView(scroller)
        root.addView(content)

        return root
    }

    override fun onStartInputView(editorInfo: EditorInfo, restarting: Boolean) {
        super.onStartInputView(editorInfo, restarting)
        settings = store.load()
        composing.setLength(0)
        clearSuggestions()
        if (state == State.IDLE) {
            activeMode = settings.pickMode(editorInfo.packageName)
            updateModeChip()
            // reset to letters, unshifted
            symbolsShown = false
            shifted = false
            capsLock = false
            if (::keyboardView.isInitialized) {
                keyboardView.keyboard = qwerty
                applyShift()
                showKeyboard()
                updateAutoCaps()
            }
        }
    }

    override fun onFinishInput() {
        composing.setLength(0)
        clearSuggestions()
        super.onFinishInput()
    }

    override fun onUpdateSelection(
        oldSelStart: Int,
        oldSelEnd: Int,
        newSelStart: Int,
        newSelEnd: Int,
        candidatesStart: Int,
        candidatesEnd: Int,
    ) {
        super.onUpdateSelection(
            oldSelStart, oldSelEnd, newSelStart, newSelEnd, candidatesStart, candidatesEnd,
        )
        // The composing region was dropped (cursor moved away); reset our state.
        if (composing.isNotEmpty() && candidatesStart == -1) {
            composing.setLength(0)
            clearSuggestions()
        }
    }

    // --- typing (KeyboardView.OnKeyboardActionListener) ------------------

    override fun onKey(primaryCode: Int, keyCodes: IntArray?) {
        val ic = currentInputConnection ?: return
        when (primaryCode) {
            0 -> Unit // spacer key
            Keyboard.KEYCODE_SHIFT -> handleShift()
            Keyboard.KEYCODE_DELETE -> handleDelete(ic)
            Keyboard.KEYCODE_DONE -> handleEnter(ic)
            Keyboard.KEYCODE_MODE_CHANGE -> toggleSymbols()
            32 -> handleSpace(ic)
            else -> {
                if (Character.isLetter(primaryCode)) {
                    val ch = if (shifted || capsLock) {
                        Character.toUpperCase(primaryCode).toChar()
                    } else {
                        primaryCode.toChar()
                    }
                    composing.append(ch)
                    ic.setComposingText(composing, 1)
                    if (shifted && !capsLock) { shifted = false; applyShift() }
                    updateSuggestions()
                } else {
                    finishComposing(ic)
                    ic.commitText(primaryCode.toChar().toString(), 1)
                    updateAutoCaps()
                }
            }
        }
    }

    private fun handleDelete(ic: android.view.inputmethod.InputConnection) {
        if (composing.isNotEmpty()) {
            composing.setLength(composing.length - 1)
            if (composing.isEmpty()) {
                ic.finishComposingText()
                clearSuggestions()
                updateAutoCaps()
            } else {
                ic.setComposingText(composing, 1)
                updateSuggestions()
            }
        } else {
            val sel = ic.getSelectedText(0)
            if (!sel.isNullOrEmpty()) ic.commitText("", 1) else ic.deleteSurroundingText(1, 0)
            updateAutoCaps()
        }
    }

    private fun handleSpace(ic: android.view.inputmethod.InputConnection) {
        // Finish the current word (autocorrecting if we have a strong suggestion).
        if (composing.isNotEmpty()) {
            currentSuggestion?.autoCorrect?.let { ic.setComposingText(it, 1) }
            ic.finishComposingText()
            composing.setLength(0)
            clearSuggestions()
            ic.commitText(" ", 1)
            lastSpaceTime = SystemClock.uptimeMillis()
            updateAutoCaps()
            return
        }
        // No word in progress: double-space inserts ". " (Gboard behavior).
        val now = SystemClock.uptimeMillis()
        val before = ic.getTextBeforeCursor(2, 0)
        if (now - lastSpaceTime < 400 && before != null && before.length == 2 &&
            before[1] == ' ' && Character.isLetterOrDigit(before[0])
        ) {
            ic.deleteSurroundingText(1, 0)
            ic.commitText(". ", 1)
            lastSpaceTime = 0
        } else {
            ic.commitText(" ", 1)
            lastSpaceTime = now
        }
        updateAutoCaps()
    }

    // --- suggestions ----------------------------------------------------

    private fun updateSuggestions() {
        if (!::suggestionRow.isInitialized) return
        val word = composing.toString()
        if (word.isEmpty()) { clearSuggestions(); return }
        val res = suggest.suggest(word)
        currentSuggestion = res
        if (res.candidates.size >= 2 || res.autoCorrect != null) showSuggestions(res) else clearSuggestions()
    }

    private fun showSuggestions(res: SuggestionEngine.Result) {
        for (i in 0 until candViews.size) {
            val tv = candViews[i]
            val c = res.candidates.getOrNull(i)
            if (c == null) {
                tv.text = ""
                tv.visibility = View.INVISIBLE
            } else {
                tv.text = c
                tv.visibility = View.VISIBLE
                val auto = res.autoCorrect != null && c == res.autoCorrect
                tv.setTypeface(null, if (auto) Typeface.BOLD else Typeface.NORMAL)
                tv.setTextColor(if (auto) Color.WHITE else Color.parseColor("#CCCCCC"))
            }
        }
        suggestionRow.visibility = View.VISIBLE
        controlsRow.visibility = View.GONE
    }

    private fun clearSuggestions() {
        currentSuggestion = null
        if (::suggestionRow.isInitialized) {
            suggestionRow.visibility = View.GONE
            controlsRow.visibility = View.VISIBLE
        }
    }

    private fun finishComposing(ic: android.view.inputmethod.InputConnection) {
        if (composing.isNotEmpty()) {
            ic.finishComposingText()
            composing.setLength(0)
        }
        clearSuggestions()
    }

    private fun onCandidate(index: Int) {
        val ic = currentInputConnection ?: return
        val cand = currentSuggestion?.candidates?.getOrNull(index) ?: return
        ic.setComposingText(cand, 1)
        ic.finishComposingText()
        ic.commitText(" ", 1)
        composing.setLength(0)
        clearSuggestions()
        lastSpaceTime = SystemClock.uptimeMillis()
        updateAutoCaps()
    }

    /** Auto-capitalize at sentence starts when the field asks for it. */
    private fun updateAutoCaps() {
        if (capsLock || symbolsShown) return
        val ic = currentInputConnection ?: return
        val ei = currentInputEditorInfo ?: return
        val want = ic.getCursorCapsMode(ei.inputType) != 0
        if (want != shifted) {
            shifted = want
            applyShift()
        }
    }

    private fun handleShift() {
        val now = SystemClock.uptimeMillis()
        when {
            capsLock -> { capsLock = false; shifted = false }
            shifted -> if (now - lastShiftTime < 300) { capsLock = true; shifted = false } else shifted = false
            else -> shifted = true
        }
        lastShiftTime = now
        applyShift()
    }

    /** Reflect the shift/caps state in the letter key labels. */
    private fun applyShift() {
        if (symbolsShown) return
        val up = shifted || capsLock
        qwerty.isShifted = up
        for (k in qwerty.keys) {
            val lbl = k.label
            if (lbl != null && lbl.length == 1 && Character.isLetter(lbl[0])) {
                k.label = if (up) lbl.toString().uppercase() else lbl.toString().lowercase()
            }
        }
        keyboardView.invalidateAllKeys()
    }

    private fun toggleSymbols() {
        currentInputConnection?.let { finishComposing(it) }
        symbolsShown = !symbolsShown
        shifted = false
        capsLock = false
        keyboardView.keyboard = if (symbolsShown) symbols else qwerty
        keyboardView.invalidateAllKeys()
    }

    private fun handleEnter(ic: android.view.inputmethod.InputConnection) {
        finishComposing(ic)
        val ei = currentInputEditorInfo
        val action = (ei?.imeOptions ?: 0) and EditorInfo.IME_MASK_ACTION
        val noEnter = ((ei?.imeOptions ?: 0) and EditorInfo.IME_FLAG_NO_ENTER_ACTION) != 0
        if (!noEnter && action != EditorInfo.IME_ACTION_NONE && action != EditorInfo.IME_ACTION_UNSPECIFIED) {
            ic.performEditorAction(action)
        } else {
            ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER))
            ic.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER))
        }
    }

    override fun onPress(primaryCode: Int) {
        // Custom preview bubble only for character keys (not space/shift/delete/enter/?123).
        if (primaryCode > 32) keyboardView.showPreview(primaryCode) else keyboardView.hidePreview()
    }
    override fun onRelease(primaryCode: Int) {
        keyboardView.hidePreview()
    }
    override fun onText(text: CharSequence?) {}
    override fun swipeLeft() {}
    override fun swipeRight() {}
    override fun swipeUp() {}
    override fun swipeDown() {}

    // --- mode -----------------------------------------------------------

    private fun cycleMode() {
        if (state != State.IDLE) return
        val names = settings.modes.map { it.name }
        if (names.isEmpty()) return
        val idx = names.indexOf(activeMode)
        activeMode = names[(idx + 1) % names.size]
        updateModeChip()
    }

    private fun updateModeChip() {
        if (::modeChip.isInitialized) modeChip.text = activeMode
    }

    // --- dictation ------------------------------------------------------

    private fun onMicTap() {
        when (state) {
            State.PROCESSING -> Unit
            State.RECORDING -> stopRecording()
            State.IDLE -> {
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
                    PackageManager.PERMISSION_GRANTED
                ) {
                    showTranscript()
                    showStatus("Grant mic permission, then tap 🎤 again")
                    startActivity(
                        Intent(this, PermissionActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                    return
                }
                startRecording()
            }
        }
    }

    private fun startRecording() {
        val sonioxKey = keys.soniox()
        if (sonioxKey.isEmpty()) {
            showTranscript(); showStatus("No Soniox key — set it in Settings"); return
        }
        state = State.RECORDING
        setMicBg(REC)
        showTranscript()
        showStatus("Listening…")

        val s = SonioxClient(apiKey = sonioxKey, vocab = settings.vocab).open { partial ->
            main.post { if (state == State.RECORDING) showStatus(partial.ifEmpty { "Listening…" }) }
        }
        session = s

        val c = AudioCapture()
        capture = c
        c.start(
            onPcm = { buf, len -> s.feed(buf, len) },
            onError = { e -> main.post { fail("Mic error: ${e.message}") } },
        )
    }

    private fun stopRecording() {
        state = State.PROCESSING
        setMicBg(PROC)
        showStatus("Cleaning…")

        val c = capture; capture = null
        val s = session; session = null
        c?.stop()

        val mode = settings.modeByName(activeMode)
        val anthropicKey = keys.anthropic()

        work.execute {
            try {
                val transcript = s?.finish(20L).orEmpty()
                if (transcript.isBlank()) { main.post { resetIdle() }; return@execute }
                val cleaned = if (mode == null || !mode.useLlm || anthropicKey.isEmpty()) {
                    transcript
                } else {
                    ClaudeCleaner(anthropicKey)
                        .clean(transcript, Prompts.system(settings.globalPrompt, mode.prompt, settings.vocab))
                }
                main.post {
                    currentInputConnection?.commitText(cleaned, 1)
                    resetIdle()
                }
            } catch (e: Throwable) {
                Log.e(TAG, "dictation failed", e)
                main.post { fail("Error: ${e.message}") }
            }
        }
    }

    private fun resetIdle() {
        state = State.IDLE
        setMicBg(null)
        showStatus("")
        showKeyboard()
    }

    private fun fail(msg: String) {
        capture?.stop(); capture = null
        session?.cancel(); session = null
        state = State.IDLE
        setMicBg(null)
        status.setTextColor(Color.parseColor("#FF8A80"))
        showStatus(msg)
    }

    // --- view helpers ---------------------------------------------------

    private fun showKeyboard() {
        if (::keyboardView.isInitialized) keyboardView.visibility = View.VISIBLE
        if (::scroller.isInitialized) scroller.visibility = View.GONE
    }

    private fun showTranscript() {
        if (::keyboardView.isInitialized) keyboardView.visibility = View.GONE
        if (::scroller.isInitialized) scroller.visibility = View.VISIBLE
        status.setTextColor(Color.WHITE)
    }

    private fun showStatus(text: String) {
        status.text = text
        scroller.post { scroller.fullScroll(View.FOCUS_DOWN) }
    }

    private fun setMicBg(bg: Int?) {
        mic.setBackgroundColor(bg ?: Color.TRANSPARENT)
    }

    private fun iconView(res: Int, onClick: () -> Unit): ImageView =
        ImageView(this).apply {
            setImageResource(res)
            imageTintList = ColorStateList.valueOf(Color.WHITE)
            scaleType = ImageView.ScaleType.CENTER_INSIDE
            setPadding(dp(12), dp(11), dp(12), dp(11))
            layoutParams = LinearLayout.LayoutParams(dp(50), dp(44))
            isClickable = true
            setOnClickListener { onClick() }
        }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun openSettings() {
        startActivity(
            Intent(this, SettingsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    private fun switchToPreviousImeCompat(): Boolean =
        try { switchToPreviousInputMethod() } catch (_: Throwable) { false }

    private fun imm() = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager

    override fun onDestroy() {
        capture?.stop()
        session?.cancel()
        work.shutdownNow()
        super.onDestroy()
    }

    private companion object {
        const val TAG = "typelessless"
        val BG = Color.parseColor("#1E1E1E")
        val REC = Color.parseColor("#E5534B")
        val PROC = Color.parseColor("#C9922B")
    }
}
