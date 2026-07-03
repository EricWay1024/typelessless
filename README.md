# typelessless

A voice-dictation tool you own end-to-end. Hold a key, speak (freely mixing
中文 and English), release — cleaned text drops into whatever field has focus.
No subscription, no lock-in.

- **STT:** [Soniox](https://soniox.com) realtime — genuine mid-sentence 中/英
  code-switching, plus custom vocabulary bias.
- **Cleanup:** Claude Haiku, with per-mode prompts you control. Pluggable, and
  fully optional (a mode can use raw transcripts).
- **Modes:** toggle *working* / *chatting* (or your own) from the tray icon.
- **Everything provider-facing sits behind an interface** — swap Soniox or
  Claude for anything (incl. a local model) without touching the app.

```
push-to-talk hotkey → mic (16 kHz PCM)
   → Soniox STT   (language_hints=[en, zh], context.terms = your vocab)
   → mode router  (working ⇄ chatting)
   → Claude Haiku cleanup  (your per-mode prompt)  [or passthrough]
   → paste into the focused field
```

Phase 1 is this Windows desktop client. Phase 2 is an Android IME that reuses
the same Soniox + cleanup contract.

## Setup (Windows)

Run it **on Windows** (it needs the Windows mic, global hotkey, and text
injection — it will not work inside WSL). Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
copy config.example.toml config.toml   # then edit config.toml
```

Put your keys in `config.toml` (or set `SONIOX_API_KEY` / `ANTHROPIC_API_KEY`
in the environment and leave them blank in the file).

## Run

```powershell
python -m typelessless
```

Hold **F9** (configurable), speak, release. The tray icon toggles mode, reloads
config, and quits.

## Verify the pipeline first (any OS, no mic)

Before wiring hotkeys, confirm your keys, vocab, and prompts against a real
audio file — this path needs only a Soniox key (+ optional Anthropic key):

```bash
python -m typelessless filetest sample.wav working
```

It prints the raw Soniox transcript and the cleaned result.

## Configuration

Everything lives in `config.toml` (see `config.example.toml` for the annotated
version): keys, STT model, `language_hints`, push-to-talk key, injection
method, custom `vocab.terms`, and one `[modes.<name>]` block per mode with its
own cleanup `prompt`. "Reload config" in the tray picks up edits live.

## Editing from WSL

The repo lives in WSL, but the app runs on Windows. From a Windows shell you
can work in place via the `\\wsl$\<distro>\home\eric\projects\typelessless`
path, or `git clone` it onto the Windows side. Keep one `config.toml` wherever
you run it.

## Layout

```
src/typelessless/
  config.py        load config.toml (+ env fallback)
  modes.py         Mode dataclass
  audio.py         mic capture (sounddevice)
  stt/base.py      SttClient / SttSession interface
  stt/soniox.py    Soniox realtime WebSocket client
  cleanup/base.py  Cleaner interface
  cleanup/claude.py, passthrough.py
  inject.py        Windows paste / unicode-type
  hotkey.py        global push-to-talk (pynput)
  tray.py          system-tray menu (pystray)
  app.py           orchestrator
  filetest.py      offline pipeline check
```

## Cost

Soniox ≈ $0.10–0.12/hr of audio; Haiku cleanup is fractions of a cent per
utterance (cached system prompt). Realistically a few dollars a month.
