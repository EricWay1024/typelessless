from __future__ import annotations

from typing import Callable, Optional

# Names that should match whichever Right-Alt symbol pynput reports on a given
# keyboard layout (plain layouts report alt_r; AltGr layouts report alt_gr).
_RIGHT_ALT = {"alt_r", "right_alt", "ralt", "altgr", "alt_gr"}


class Hotkey:
    """A global activation key.

    mode="toggle": press once to start, press again to stop + insert (Typeless-style).
    mode="hold":   walkie-talkie — hold to talk, release to insert.

    Auto-repeat while a key is held is debounced, so one physical press is one
    event. pynput is imported lazily so the package imports on a headless box.
    """

    def __init__(
        self,
        key_name: str,
        mode: str = "toggle",
        *,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_toggle: Optional[Callable[[], None]] = None,
    ):
        self._key_name = key_name
        self._mode = mode
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_toggle = on_toggle
        self._down = False  # physical key currently held (debounces auto-repeat)
        self._listener = None

    def _matcher(self, keyboard):
        name = self._key_name.strip().lower()
        Key = keyboard.Key
        if name in _RIGHT_ALT:
            targets = {k for k in (getattr(Key, "alt_r", None), getattr(Key, "alt_gr", None)) if k}
            return lambda key: key in targets
        if len(name) == 1:
            return lambda key: getattr(key, "char", None) == name
        target = getattr(Key, name)
        return lambda key: key == target

    def _suppress_vks(self, keyboard) -> set[int]:
        """Virtual-key codes to swallow so the key never reaches other apps."""
        name = self._key_name.strip().lower()
        Key = keyboard.Key
        if name in _RIGHT_ALT:
            return {0xA5}  # VK_RMENU (Right Alt)
        if len(name) == 1:
            vk = getattr(keyboard.KeyCode.from_char(name), "vk", None)
            return {vk} if vk else set()
        vk = getattr(getattr(Key, name).value, "vk", None)
        return {vk} if vk else set()

    def start(self) -> None:
        import sys

        from pynput import keyboard

        matches = self._matcher(keyboard)
        suppress_vks = self._suppress_vks(keyboard)

        def on_press(key):
            if self._down or not matches(key):
                return
            self._down = True
            if self._mode == "hold":
                if self._on_start:
                    self._on_start()
            elif self._on_toggle:
                self._on_toggle()

        def on_release(key):
            if not self._down or not matches(key):
                return
            self._down = False
            if self._mode == "hold" and self._on_stop:
                self._on_stop()

        kwargs = {"on_press": on_press, "on_release": on_release}
        if sys.platform == "win32" and suppress_vks:
            # Swallow the activation key system-wide — it is still delivered to
            # our callbacks, but no longer reaches the focused app (so Right Alt
            # stops triggering menus/focus elsewhere).
            def win32_event_filter(msg, data):
                if data.vkCode in suppress_vks:
                    self._listener.suppress_event()

            kwargs["win32_event_filter"] = win32_event_filter

        self._listener = keyboard.Listener(**kwargs)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
