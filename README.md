# typelessless

Voice dictation you own end-to-end. Press a key, speak (freely mixing 中文 and
English), press again — cleaned text is inserted into whatever field has focus.
No subscription, no lock-in.

- **STT:** [Soniox](https://soniox.com) realtime — genuine mid-sentence 中/英
  code-switching, with custom-vocabulary bias.
- **Cleanup:** Claude Haiku, per-mode prompts you control (optional — a mode can
  return raw transcripts).
- **Activation:** **Right Alt** by default, as a **toggle** (press to start,
  press again to stop). Walkie-talkie *hold* mode is also available.
- **Modes:** *working* / *chatting* (or your own), switched from the tray.
- Provider-facing code sits behind interfaces — swap Soniox or Claude (or a
  local model) without touching the app.

```
Right Alt (toggle) → mic (16 kHz) → Soniox STT (hints=[en,zh] + vocab bias)
   → mode router → Claude Haiku cleanup [or raw] → paste into focused field
```

Phase 1 (this repo): Windows desktop app. Phase 2: Android IME reusing the same
Soniox + cleanup contract.

## Install as a Windows app (single .exe)

On Windows with Python 3.11+:

```powershell
git clone <this repo>
cd typelessless
./build.ps1
```

`build.ps1` creates a venv, installs everything, and produces
**`dist\typelessless.exe`** plus a `dist\config.toml` to fill in. Then:

1. Edit `dist\config.toml` — add your Soniox key (and Anthropic key for cleanup).
2. Double-click **`dist\typelessless.exe`**. A tray icon appears.
3. Press **Right Alt**, speak, press **Right Alt** again → the text is inserted.

To launch on login, drop a shortcut to `typelessless.exe` into `shell:startup`.
To hide the log console once you trust it, set `console=False` in
`typelessless.spec` and rebuild.

## Run from source (dev)

```powershell
./run.ps1              # venv + install + config.toml + run, in one step
```

or manually:

```powershell
python -m venv .venv; .\.venv\Scripts\activate
pip install -e .
copy config.example.toml config.toml    # add keys
python -m typelessless
```

## Verify the pipeline first (any OS, no mic)

Confirm your keys, vocab, and prompts against a real audio file — needs only a
Soniox key (+ optional Anthropic key), and works on Linux/macOS too:

```bash
pip install websockets anthropic
cp config.example.toml config.toml       # add keys
python -m typelessless filetest sample.wav working
```

Prints the raw Soniox transcript and the cleaned result.

## Configuration (`config.toml`)

See `config.example.toml` (annotated). Highlights:

- `[keys]` — Soniox + Anthropic (or leave blank → `$SONIOX_API_KEY` /
  `$ANTHROPIC_API_KEY`).
- `[stt].language_hints` — e.g. `["en","zh"]`; this is what drives code-switching.
- `[hotkey].key` / `.mode` — default `key="alt_r"`, `mode="toggle"` (or `"hold"`).
- `[inject].method` — `"paste"` (default, Unicode-safe) or `"type"`.
- `[vocab].terms` — names / jargon / math; biases STT **and** normalizes spelling
  during cleanup.
- `[modes.<name>].prompt` — per-mode cleanup prompt. "Reload config" in the tray
  applies edits live.

## Layout

```
src/typelessless/
  config.py        load config.toml (+ env fallback, exe-relative when frozen)
  modes.py         Mode dataclass
  audio.py         mic capture (sounddevice)
  stt/{base,soniox}.py     STT interface + Soniox realtime WebSocket client
  cleanup/{base,claude,passthrough}.py
  inject.py        Windows paste / unicode-type
  hotkey.py        global hotkey — toggle or hold (pynput)
  tray.py          system-tray menu (pystray)
  app.py           orchestrator
  filetest.py      offline pipeline check
typelessless.spec  PyInstaller build → dist/typelessless.exe
build.ps1 / run.ps1
```

## Cost

Soniox ≈ $0.10–0.12/hr of audio; Haiku cleanup is fractions of a cent per
utterance (cached system prompt). A few dollars a month in normal use.
