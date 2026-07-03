from __future__ import annotations

import threading

from . import config as config_mod
from .audio import Microphone
from .cleanup.claude import ClaudeCleaner
from .cleanup.passthrough import Passthrough
from .hotkey import Hotkey
from .inject import inject_text
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
        self._session = None
        self._mic = None
        self._icon = None
        self._hotkey = None

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

    # --- mode + status --------------------------------------------------
    def set_mode(self, name: str) -> None:
        if name in self.cfg.modes:
            self.active_mode = name
            self._set_status(self._recording)
            print(f"[mode] {name}")

    def _set_status(self, recording: bool) -> None:
        if self._icon is not None:
            self._icon.title = (
                "typelessless — ● recording" if recording else f"typelessless — {self.active_mode}"
            )

    # --- activation -----------------------------------------------------
    def toggle(self) -> None:
        """Toggle mode: press once to start, press again to stop + insert."""
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
            self._set_status(True)
            print("[rec] listening…")
        except Exception as exc:  # noqa: BLE001
            print(f"[rec] failed to start: {exc}")
            self._recording = False
            self._session = self._mic = None
            self._set_status(False)

    def stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
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
                cleaned = transcript

            try:
                inject_text(cleaned, self.cfg.inject_method, self.cfg.restore_clipboard)
                print(f"[out] {cleaned!r}")
            except Exception as exc:  # noqa: BLE001
                print(f"[inject] {exc}")
        finally:
            self._set_status(False)

    # --- lifecycle ------------------------------------------------------
    def reload(self) -> None:
        try:
            self.cfg = config_mod.load()
            self.modes = list(self.cfg.modes.keys())
            if self.active_mode not in self.cfg.modes:
                self.active_mode = self.cfg.default_mode
            self._build_backends()
            self._set_status(self._recording)
            print("[config] reloaded")
        except Exception as exc:  # noqa: BLE001
            print(f"[config] reload failed: {exc}")

    def quit(self) -> None:
        if self._hotkey is not None:
            self._hotkey.stop()
        if self._icon is not None:
            self._icon.stop()

    def run(self) -> None:
        from .tray import make_icon

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
        print(f"typelessless running. {how}. Mode: {self.active_mode}. (tray → mode/quit)")
        self._icon = make_icon(self)
        self._icon.run()  # blocks on the main thread until Quit
