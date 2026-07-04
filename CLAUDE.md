# CLAUDE.md — working notes for this repo

typelessless is a self-owned voice-dictation tool: **cloud STT (Soniox realtime)
→ LLM cleanup (Claude Haiku) → insert text**. Two clients share one provider
contract, reimplemented (not shared code) in each:

- **Desktop** — `src/typelessless/` (Python), a Windows tray app: global hotkey →
  record → clean → paste. Packaged with PyInstaller (`build.ps1`).
- **Android** — `android/` (Kotlin), a custom keyboard (IME) with a mic button.
  See `docs/android-plan.md`.

## Architecture / conventions

- Provider code sits behind interfaces (STT client/session, Cleaner). Swapping a
  provider is a parallel edit in both clients, not a rethink.
- **`shared/defaults.json` is the single source of truth** for the global prompt,
  modes, and vocab. It's generated from `src/typelessless/settings.py` and copied
  into the Android assets by a Gradle task. Edit prompts in `settings.py`,
  regenerate — don't hand-maintain two copies.
- Config split: `config.toml` (system settings + API keys; hand-edited;
  **gitignored, never committed**) vs `settings.json` in the app data dir
  (user-editable via the Settings UI: modes/prompts/vocab/rules). Settings **seed
  once** from defaults; changed bundled defaults don't reach existing users until
  they use "Reset to defaults".
- Bring-your-own-keys. Never commit keys; `config.example.toml` keeps them blank.

## Prompt design (learned the hard way)

- **Cleanup runs at `temperature=0`.** At the default (1.0) Haiku drifts and will
  occasionally *translate* mid-sentence — violating the core no-translate rule.
  Temp 0 makes the transform deterministic and faithful.
- **Frame cleanup as a text function, not a chat assistant, and wrap the
  transcript in `<transcript>…</transcript>`.** Otherwise the model breaks
  character on clean / greeting / instruction-like input ("I'm a transcript
  cleaner, there's nothing to clean…") or obeys injected instructions. The global
  prompt forbids refusing/explaining/replying; the transcript is passed as
  delimited data.
- **No-translate is absolute — even in the most aggressive `polish` mode.** A
  span's *language* is not a "word choice" that rewriting may change: English
  clauses stay English, Chinese stays Chinese; never pick one matrix language.
- **`chatting` mode is `use_llm: false`** — Soniox output is already
  punctuated/segmented, so casual chat skips the LLM (saves a call, keeps natural
  disfluencies).
- Modes are self-contained (each level inlines the lower levels' edits) so they
  don't depend on one another.

## Soniox realtime STT gotchas

- **Do NOT set OkHttp `pingInterval`** — Soniox doesn't answer WebSocket pings and
  drops the connection after the interval. We stream audio continuously, so the
  socket never idles.
- **Handle WebSocket `onClosing`** — Soniox closes the stream when done; without
  handling it the client hangs after the transcript is complete.
- Final tokens arrive at ~audio-duration pace. A burst file-test must scale its
  timeout with clip length; the live path only waits for the short tail after the
  `""` end-of-stream marker.

## Desktop (Python) notes

- Frozen PyInstaller entry runs as top-level `__main__` → use **absolute
  imports** (`from typelessless.x import …`), never relative.
- `pynput` key suppression: `suppress_event()` raises inside the filter *before*
  callbacks, so handle the key IN the `win32_event_filter`, not in `on_press`.
- Win32 UI is pure ctypes (overlay, Core Audio mute, foreground detection) to
  avoid bundling tkinter.

## Android (Kotlin) notes

- Build with the **Gradle wrapper** (`./gradlew`); needs a real **JDK 17** (a
  default `java` may be a JRE without `javac` — pin `org.gradle.java.home`).
  compileSdk 36 / minSdk 26.
- The keyboard uses the classic (deprecated but reliable) `KeyboardView`:
  - **Long-press needs `android:popupLayout` set on the KeyboardView**, else
    `onLongPress` is never called (`if (mPopupLayout == 0) return false`).
  - The **built-in key-preview PopupWindow doesn't render inside an IME** — draw
    the preview on the canvas in `onDraw` instead.
  - KeyboardView **skips `onRelease` after a long-press aborts the key** — hide
    transient UI on `onTouchEvent` ACTION_UP, not in `onRelease`.
  - In keyboard XML, `?` / `@` at the START of an attribute value must be escaped
    (`\?`, `\@`) or AAPT reads them as resource references.
- Word suggestions use **composing text** (`setComposingText`/
  `finishComposingText`); autocorrect swaps the composing word on space.
- An IME can't request a runtime permission from its own window — launch a tiny
  transparent Activity to request `RECORD_AUDIO`.
- The long-press number/symbol map matches Gboard (`1234567890` / `@#£_&-+()` /
  `*"':;!?`).

## Testing

- **Verify prompt changes with a direct temp-0 Anthropic API call** (a few lines
  of `urllib`/`requests`), not by round-tripping through a device — fast,
  deterministic, easy to A/B old vs new.
- Android UI is verified screenshot-first (`adb exec-out screencap`); typing and
  long-press via scripted `input tap` / `input swipe`.
- Match the surrounding code's style, comment density, and idiom.
