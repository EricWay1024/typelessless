from __future__ import annotations

from typing import Callable


class PushToTalk:
    """Global hold-to-talk hotkey. Fires on_press once when the key goes down
    and on_release when it comes back up (ignoring auto-repeat). pynput is
    imported lazily so the package imports on a headless box."""

    def __init__(self, key_name: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self._key_name = key_name
        self._on_press = on_press
        self._on_release = on_release
        self._active = False
        self._listener = None

    def _resolve(self, keyboard):
        name = self._key_name.strip()
        if len(name) == 1:
            return keyboard.KeyCode.from_char(name)
        return getattr(keyboard.Key, name.lower())

    def start(self) -> None:
        from pynput import keyboard

        target = self._resolve(keyboard)

        def matches(key) -> bool:
            if isinstance(target, keyboard.Key):
                return key == target
            return getattr(key, "char", None) == getattr(target, "char", None)

        def on_press(key):
            if not self._active and matches(key):
                self._active = True
                self._on_press()

        def on_release(key):
            if self._active and matches(key):
                self._active = False
                self._on_release()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
