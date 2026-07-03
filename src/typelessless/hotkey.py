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
        import threading

        from pynput import keyboard

        suppress_vks = self._suppress_vks(keyboard)

        def dispatch(fn) -> None:
            # Run the action off the hook thread so the low-level keyboard hook
            # returns immediately (Windows silently drops slow hooks).
            if fn is not None:
                threading.Thread(target=fn, daemon=True).start()

        def fire_press() -> None:
            dispatch(self._on_start if self._mode == "hold" else self._on_toggle)

        def fire_release() -> None:
            if self._mode == "hold":
                dispatch(self._on_stop)

        # Windows: pynput's suppress_event() aborts the event *before* it reaches
        # on_press/on_release, so a suppressed key would fire no callback. We
        # therefore detect the key and act inside the filter, then swallow it so
        # it can't also reach the focused app.
        if sys.platform == "win32" and suppress_vks:
            _DOWN = {0x100, 0x104}  # WM_KEYDOWN, WM_SYSKEYDOWN (Alt = SYS*)
            _UP = {0x101, 0x105}    # WM_KEYUP, WM_SYSKEYUP

            def win32_event_filter(msg, data):
                if data.vkCode not in suppress_vks:
                    return True  # let every other key through untouched
                if msg in _DOWN:
                    if not self._down:
                        self._down = True
                        fire_press()
                elif msg in _UP:
                    if self._down:
                        self._down = False
                        fire_release()
                self._listener.suppress_event()  # raises → swallows the key

            self._listener = keyboard.Listener(
                on_press=lambda *a: None,
                on_release=lambda *a: None,
                win32_event_filter=win32_event_filter,
            )
            self._listener.start()
            return

        # Fallback (non-Windows, or a key with no known vk): passive listener,
        # no suppression — the key also reaches other apps.
        matches = self._matcher(keyboard)

        def on_press(key):
            if self._down or not matches(key):
                return
            self._down = True
            fire_press()

        def on_release(key):
            if not self._down or not matches(key):
                return
            self._down = False
            fire_release()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
