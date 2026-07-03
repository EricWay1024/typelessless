from __future__ import annotations

import array
import threading
from collections import deque

from . import config as config_mod
from . import dictlog, foreground, history, settings, startup, sysmute
from .audio import Microphone
from .cleanup.claude import ClaudeCleaner
from .cleanup.passthrough import Passthrough
from .hotkey import Hotkey
from .inject import inject_text
from .modes import Mode
from .overlay import StatusOverlay
from .stt.soniox import SonioxClient


class App:
    def __init__(self, cfg: config_mod.Config):
        self.cfg = cfg
        # User-editable settings (modes / prompts / vocab / rules), seeded from
        # config.toml on first run, then owned by the Settings web UI.
        seed = {
            "global_prompt": "",
            "vocab": list(cfg.vocab),
            "default_mode": cfg.default_mode,
            "modes": [{"name": n, "prompt": m.prompt, "use_llm": m.use_llm} for n, m in cfg.modes.items()],
            "rules": [],
        }
        self.active_mode = cfg.default_mode
        self.settings = settings.load(seed)
        self._apply_settings(self.settings)

        self._passthrough = Passthrough()
        self._stt = None
        self._llm = None
        self._build_backends()

        self._lock = threading.Lock()
        self._recording = False
        self._state = "idle"
        self._session = None
        self._mic = None
        self._audio_buf = bytearray()
        self._levels: deque = deque(maxlen=48)
        self._prev_mute = None
        self._icon = None
        self._hotkey = None
        self._overlay = None
        self._webui_url = None
        self._stop_event = threading.Event()

    # --- settings-derived state -----------------------------------------
    def _apply_settings(self, s: dict) -> None:
        self._global_prompt = s.get("global_prompt", "")
        self._vocab = list(s.get("vocab", []))
        self._rules = list(s.get("rules", []))
        self._smodes = {
            m["name"]: Mode(m["name"], m.get("prompt", ""), bool(m.get("use_llm", True)))
            for m in s.get("modes", [])
        }
        if not self._smodes:
            self._smodes = {"working": Mode("working", "", True)}
        self.modes = list(self._smodes.keys())
        dm = s.get("default_mode")
        self._default_mode = dm if dm in self._smodes else self.modes[0]
        if self.active_mode not in self._smodes:
            self.active_mode = self._default_mode

    def _build_backends(self) -> None:
        self._stt = SonioxClient(
            self.cfg.soniox_key, self.cfg.stt_model, self.cfg.sample_rate,
            self.cfg.language_hints, self._vocab,
        )
        self._llm = None
        if self.cfg.anthropic_key:
            try:
                self._llm = ClaudeCleaner(self.cfg.anthropic_key, self.cfg.cleanup_model)
            except Exception as exc:  # noqa: BLE001
                print(f"[cleanup] Claude unavailable ({exc}); modes will use raw transcripts.")

    def _cleaner_for(self, mode):
        return self._llm if (mode.use_llm and self._llm is not None) else self._passthrough

    def _effective_mode(self, mode: Mode) -> Mode:
        gp = (self._global_prompt or "").strip()
        mp = (mode.prompt or "").strip()
        prompt = f"{gp}\n\n{mp}".strip() if gp else mp
        return Mode(mode.name, prompt, mode.use_llm)

    # --- state / status -------------------------------------------------
    def status(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        self._state = state
        if self._icon is not None:
            label = {"recording": "● recording", "processing": "… processing"}.get(state, self.active_mode)
            try:
                self._icon.title = f"typelessless — {label}"
            except Exception:
                pass

    def set_mode(self, name: str) -> None:
        if name in self._smodes:
            self.active_mode = name
            self._set_state(self._state)
            print(f"[mode] {name}")

    def _pick_mode(self) -> str:
        """Choose a mode from the focused window: first matching rule, else the
        default mode."""
        try:
            exe, title = foreground.active_app()
        except Exception:
            exe = title = ""
        for r in self._rules:
            m = (r.get("match") or "").lower()
            if m and (m in exe or m in title) and r.get("mode") in self._smodes:
                return r["mode"]
        return self._default_mode if self._default_mode in self._smodes else self.modes[0]

    # --- activation -----------------------------------------------------
    def toggle(self) -> None:
        with self._lock:
            recording = self._recording
        if recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _feed_audio(self, pcm: bytes) -> None:
        self._audio_buf.extend(pcm)  # keep a copy so the recording is never lost
        self._push_level(pcm)
        session = self._session
        if session is not None:
            session.feed(pcm)

    def _push_level(self, pcm: bytes) -> None:
        try:
            a = array.array("h")
            a.frombytes(pcm if len(pcm) % 2 == 0 else pcm[:-1])
            if not a:
                return
            step = max(1, len(a) // 800)
            total = count = 0
            for i in range(0, len(a), step):
                v = a[i]
                total += v * v
                count += 1
            rms = (total / count) ** 0.5 / 32768.0
            self._levels.append(min(1.0, rms * 7.5))
        except Exception:
            pass

    def audio_levels(self) -> list:
        return list(self._levels)

    def _mute_system(self, on: bool) -> None:
        if not self.cfg.mute_on_record:
            return
        try:
            if on:
                self._prev_mute = sysmute.get_mute()
                sysmute.set_mute(True)
            else:
                sysmute.set_mute(bool(self._prev_mute))
                self._prev_mute = None
        except Exception:
            pass

    def start_recording(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
        try:
            self.active_mode = self._pick_mode()  # auto-select from the focused app
            self._mute_system(True)
            self._audio_buf = bytearray()
            self._levels.clear()
            self._session = self._stt.open_session(audio_format="pcm_s16le")
            self._mic = Microphone(self.cfg.sample_rate, self._feed_audio)
            self._mic.start()
            self._set_state("recording")
            print(f"[rec] listening… (mode: {self.active_mode})")
        except Exception as exc:  # noqa: BLE001
            print(f"[rec] failed to start: {exc}")
            self._recording = False
            self._session = self._mic = None
            self._mute_system(False)
            self._set_state("idle")

    def stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        self._mute_system(False)
        self._set_state("processing")
        threading.Thread(target=self._finalize, daemon=True).start()

    def _finalize(self) -> None:
        mic, session = self._mic, self._session
        buf = bytes(self._audio_buf)
        self._mic = self._session = None
        try:
            try:
                if mic is not None:
                    mic.stop()
            except Exception:
                pass

            entry = None
            if len(buf) >= self.cfg.sample_rate:  # ~0.5 s or more
                entry = history.create_entry(buf, self.cfg.sample_rate, self.active_mode)

            try:
                transcript = session.finish() if session is not None else ""
            except Exception as exc:  # noqa: BLE001
                print(f"[stt] {exc}")
                dictlog.append("error", f"stt: {exc}")
                if entry:
                    history.mark(entry["id"], status="failed", error=f"stt: {exc}")
                return

            if not transcript:
                print("[rec] (nothing heard)")
                if entry:
                    history.mark(entry["id"], status="failed", error="no transcript")
                return
            print(f"[stt] {transcript!r}")

            mode = self._smodes[self.active_mode]
            notes = []
            try:
                cleaned = self._cleaner_for(mode).clean(transcript, self._effective_mode(mode), self._vocab)
            except Exception as exc:  # noqa: BLE001
                print(f"[cleanup] {exc}; using raw transcript.")
                dictlog.append("error", f"cleanup: {exc}")
                cleaned = transcript
                notes.append(f"cleanup: {exc}")

            try:
                inject_text(cleaned, self.cfg.inject_method, self.cfg.restore_clipboard)
                print(f"[out] {cleaned!r}")
                dictlog.append(self.active_mode, cleaned)
            except Exception as exc:  # noqa: BLE001
                print(f"[inject] {exc}")
                dictlog.append("error", f"inject: {exc}")
                notes.append(f"inject: {exc}")

            if entry:
                history.mark(entry["id"], status="ok", transcript=transcript, text=cleaned, error="; ".join(notes))
        finally:
            self._set_state("idle")

    # --- retry / history (web UI) ---------------------------------------
    def history_entries(self):
        return history.entries(200)

    def copy_text(self, eid: str) -> None:
        entry = history.get(eid)
        if entry and entry.get("text"):
            try:
                import pyperclip

                pyperclip.copy(entry["text"])
            except Exception:
                pass

    def retry_entry(self, eid: str) -> None:
        entry = history.get(eid)
        wav = history.wav_path(entry)
        if entry is None or wav is None:
            if entry is not None:
                history.mark(eid, status="failed", error="audio no longer available")
            return
        history.mark(eid, status="processing")
        try:
            session = self._stt.open_session(audio_format="auto")
            with open(wav, "rb") as fh:
                while True:
                    chunk = fh.read(3840)
                    if not chunk:
                        break
                    session.feed(chunk)
            transcript = session.finish(timeout=60.0)
        except Exception as exc:  # noqa: BLE001
            history.mark(eid, status="failed", error=f"stt: {exc}")
            return
        if not transcript:
            history.mark(eid, status="failed", error="no transcript")
            return
        mode = self._smodes.get(entry.get("mode")) or self._smodes[self._default_mode]
        try:
            cleaned = self._cleaner_for(mode).clean(transcript, self._effective_mode(mode), self._vocab)
        except Exception as exc:  # noqa: BLE001
            cleaned = transcript
            history.mark(eid, status="ok", transcript=transcript, text=cleaned, error=f"cleanup: {exc}")
        else:
            history.mark(eid, status="ok", transcript=transcript, text=cleaned, error="")
        dictlog.append(f"retry:{entry.get('mode', '')}", cleaned)
        try:
            import pyperclip

            pyperclip.copy(cleaned)
        except Exception:
            pass

    # --- settings API (web UI) ------------------------------------------
    def get_settings(self) -> dict:
        return self.settings

    def save_settings(self, data: dict) -> dict:
        self.settings = settings.save(data)
        self._apply_settings(self.settings)
        self._build_backends()  # vocab may have changed → refresh Soniox context
        self._refresh_menu()
        print("[settings] saved")
        return self.settings

    def _refresh_menu(self) -> None:
        if self._icon is not None:
            try:
                from .tray import build_menu

                self._icon.menu = build_menu(self)
                self._icon.update_menu()
            except Exception:
                pass

    # --- tray actions ---------------------------------------------------
    def open_log(self) -> None:
        dictlog.open_log()

    def show_history(self) -> None:
        if self._webui_url:
            import webbrowser

            webbrowser.open(self._webui_url)

    def show_settings(self) -> None:
        if self._webui_url:
            import webbrowser

            webbrowser.open(self._webui_url + "settings")

    def startup_enabled(self) -> bool:
        return startup.is_enabled()

    def toggle_startup(self) -> None:
        on = startup.toggle()
        print(f"[startup] {'enabled' if on else 'disabled'}")

    def reload(self) -> None:
        try:
            self.cfg = config_mod.load()
            self.settings = settings.load()
            self._apply_settings(self.settings)
            self._build_backends()
            self._refresh_menu()
            print("[config] reloaded")
        except Exception as exc:  # noqa: BLE001
            print(f"[config] reload failed: {exc}")

    def quit(self) -> None:
        self._stop_event.set()
        if self._hotkey is not None:
            self._hotkey.stop()
        if self._icon is not None:
            self._icon.stop()

    def run(self) -> None:
        from .tray import make_icon

        self._overlay = StatusOverlay(self.status, self.audio_levels, self._stop_event)
        self._overlay.start()

        try:
            from . import webui

            self._webui_url = webui.start(self)
            print(f"[history] {self._webui_url}")
        except Exception as exc:  # noqa: BLE001
            print(f"[history] web UI unavailable: {exc}")

        if self.cfg.hotkey_mode == "hold":
            self._hotkey = Hotkey(
                self.cfg.hotkey, "hold", on_start=self.start_recording, on_stop=self.stop_recording
            )
            how = f"Hold [{self.cfg.hotkey}] to talk, release to insert"
        else:
            self._hotkey = Hotkey(self.cfg.hotkey, "toggle", on_toggle=self.toggle)
            how = f"Press [{self.cfg.hotkey}] to start, press again to stop + insert"

        self._hotkey.start()
        print(f"typelessless running. {how}. (tray → settings/history/quit)")

        self._icon = make_icon(self)
        try:
            self._icon.run()
        finally:
            self._stop_event.set()
            if self._hotkey is not None:
                self._hotkey.stop()
