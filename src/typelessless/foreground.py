from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"


def active_app() -> tuple[str, str]:
    """Return (exe_name, window_title), both lower-cased, for the foreground
    window — used to auto-select a mode. ('', '') off Windows or on failure."""
    if not IS_WINDOWS:
        return "", ""
    try:
        import ctypes
        from ctypes import POINTER, byref, c_int, create_unicode_buffer, wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.restype = c_int
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.restype = c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, c_int]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, POINTER(wintypes.DWORD)]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""

        n = user32.GetWindowTextLengthW(hwnd)
        buf = create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = (buf.value or "").lower()

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, byref(pid))
        exe = ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if h:
            try:
                size = wintypes.DWORD(260)
                pbuf = create_unicode_buffer(260)
                if kernel32.QueryFullProcessImageNameW(h, 0, pbuf, byref(size)):
                    exe = (pbuf.value or "").rsplit("\\", 1)[-1].lower()
            finally:
                kernel32.CloseHandle(h)
        return exe, title
    except Exception:
        return "", ""
