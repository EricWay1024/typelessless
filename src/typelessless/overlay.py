from __future__ import annotations

import sys
import threading
from typing import Callable

IS_WINDOWS = sys.platform == "win32"


def _rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)  # Win32 COLORREF is 0x00BBGGRR


_STATE_COLORS = {
    "recording": _rgb(229, 57, 53),    # red
    "processing": _rgb(249, 168, 37),  # amber
}


class StatusOverlay:
    """A tiny always-on-top, click-through dot in the bottom-left corner that
    reflects the dictation state (red = recording, amber = processing, hidden =
    idle). Pure Win32 via ctypes — nothing to bundle. No-op on non-Windows.

    Runs its own window + message loop on a daemon thread and polls a state
    getter on a timer; the app never has to touch it.
    """

    SIZE = 14
    MARGIN_X = 20
    MARGIN_BOTTOM = 60

    def __init__(self, state_getter: Callable[[], str], stop_event: threading.Event):
        self._get_state = state_getter
        self._stop = stop_event
        self._cur = None
        self._wndproc = None  # keep the WNDPROC callback alive against GC
        self._thread = None

    def start(self) -> None:
        if not IS_WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._loop()
        except Exception:
            pass  # the overlay must never take down the app

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        # restype/argtypes are mandatory on 64-bit — defaults truncate handles.
        void = ctypes.c_void_p
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.InvalidateRect.argtypes = [wintypes.HWND, void, wintypes.BOOL]
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]
        user32.SetWindowRgn.argtypes = [wintypes.HWND, void, wintypes.BOOL]
        user32.SetTimer.restype = void
        user32.SetTimer.argtypes = [wintypes.HWND, void, wintypes.UINT, void]
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.GetMessageW.restype = ctypes.c_int
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
        gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
        gdi32.CreateEllipticRgn.restype = void
        gdi32.CreateEllipticRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        gdi32.DeleteObject.argtypes = [void]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

        WS_POPUP = 0x80000000
        WS_EX_TOPMOST = 0x00000008
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_TRANSPARENT = 0x00000020  # click-through
        WS_EX_NOACTIVATE = 0x08000000
        SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
        WM_DESTROY, WM_ERASEBKGND, WM_TIMER = 0x0002, 0x0014, 0x0113
        SM_CYSCREEN = 1

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_ERASEBKGND:
                color = _STATE_COLORS.get(self._cur)
                if color is not None:
                    rc = RECT()
                    user32.GetClientRect(hwnd, ctypes.byref(rc))
                    brush = gdi32.CreateSolidBrush(color)
                    user32.FillRect(wparam, ctypes.byref(rc), brush)  # wparam is the HDC
                    gdi32.DeleteObject(brush)
                return 1
            if msg == WM_TIMER:
                self._tick(user32, hwnd, SW_SHOWNOACTIVATE, SW_HIDE)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(wndproc)

        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "typelessless_overlay"
        user32.RegisterClassW(ctypes.byref(wc))  # ignore "already exists"

        sh = user32.GetSystemMetrics(SM_CYSCREEN)
        x, y = self.MARGIN_X, sh - self.SIZE - self.MARGIN_BOTTOM
        ex = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        hwnd = user32.CreateWindowExW(
            ex, wc.lpszClassName, "typelessless", WS_POPUP,
            x, y, self.SIZE, self.SIZE, None, None, hinst, None,
        )
        if not hwnd:
            return
        # clip the square window to a circle → a round dot
        rgn = gdi32.CreateEllipticRgn(0, 0, self.SIZE + 1, self.SIZE + 1)
        user32.SetWindowRgn(hwnd, rgn, True)  # window owns the region now
        user32.SetTimer(hwnd, 1, 80, None)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _tick(self, user32, hwnd, sw_show, sw_hide) -> None:
        if self._stop.is_set():
            user32.DestroyWindow(hwnd)
            return
        try:
            state = self._get_state()
        except Exception:
            state = "idle"
        if state == self._cur:
            return
        self._cur = state
        if state in _STATE_COLORS:
            user32.ShowWindow(hwnd, sw_show)
            user32.InvalidateRect(hwnd, None, True)
        else:
            user32.ShowWindow(hwnd, sw_hide)
