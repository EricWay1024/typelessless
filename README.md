# typelessless

A voice-dictation tool you own end-to-end — a self-hosted alternative to
Typeless for Windows, built for people who speak **中文 and English mixed
together**. Press a key, talk (switching languages mid-sentence), press again —
cleaned text is inserted into whatever field has focus. No subscription, your
own API keys, your own prompts.

```
Right Alt (toggle) → mic (16 kHz) → Soniox STT  (语言提示 en+zh, 词汇偏置)
   → mode router (auto by focused app) → Claude cleanup → paste into focused field
```

## Features

- **Real 中/英 code-switching** via [Soniox](https://soniox.com) realtime STT —
  mid-sentence language switching, no manual toggling, with custom-vocabulary bias.
- **LLM cleanup** via Claude, with a global "core" prompt plus per-mode prompts.
  Four default modes, escalating in aggressiveness:
  `chatting` (verbatim+) · `working` (remove fillers/false starts) ·
  `cleaning` (reorder/merge redundancy) · `polish` (cross-sentence merge + rewrite).
- **Auto mode selection by focused window** — e.g. focus VS Code → `working`;
  configurable app→mode rules, else a default mode.
- **Settings web UI** (tray → Settings) to create/edit modes, the global prompt,
  the vocabulary, the default mode, and the routing rules — no file editing.
- **History web UI** (tray → Show history) — every dictation is logged with its
  audio; **retry** re-transcribes a saved recording and copies the result. The
  raw audio is saved *before* any network call, so a failed request never loses
  a recording.
- **Floating waveform indicator** at the bottom-center of the monitor under your
  cursor (red = recording, amber = processing).
- **Mutes system audio while recording** (restored on stop).
- **Push-to-talk toggle** on Right Alt (fully suppressed so it doesn't leak to
  other apps); walkie-talkie *hold* mode also available.
- **Login autostart** toggle; runs as a tray app with no console.
- Provider-facing code sits behind interfaces — swap Soniox or Claude (or a
  local model) without touching the app.

## Bring your own keys

You supply your own [Soniox](https://console.soniox.com) key (STT) and, for
cleanup, an [Anthropic](https://console.anthropic.com) key. They live in
`config.toml`, which is **gitignored** — it is never committed. You can also set
`$SONIOX_API_KEY` / `$ANTHROPIC_API_KEY` instead and leave the file blank.

Rough cost: Soniox ≈ $0.10–0.12 / hour of audio; Claude Haiku cleanup is a
fraction of a cent per utterance. A few dollars a month in normal use.

## Install (Windows, single .exe)

Windows with Python 3.11+:

```powershell
git clone https://github.com/EricWay1024/typelessless
cd typelessless
./build.ps1
```

`build.ps1` creates a venv, installs everything, and produces
**`dist\typelessless.exe`** plus a `dist\config.toml`. Then:

1. Edit `dist\config.toml` — add your Soniox key (and Anthropic key for cleanup).
2. Double-click **`dist\typelessless.exe`** — a tray icon appears.
3. Press **Right Alt**, speak, press **Right Alt** again → text is inserted.
4. Tray → **Settings** to customize modes/prompts/vocab/rules; **Show history**
   to review, play back, and retry past dictations; **Start on login** to
   autostart.

## Run from source (dev)

```powershell
./run.ps1     # venv + install + config.toml + run, in one step
```

Verify the STT+cleanup pipeline against an audio file on any OS (no mic needed):

```bash
pip install websockets anthropic
cp config.example.toml config.toml     # add keys
python -m typelessless filetest sample.wav working
python -m typelessless check            # verify all components load
```

## Configuration

- `config.toml` (system settings, hand-edited): API keys, STT model,
  `language_hints`, hotkey, injection method, `mute_while_recording`. See
  `config.example.toml`.
- **Modes, prompts, global prompt, vocabulary, and app→mode rules** are managed
  in the **Settings web UI** (tray → Settings) and stored in
  `%APPDATA%\typelessless\settings.json`. On first run this is seeded from the
  built-in defaults (`src/typelessless/settings.py`).

Logs and recordings live under `%APPDATA%\typelessless\`
(`dictations.log`, `history.json`, `recordings\`).

## Layout

```
src/typelessless/
  config.py / settings.py   system config (toml) + editable settings (json)
  modes.py                  Mode dataclass
  audio.py                  mic capture (sounddevice)
  stt/{base,soniox}.py      STT interface + Soniox realtime WebSocket client
  cleanup/{base,claude,passthrough}.py
  inject.py                 Windows paste / unicode-type
  hotkey.py                 global hotkey — toggle or hold, key-suppressing (pynput)
  overlay.py                floating waveform indicator (Win32/ctypes)
  sysmute.py                mute system audio (Core Audio COM via ctypes)
  foreground.py             focused-window detection for mode routing
  history.py / webui.py     recording store + local history/settings web UI
  dictlog.py / startup.py   dictation log + login autostart
  tray.py / app.py          tray menu + orchestrator
  filetest.py / selfcheck.py
typelessless.spec           PyInstaller build → dist/typelessless.exe
build.ps1 / run.ps1
```

## Prebuilt binaries & licenses

This project is **MIT-licensed** (see [LICENSE](LICENSE)). It depends on
`pynput` and `pystray` (both **LGPL-3.0**), used as ordinary pip packages — this
does not affect the license of this code. If you distribute a **prebuilt**
`typelessless.exe` (PyInstaller-bundled), note that LGPL asks that recipients be
able to replace those libraries; the simplest way to satisfy that is to point
users at this source and `build.ps1` so they can rebuild. Distributing the
**source** has no such caveat. Other dependencies (`anthropic`, `websockets`,
`sounddevice`, `pillow`, `pyperclip`) are MIT/BSD.

## Status

Windows desktop app (working). An Android IME reusing the same Soniox + cleanup
contract is a possible next phase.
