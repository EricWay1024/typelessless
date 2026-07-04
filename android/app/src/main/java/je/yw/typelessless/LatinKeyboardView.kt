package je.yw.typelessless

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.inputmethodservice.Keyboard
import android.inputmethodservice.KeyboardView
import android.util.AttributeSet
import android.view.MotionEvent

/**
 * KeyboardView with the Gboard extras plain KeyboardView lacks here:
 *  - long-press inserts the key's popupCharacters (number/symbol);
 *  - each such key shows that char as a small hint in the top-right corner;
 *  - a key-press preview bubble drawn on the canvas (the built-in PopupWindow
 *    preview doesn't render inside an IME). On long-press the bubble switches to
 *    show the symbol being inserted. Hidden reliably on touch-up.
 */
class LatinKeyboardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyle: Int = 0,
) : KeyboardView(context, attrs, defStyle) {

    var onLongPressChar: ((Char) -> Unit)? = null

    private val density = resources.displayMetrics.density

    private val hintPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#99FFFFFF")
        textAlign = Paint.Align.RIGHT
        textSize = 12f * density
    }
    private val previewBg = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#5A5A60") }
    private val previewText = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textAlign = Paint.Align.CENTER
        textSize = 30f * density
    }

    private var previewKey: Keyboard.Key? = null
    private var previewLabel: String? = null

    fun showPreview(code: Int) {
        val key = keyboard?.keys?.firstOrNull { it.codes.isNotEmpty() && it.codes[0] == code } ?: return
        previewKey = key
        previewLabel = key.label?.toString()
        invalidate()
    }

    fun hidePreview() {
        if (previewKey != null) {
            previewKey = null
            previewLabel = null
            invalidate()
        }
    }

    override fun onLongPress(popupKey: Keyboard.Key): Boolean {
        val pc = popupKey.popupCharacters
        if (pc.isNullOrEmpty()) return super.onLongPress(popupKey)
        if (pc.length == 1) {
            // Show the symbol in the bubble, then insert it.
            previewKey = popupKey
            previewLabel = pc[0].toString()
            invalidate()
            onLongPressChar?.invoke(pc[0])
            return true
        }
        hidePreview()
        return try {
            super.onLongPress(popupKey)
        } catch (_: Throwable) {
            onLongPressChar?.invoke(pc[0])
            true
        }
    }

    override fun onTouchEvent(me: MotionEvent): Boolean {
        val handled = super.onTouchEvent(me)
        when (me.actionMasked) {
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL, MotionEvent.ACTION_POINTER_UP -> hidePreview()
        }
        return handled
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val kb = keyboard ?: return

        // Corner hints (primary long-press char).
        val padX = 8f * density
        val baseY = hintPaint.textSize + 6f * density
        for (key in kb.keys) {
            val hint = key.popupCharacters ?: continue
            if (hint.isEmpty()) continue
            canvas.drawText(hint[0].toString(), key.x + key.width - padX, key.y + baseY, hintPaint)
        }

        // Key-press preview bubble.
        val key = previewKey ?: return
        val label = previewLabel ?: return
        val cx = key.x + key.width / 2f
        val w = key.width * 1.12f
        val h = key.height * 0.98f
        var bottom = key.y - 6f * density
        var top = bottom - h
        if (top < 2f * density) { top = 2f * density; bottom = top + h }
        val r = 12f * density
        canvas.drawRoundRect(cx - w / 2f, top, cx + w / 2f, bottom, r, r, previewBg)
        val fm = previewText.fontMetrics
        canvas.drawText(label, cx, (top + bottom) / 2f - (fm.ascent + fm.descent) / 2f, previewText)
    }
}
