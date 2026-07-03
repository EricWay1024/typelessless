from __future__ import annotations

import sys
import time

IS_WINDOWS = sys.platform == "win32"


def inject_text(text: str, method: str = "paste", restore_clipboard: bool = True) -> None:
    """Insert `text` into whatever field currently has focus."""
    if not text:
        return
    if not IS_WINDOWS:
        raise RuntimeError("Text injection is only implemented on Windows (run the app on Windows).")
    if method == "type":
        _type_unicode(text)
    else:
        _paste(text, restore_clipboard)


def _paste(text: str, restore: bool) -> None:
    import pyperclip

    prev = None
    if restore:
        try:
            prev = pyperclip.paste()
        except Exception:
            prev = None
    pyperclip.copy(text)
    time.sleep(0.03)
    _ctrl_v()
    if restore and prev is not None:
        time.sleep(0.15)
        try:
            pyperclip.copy(prev)
        except Exception:
            pass


def _ctrl_v() -> None:
    import ctypes

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_V = 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def _type_unicode(text: str) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]

    def send_units(units: list[int]) -> None:
        events = []
        for u in units:
            events.append(INPUT(type=INPUT_KEYBOARD, u=_UNION(ki=KEYBDINPUT(0, u, KEYEVENTF_UNICODE, 0, 0))))
            events.append(
                INPUT(type=INPUT_KEYBOARD, u=_UNION(ki=KEYBDINPUT(0, u, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)))
            )
        arr = (INPUT * len(events))(*events)
        user32.SendInput(len(events), ctypes.byref(arr), ctypes.sizeof(INPUT))

    for ch in text:
        cp = ord(ch)
        if cp > 0xFFFF:  # emit a UTF-16 surrogate pair
            cp -= 0x10000
            send_units([0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)])
        else:
            send_units([cp])
