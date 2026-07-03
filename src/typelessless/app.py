from __future__ import annotations

import array
import threading
from collections import deque

from . import config as config_mod
from . import dictlog, history, startup
from .audio import Microphone
from .cleanup.claude import ClaudeCleaner
from .cleanup.passthrough import Passthrough
from .hotkey import Hotkey
from .inject import inject_text
from .overlay import StatusOverlay
from .stt.soniox import SonioxClient


class App:
    def __init__(self, cfg: config_mod.Config):
        self.cfg = cfg
        self.active_mode = cfg.default_mode
        self.modes = list(cfg.modes.keys())

        self._passthrough = Passthrough()
        self._stt = None
        self._llm = None
        self._build_backends()

        self._lock = threading.Lock()
        self._recording = False
        self._state = "idle"  # idle | recording | processing  (drives the overlay)
        self._session = None
        self._mic = None
        self._audio_buf = bytearray()
        self._levels: deque = deque(maxlen=48)  # recent audio levels for the waveform
        self._icon = None
        self._hotkey = None
        self._overlay = None
        self._webui_url = None
        self._stop_event = threading.Event()

    # --- setup ----------------------------------------------------------
    def _build_backends(self) -> None:
        self._stt = SonioxClient(
            self.cfg.soniox_key,
            self.cfg.stt_model,
            self.cfg.sample_rate,
            self.cfg.language_hints,
            self.cfg.vocab,
        )
        self._llm = None
        if self.cfg.anthropic_key:
            try:
                self._llm = ClaudeCleaner(self.cfg.anthropic_key, self.cfg.cleanup_model)
            except Exception as exc:  # noqa: BLE001
                print(f"[cleanup] Claude unavailable ({exc}); modes will use raw transcripts.")

    def _cleaner_for(self, mode):
        if mode.use_llm and self._llm is not None:
            return self._llm
        return self._passthrough

    # --- state ----------------------------------------------------------
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
        if name in self.cfg.modes:
            self.active_mode = name
            self._set_state(self._state)
            print(f"[mode] {name}")

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
            step = max(1, len(a) // 800)  # subsample to bound cost
            total = count = 0
            for i in range(0, len(a), step):
                v = a[i]
                total += v * v
                count += 1
            rms = (total / count) ** 0.5 / 32768.0
            self._levels.append(min(1.0, rms * 6.0))
        except Exception:
            pass

    def audio_levels(self) -> list:
        return list(self._levels)

    def start_recording(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
        try:
            self._audio_buf = bytearray()
            self._levels.clear()
            self._session = self._stt.open_session(audio_format="pcm_s16le")
            self._mic = Microphone(self.cfg.sample_rate, self._feed_audio)
            self._mic.start()
            self._set_state("recording")
            print("[rec] listening…")
        except Exception as exc:  # noqa: BLE001
            print(f"[rec] failed to start: {exc}")
            self._recording = False
            self._session = self._mic = None
            self._set_state("idle")

    def stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
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

            # Save the audio FIRST — before any network call — so it can't be
            # lost even if transcription/cleanup/insert fails.
            entry = None
            if len(buf) >= self.cfg.sample_rate:  # ~0.5 s of 16-bit @16k or more
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

            mode = self.cfg.modes[self.active_mode]
            notes = []
            try:
                cleaned = self._cleaner_for(mode).clean(transcript, mode, self.cfg.vocab)
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
                history.mark(
                    entry["id"], status="ok", transcript=transcript, text=cleaned, error="; ".join(notes)
                )
        finally:
            self._set_state("idle")

    # --- retry / history (used by the web UI) ---------------------------
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
        """Re-transcribe a saved recording, re-clean it, and copy the result."""
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
        mode = self.cfg.modes.get(entry.get("mode")) or self.cfg.modes[self.active_mode]
        try:
            cleaned = self._cleaner_for(mode).clean(transcript, mode, self.cfg.vocab)
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

    # --- tray actions ---------------------------------------------------
    def open_log(self) -> None:
        dictlog.open_log()

    def show_history(self) -> None:
        if self._webui_url:
            import webbrowser

            webbrowser.open(self._webui_url)

    def startup_enabled(self) -> bool:
        return startup.is_enabled()

    def toggle_startup(self) -> None:
        on = startup.toggle()
        print(f"[startup] {'enabled' if on else 'disabled'}")

    def reload(self) -> None:
        try:
            self.cfg = config_mod.load()
            self.modes = list(self.cfg.modes.keys())
            if self.active_mode not in self.cfg.modes:
                self.active_mode = self.cfg.default_mode
            self._build_backends()
            self._set_state(self._state)
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
        print(f"typelessless running. {how}. Mode: {self.active_mode}. (tray → history/log/quit)")

        self._icon = make_icon(self)
        try:
            self._icon.run()  # blocks on the main thread until Quit
        finally:
            self._stop_event.set()
            if self._hotkey is not None:
                self._hotkey.stop()
