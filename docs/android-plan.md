# typelessless — Android plan

Status: **rev 2 · Phase 2 (QWERTY) in progress** · last updated 2026-07-04

> **Progress log**
> - 2026-07-03 — **Phase 0 DONE (verified on device).** `android/` Gradle project
>   (Gradle 9.0.0 / AGP 8.12.0 / Kotlin 2.1.20, compileSdk 36 / minSdk 26 /
>   targetSdk 34) builds `app-debug.apk`. Installed on the OnePlus 8T over
>   wireless adb; keyboard enables, the placeholder bar shows, and the 🌐
>   switch-to-Gboard button works (short = previous IME, long = picker). Gradle
>   pinned to JDK 17 (`org.gradle.java.home`) since the PATH `java` is a JRE 21.
> - 2026-07-03 — **Phase 1 DONE (verified on device).** Kotlin pipeline
>   (`pipeline/`): `WavReader`, `SonioxClient` (OkHttp WebSocket), `ClaudeCleaner`
>   (OkHttp POST), `Prompts` (global+working copied from settings.py). Keys via
>   gitignored `local.properties` → `BuildConfig`. Ran a 50 s bilingual clip on
>   the OnePlus: Soniox returned correct 中/英 code-switched text; Claude Haiku
>   cleaned it (1.66 s) identically to the desktop — fillers dropped, no
>   translation, terms verbatim. Two fixes found: (a) must handle OkHttp
>   `onClosing` or the socket hangs after Soniox closes; (b) realtime STT emits
>   finals at ~audio-duration pace, so the burst file-test timeout must scale with
>   clip length (live path only waits for the short tail after end-of-stream).
> - 2026-07-03 — **Phase 3 (live dictation) DONE (verified on device by user).**
>   `AudioCapture` (AudioRecord 16 kHz mono), streaming `SonioxSession`
>   (feed/finish, pre-open buffering, onClosing handled), `PermissionActivity`
>   (transparent RECORD_AUDIO request for the IME), and the IME wired: mic toggles
>   recording, live partial transcript shown, cleanup on stop, `commitText` into
>   the focused field. User dictated 中/英 into a real app successfully and liked
>   the live captions. UI refinement applied: tall auto-scrolling transcript area
>   above a mic + 🌐 control row.
> - 2026-07-03 — **Phase 4 built (settings/modes/routing).** `shared/defaults.json`
>   is the single source of truth (generated from settings.py; Gradle copies it
>   into assets each build). `settings/` package: `AppSettings`/`Mode`/`Rule`,
>   `SettingsStore` (seed-from-defaults, normalize like the desktop),
>   `Keys` (SharedPreferences + BuildConfig fallback). IME reloads settings on
>   focus, auto-picks mode by `EditorInfo.packageName`, mode chip cycles/overrides,
>   cleans with the active mode's prompt. `SettingsActivity` edits keys, global
>   prompt, per-mode prompts (add/remove), vocab, default mode, and rules.
>   Fixed a regression: the `pingInterval(15s)` added in Phase 3 killed long
>   Soniox sessions (Soniox doesn't pong); removed — we stream audio continuously
>   so the socket never idles. Also set Claude cleanup **temperature 0** — at the
>   default (1.0) Haiku occasionally *translated* English→Chinese (violating the
>   core no-translate rule); temp 0 makes the transform deterministic and faithful.
>   The desktop has the same latent risk and should get the same one-line fix.
>   Settings path verified on device (mode loaded from store, seeded from
>   defaults.json, faithful cleanup). **Desktop still needs migrating to read
>   shared/defaults.json** (deferred to avoid touching the frozen build now).
> - 2026-07-04 — **Mode design update (user feedback).** (1) `chatting` now
>   `use_llm=false` — Soniox's raw output is already punctuated/segmented, so
>   casual chat skips the LLM entirely (saves a call, keeps natural disfluencies).
>   (2) `polish` made more aggressive per research ([whisper-talk], orcaman GPT-4o
>   fixer, HN): correct ASR errors from context+phonetics, merge repeated ideas
>   across the whole passage, freer reconstruction. Both changed at the source
>   (`settings.py`) and regenerated into `shared/defaults.json`.
>   **Caught a serious regression by file-testing:** the first aggressive polish
>   prompt *translated* English→Chinese (the #1 no-no) because "rewrite for
>   readability / supersedes word choices" overrode no-translate. Fixed by making
>   the prompt state that the no-translate rule is never superseded and that a
>   span's *language* isn't a "word choice" — rewriting/merging happen within each
>   language, whole English clauses stay English. Verified via a direct Anthropic
>   call (temp 0): polish now merges/reorders/error-corrects while preserving
>   中/英 code-switching.
> - **Known limitation:** settings seed once (file-absent); existing users don't
>   auto-get new default prompts — use Settings → "Reset to defaults" (or a fresh
>   install). Note: `pm clear` does NOT wipe files on this OxygenOS device; use
>   `run-as rm files/settings.json` to force a reseed during dev.
> - 2026-07-04 — **Desktop brought in sync.** `cleanup/claude.py` now sends
>   `temperature=0`; `settings.py` defaults already carry chatting-passthrough +
>   fixed polish. Rebuilt the Windows exe from WSL via `_winbuild.ps1` (powershell
>   full-path; killed the running instance first), frozen filetest confirmed
>   no-translation, and relaunched it. Live `%APPDATA%\...\settings.json` patched
>   in place (chatting `use_llm=false` + fixed polish prompt, backup saved),
>   vocab/rules/global untouched. Also added Android keyboard UI polish: removed
>   the idle hint line; four equal-width control buttons — mode · 🎤 · 🌐 · ⚙
>   (⚙ opens Settings).
> - 2026-07-04 — **Phase 2 (QWERTY) started, verified visually on device.**
>   Classic `KeyboardView` (deprecated but ideal for long-press + aligned columns):
>   `res/xml/qwerty.xml` + `symbols.xml`, dark rounded keys (`key_background.xml`),
>   shift/caps (label case toggles), backspace-repeat, `?123` symbols page,
>   space/enter with editor-action handling. `LatinKeyboardView` intercepts
>   onLongPress to insert the key's popupChar and draws a Gboard-style hint in each
>   key's corner. Keyboard swaps to the big transcript while recording. Verified by
>   adb screenshot (`exec-out screencap -p >file`; the phone is PIN-locked so
>   `/sdcard` writes / normal screencap gave black — exec-out works). Long-press
>   map matched to the user's Gboard exactly: 1234567890 / @#£_&-+() / *"':;!?
>   (only `d` differed: $→£). Control icons switched from color emoji to white
>   vector drawables (mic/globe/gear).
>   **Long-press fix + verify (2026-07-04):** long-press was inserting the letter
>   because KeyboardView's long-press handler early-returns when `popupLayout` is
>   unset (`if (mPopupLayout == 0) return false;` → onLongPress never called).
>   Added `res/layout/keyboard_popup.xml` + `android:popupLayout` on the
>   KeyboardView. Verified on device via adb (long-press q→1, tap w→w, long-press
>   e→3 → field showed "1w3"). White icons + per-key hints + d→£ all confirmed by
>   screenshot. **TODO:** key-preview popups, sentence auto-cap, gesture/prediction
>   (deferred). Screenshot tips: use `adb exec-out screencap -p >file` (plain
>   screencap → black on this device); after reinstall, `ime enable`+`ime set`
>   ours (reinstall resets enabled state); do NOT `am force-stop` the IME app
>   before capturing (system falls back to Gboard). Phone reachable via mDNS
>   transport even after IP change — plain `adb` (single device), old `-s IP:port`
>   dies.
> - 2026-07-04 — **Fixed cleanup "breaking character" (prompt-injection).** The
>   LLM sometimes replied conversationally ("I'm a transcript cleaner… there's
>   nothing to clean") instead of returning the text — on already-clean input,
>   greetings, or anything reading as an instruction. Fix (both platforms):
>   hardened the global prompt (it's a text function, never a chat assistant,
>   never refuses/explains) AND wrap the transcript in `<transcript>…</transcript>`
>   in the user turn so it's treated strictly as data. Verified via direct temp-0
>   API tests: clean sentences pass through verbatim, "ignore your instructions…"
>   / "what is the capital of France?" are NOT obeyed, messy transcripts still
>   clean normally. Applied to settings.py + defaults.json + claude.py +
>   ClaudeCleaner.kt; live settings.json patched on both; both apps rebuilt.
> - **Other next options:** English next-word (bigram) prediction; polish
>   (waveform, audio-focus ducking, history/retry, encrypted keys); migrate
>   desktop to shared/defaults.json; auto-reseed on defaults change.

The Windows desktop app is done. This document plans the Android side: a real
soft keyboard (IME) that (a) types English like Gboard, (b) dictates cleaned,
bilingual text into any app via a mic button, and (c) has a prominent **one-tap
switch back to Google Keyboard** — the single feature Typeless is missing.

Sections marked **[DECIDE]** are still open. Everything else is settled from our
discussion and reflected below.

---

## 1. Goal & scope (v1)

**Headline goal:** a keyboard we own that does three things well —

1. **Type** — English QWERTY, like Gboard, with a 3-candidate suggestion strip.
2. **Dictate** — tap the mic, speak 中/英 mixed, get cleaned text committed into
   the focused field of any app (Soniox STT → Claude cleanup → `commitText`).
3. **Switch away instantly** — a dedicated on-keyboard button to jump back to
   Gboard (or any keyboard) for Chinese / French / whatever. **Short-press =
   switch to previous keyboard; long-press = full keyboard picker.** This is the
   thing you most wanted and Typeless lacks; it's a first-class button, not
   buried.

Also in v1: the same **modes** (chatting / working / cleaning / polish),
**global prompt + per-mode prompts + vocabulary** as desktop; **auto mode by
target app** (`EditorInfo.packageName`); **bring-your-own-keys** stored encrypted
on device; **never lose a recording** (WAV to disk before any network call, with
retry).

**Settled from discussion:**
- Real keyboard, not a voice-only bar. English first.
- The switch-to-Gboard button is a headline feature.
- **No cross-device config sync** for v1 — the phone keeps its own local
  settings.
- **Default prompts are shared** — extracted to a repo-level file both the Python
  desktop and the Kotlin app read, so there's one source of truth.

**Deferred:** Chinese/French *typing* layouts (the mic already handles spoken
Chinese; for typed Chinese you tap the switch button → Gboard). Play Store
publishing (sideload the APK first). Gesture/swipe typing.

---

## 2. Confirmed dev environment

Checked on this machine — **ready, WSL-native, no Android Studio required:**

- Android SDK already installed at `/home/eric/android-sdk`
  (`ANDROID_HOME` set), with `adb 36.0.2`, `sdkmanager`, and **platforms
  android-34 & android-36**, **build-tools 34/35/36**, NDK 27, cmake.
- **Java 21** (OpenJDK) on PATH.
- No system `gradle` — fine, we use the **Gradle wrapper** (`./gradlew`), which
  fetches its own Gradle.

**Workflow:** project lives in WSL at `typelessless/android/` (native FS, fast
builds). Build with `./gradlew assembleDebug` / `installDebug`. Deploy to a
**physical phone over wireless `adb`**: on the phone enable Developer options →
Wireless debugging, then `adb pair` / `adb connect <ip:port>` from WSL, then
`adb install`. No USB passthrough needed. (Android Studio on Windows can open
the same project if you ever prefer a GUI.)

- **compileSdk / targetSdk:** 36. **minSdk:** 26 (Android 8.0) — covers ~95%+ of
  devices, enables `EncryptedSharedPreferences` and modern `AudioRecord`.
- **Test device:** OnePlus 8T (`KB2005`), **Android 14** (API 34). Modern —
  supports wireless debugging; connect it via Developer options → Wireless
  debugging when we reach Phase 3. Only affects the test loop, not the build.

---

## 3. Architecture

**Fat client, direct-to-cloud** — no backend, mirroring the desktop. The phone
talks to Soniox and Anthropic directly with your own keys. Nothing always-on to
host, no third box in your audio path. (No config-sync backend either — decided.)

```
Our keyboard (InputMethodService)
  ├─ TYPE:  QWERTY view → suggestion strip → InputConnection.commitText()
  ├─ SWITCH: globe button → switchToPreviousInputMethod() / showInputMethodPicker()
  └─ DICTATE:
       tap mic
       ├─ AudioRecord 16 kHz mono PCM16
       │     └─ write WAV to app storage   ← before any network (never-lose)
       ├─ OkHttp WebSocket ─► Soniox   (language_hints en+zh, context.terms=vocab)
       │     ◄─ is_final tokens → shown live in the suggestion strip
       ├─ pick mode (target-app rule → else default)   EditorInfo.packageName
       ├─ OkHttp POST ─► Claude  (system = globalPrompt + modePrompt + vocab line)
       │     ◄─ cleaned text
       └─ InputConnection.commitText(cleaned)
```

The Soniox WebSocket config and the Claude request are **byte-for-byte the same
shapes** as the desktop (`stt/soniox.py`, `cleanup/claude.py`) — same URL, same
`model` / `language_hints` / `context.terms` / `pcm_s16le`@16k, same
`is_final` / `""`-to-end handshake; same cached `system` = mode prompt + a
"preferred spellings" vocab line, same `user` = transcript.

---

## 4. The keyboard, concretely

### 4a. Typing + the switch button (the "real keyboard" part)
- QWERTY drawn with Jetpack **Compose** (modern, less boilerplate than the
  deprecated `KeyboardView`): letters, shift/caps, `?123` symbols page,
  backspace with auto-repeat, space, enter, comma/period, long-press for accents.
- **Switch button** (globe): **short-press → `switchToPreviousInputMethod()`**
  (instant jump back to Gboard), **long-press → `showInputMethodPicker()`** (pick
  any keyboard/language). Directly fixes your Typeless complaint.
- **Mic button** and **mode chip** live in the top strip.

### 4b. Suggestions / "guess 3 words" — **[DECIDE] fidelity**
Honest tradeoff: real Gboard prediction is on-device ML; we won't match it in v1.
Two realistic routes —

- **Route 1 — build a "Gboard-lite" strip from scratch (recommended).** Bundle a
  permissively-licensed English word-frequency list; do prefix **completion**
  (trie → top-3 by frequency), **autocorrect** (edit-distance-1/2 on space), and
  light **next-word** via a small bigram table. Keeps the app MIT-clean and
  "totally ours." Good, not neural. ~2–3 days of the estimate.
- **Route 2 — fork an open-source engine.** Base the keyboard on an existing OSS
  keyboard for real prediction. **License matters:** *AnySoftKeyboard* /
  *FlorisBoard* are Apache-2.0 (compatible with staying permissive); *OpenBoard*
  / *HeliBoard* are **GPL-3.0** (would force this whole app to GPL — conflicts
  with our MIT). More prediction quality, but we inherit a big codebase and
  (if GPL) a license change.

My recommendation: **Route 1 now.** Voice is the primary input path here; a
solid completion+autocorrect strip is plenty for the typing you'll actually do
by hand, and it keeps the project clean and self-contained. If the suggestions
feel weak in daily use, we revisit Route 2 (AnySoftKeyboard, to stay permissive).

---

## 5. The IME mechanics (novel/risky bits)

- `getCurrentInputConnection().commitText(text, 1)` inserts into any app's focused
  field — our "inject."
- `onStartInputView(EditorInfo, …)` → `info.packageName` = the target app, so
  **app→mode routing ports directly** from desktop `foreground.py`.
- **Mic-permission-from-an-IME gotcha:** `RECORD_AUDIO` is a runtime permission
  and a keyboard can't pop the dialog from its own window. Standard fix: on first
  mic tap without permission, launch a tiny **transparent Activity** that
  requests it and returns. Well-trodden; we prototype it first in Phase 3.
- **Mute-while-recording:** request `AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE` so
  other media ducks while you speak; release on stop.

---

## 6. What we reuse vs. rebuild

Code doesn't port (Python→Kotlin); the **contract, prompts, and design** do.

| Desktop (Python) | Android (Kotlin) | Reuse |
|---|---|---|
| Soniox client `stt/soniox.py` | OkHttp WebSocket | **Protocol verbatim** |
| Claude cleanup `cleanup/claude.py` | OkHttp POST | **Request shape identical** |
| Prompts + modes `settings.py` | Read shared `defaults.json` (new) | **Same strings, one source of truth** |
| App→mode routing `foreground.py` | `EditorInfo.packageName` | **Concept reused** |
| Mic `audio.py` | `AudioRecord` | rebuilt (platform) |
| Hotkey `hotkey.py` | mic button | replaced |
| Inject `inject.py` | `commitText()` | replaced |
| Overlay `overlay.py` | waveform in suggestion strip | rebuilt |
| Mute `sysmute.py` | `AudioManager` audio focus | rebuilt |
| History `history.py` | Room/JSON in app storage | rebuilt, same never-lose guarantee |
| Settings web UI | native Settings `Activity` | rebuilt |

**Shared-defaults refactor (agreed):** extract the default global prompt + 4
mode prompts out of `src/typelessless/settings.py` into a repo-level file
(e.g. `shared/defaults.json`); the desktop reads it as its seed, the app bundles
it as an asset. One edit updates both. Small, self-contained change — I'll do it
as step 0 so both clients diverge from the same baseline.

---

## 7. Phased plan

Each phase ends with something runnable.

- **Phase 0 — Scaffold + dev loop (0.5 d).** `android/` Gradle project (Compose,
  minSdk 26, compileSdk 36); empty IME selectable in system settings; wireless
  `adb` to your phone proven. *Deliverable:* our keyboard appears and can be
  enabled.
- **Phase 1 — Pipeline library, headless (1–2 d).** Kotlin `AudioRecord` +
  `SonioxSession` (OkHttp WS) + `ClaudeCleaner` (OkHttp POST). A dev screen runs
  a bundled WAV → Soniox → Claude and logs cleaned text (Android `filetest`).
  *Deliverable:* bundled audio → correct bilingual cleaned text, no keyboard yet.
- **Phase 2 — The keyboard itself (2–3 d).** QWERTY (Compose), shift/symbols/
  backspace/enter, the **switch-to-Gboard button** (short=previous, long=picker),
  and a basic suggestion strip (Route 1). Typing works end to end. *Deliverable:*
  a usable English keyboard with instant switch-away.
- **Phase 3 — Voice dictation in the keyboard (1–2 d).** Mic button → live
  capture → partial transcript in the strip → cleanup → `commitText`. Transparent
  permission activity. WAV-before-network. *Deliverable:* speak into any app, get
  cleaned text — the core.
- **Phase 4 — Modes, settings, vocab (1–2 d).** Settings `Activity` (keys,
  default mode, edit global/mode prompts + vocab), mode chip, **app→mode rules**
  via `packageName`, seed from shared `defaults.json`. *Deliverable:* config
  parity with desktop; auto mode by app.
- **Phase 5 — Prediction + polish (2–3 d).** Better completion/autocorrect
  (+bigram next-word), waveform, audio-focus ducking, history + retry from saved
  WAV, visible error states. *Deliverable:* daily-driver quality.
- **Phase 6 — Distribute (0.5 d).** Signed release APK, README install steps,
  `android/` build notes. Play Store later, if ever.

**Rough total:** ~8–13 focused days to a solid v1 (real keyboard included).

---

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Mic permission from an IME | Medium | Known transparent-activity pattern; prototype first thing in Phase 3. |
| Prediction quality < Gboard | High | Set expectation: "Gboard-lite" in v1 (Route 1); fork (Route 2) only if it annoys you in use. Voice is the primary path. |
| Building QWERTY is fiddly | Medium | Compose keeps it tractable; keep the layout minimal (no swipe/gestures in v1). |
| Wireless-adb flakiness | Low | Re-pair when the phone's port rotates; USB via usbipd as fallback. |
| Keys on device | Low | Your own device, encrypted at rest — matches desktop's local-keys model. |

---

## 9. Decisions — all settled

- **Package id:** `je.yw.typelessless` (reverse of the owner's `yw.je` domain —
  guarantees global uniqueness; nothing verifies domain ownership, but this is
  the idiomatic, collision-proof choice and matters if ever published).
- **Display name:** `typelessless`.
- **Test device:** OnePlus 8T (`KB2005`), Android 14 (API 34).
- **Suggestion fidelity:** **Route 1** — build a "Gboard-lite" strip from scratch
  (completion + autocorrect + light bigram next-word), MIT-clean. Revisit Route 2
  (fork AnySoftKeyboard/FlorisBoard) only if it feels weak in daily use. Locked
  as default; only affects Phase 2/5, not the early phases.
- Settled earlier: WSL-native dev, real QWERTY keyboard, switch-to-Gboard button,
  no config sync, shared default prompts, direct-to-cloud, OkHttp.

Next action: **Phase 0 — scaffold `android/` + prove wireless adb.**
