from __future__ import annotations

import threading

from . import config as config_mod
from . import dictlog, startup
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
        self._icon = None
        self._hotkey = None
        self._overlay = None
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
        """Current state, polled by the overlay."""
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
            self._set_state(self._state)  # refresh tray label
            print(f"[mode] {name}")

    # --- activation -----------------------------------------------------
    def toggle(self) -> None:
        """Toggle: press once to start, press again to stop + insert."""
        with self._lock:
            recording = self._recording
        if recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
        try:
            self._session = self._stt.open_session(audio_format="pcm_s16le")
            self._mic = Microphone(self.cfg.sample_rate, self._session.feed)
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
        # Finalize off the hotkey thread so the listener stays responsive.
        threading.Thread(target=self._finalize, daemon=True).start()

    def _finalize(self) -> None:
        mic, session = self._mic, self._session
        self._mic = self._session = None
        try:
            try:
                if mic is not None:
                    mic.stop()
                transcript = session.finish() if session is not None else ""
            except Exception as exc:  # noqa: BLE001
                print(f"[stt] {exc}")
                dictlog.append("error", f"stt: {exc}")
                return

            if not transcript:
                print("[rec] (nothing heard)")
                return
            print(f"[stt] {transcript!r}")

            mode = self.cfg.modes[self.active_mode]
            try:
                cleaned = self._cleaner_for(mode).clean(transcript, mode, self.cfg.vocab)
            except Exception as exc:  # noqa: BLE001
                print(f"[cleanup] {exc}; inserting raw transcript.")
                dictlog.append("error", f"cleanup: {exc}")
                cleaned = transcript

            try:
                inject_text(cleaned, self.cfg.inject_method, self.cfg.restore_clipboard)
                print(f"[out] {cleaned!r}")
                dictlog.append(self.active_mode, cleaned)
            except Exception as exc:  # noqa: BLE001
                print(f"[inject] {exc}")
                dictlog.append("error", f"inject: {exc}")
        finally:
            self._set_state("idle")

    # --- tray actions ---------------------------------------------------
    def open_log(self) -> None:
        dictlog.open_log()

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

        # Status overlay runs in its own thread (tkinter).
        self._overlay = StatusOverlay(self.status, self._stop_event)
        self._overlay.start()

        if self.cfg.hotkey_mode == "hold":
            self._hotkey = Hotkey(
                self.cfg.hotkey,
                "hold",
                on_start=self.start_recording,
                on_stop=self.stop_recording,
            )
            how = f"Hold [{self.cfg.hotkey}] to talk, release to insert"
        else:
            self._hotkey = Hotkey(self.cfg.hotkey, "toggle", on_toggle=self.toggle)
            how = f"Press [{self.cfg.hotkey}] to start, press again to stop + insert"

        self._hotkey.start()
        print(f"typelessless running. {how}. Mode: {self.active_mode}. (tray → mode/log/quit)")

        self._icon = make_icon(self)
        try:
            self._icon.run()  # blocks on the main thread until Quit
        finally:
            self._stop_event.set()
            if self._hotkey is not None:
                self._hotkey.stop()
