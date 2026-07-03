from __future__ import annotations

import sys
import threading
from typing import Callable

IS_WINDOWS = sys.platform == "win32"


def _rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)  # Win32 COLORREF is 0x00BBGGRR


_BG = _rgb(26, 27, 32)
_REC = _rgb(255, 99, 99)     # coral red — recording
_PROC = _rgb(255, 185, 70)   # amber — processing
_BARS = 21
_W, _H = 176, 40
_ALPHA = 205
_MARGIN_BOTTOM = 26


class StatusOverlay:
    """A modern floating pill at the bottom-center of the monitor under the
    cursor, showing a live audio waveform while recording (and a flowing
    shimmer while processing). Pure Win32 via ctypes — nothing to bundle.

    The target monitor is chosen when recording starts; moving the cursor to a
    different screen mid-recording does not move the pill. No-op off Windows.
    """

    def __init__(
        self,
        state_getter: Callable[[], str],
        level_getter: Callable[[], list],
        stop_event: threading.Event,
    ):
        self._get_state = state_getter
        self._get_levels = level_getter
        self._stop = stop_event
        self._cur = None
        self._phase = 0
        self._wndproc = None  # keep the WNDPROC alive against GC
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

    def _loop(self) -> None:  # noqa: C901 - a self-contained Win32 window
        import ctypes
        import math
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        void = ctypes.c_void_p
        cint = ctypes.c_int
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        class PAINTSTRUCT(ctypes.Structure):
            _fields_ = [("hdc", void), ("fErase", wintypes.BOOL), ("rcPaint", RECT),
                        ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL),
                        ("rgbReserved", ctypes.c_byte * 32)]

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", cint), ("cbWndExtra", cint),
                        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        # argtypes/restypes — mandatory on 64-bit (defaults truncate handles).
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           cint, cint, cint, cint, wintypes.HWND, wintypes.HMENU,
                                           wintypes.HINSTANCE, wintypes.LPVOID]
        user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
        user32.GetSystemMetrics.restype = cint
        user32.GetSystemMetrics.argtypes = [cint]
        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.MonitorFromPoint.restype = void
        user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [void, ctypes.POINTER(MONITORINFO)]
        user32.SetWindowPos.argtypes = [wintypes.HWND, void, cint, cint, cint, cint, wintypes.UINT]
        user32.ShowWindow.argtypes = [wintypes.HWND, cint]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.InvalidateRect.argtypes = [wintypes.HWND, void, wintypes.BOOL]
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.FillRect.argtypes = [void, ctypes.POINTER(RECT), void]
        user32.BeginPaint.restype = void
        user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        user32.SetWindowRgn.argtypes = [wintypes.HWND, void, wintypes.BOOL]
        user32.SetTimer.restype = void
        user32.SetTimer.argtypes = [wintypes.HWND, void, wintypes.UINT, void]
        user32.GetMessageW.restype = cint
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = LRESULT
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.PostQuitMessage.argtypes = [cint]
        gdi32.CreateSolidBrush.restype = void
        gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
        gdi32.CreateCompatibleDC.restype = void
        gdi32.CreateCompatibleDC.argtypes = [void]
        gdi32.CreateCompatibleBitmap.restype = void
        gdi32.CreateCompatibleBitmap.argtypes = [void, cint, cint]
        gdi32.SelectObject.restype = void
        gdi32.SelectObject.argtypes = [void, void]
        gdi32.BitBlt.argtypes = [void, cint, cint, cint, cint, void, cint, cint, wintypes.DWORD]
        gdi32.DeleteDC.argtypes = [void]
        gdi32.DeleteObject.argtypes = [void]
        gdi32.GetStockObject.restype = void
        gdi32.GetStockObject.argtypes = [cint]
        gdi32.RoundRect.argtypes = [void, cint, cint, cint, cint, cint, cint]
        gdi32.CreateRoundRectRgn.restype = void
        gdi32.CreateRoundRectRgn.argtypes = [cint, cint, cint, cint, cint, cint]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

        WS_POPUP = 0x80000000
        WS_EX = 0x00000008 | 0x00000080 | 0x00080000 | 0x00000020 | 0x08000000  # TOPMOST|TOOL|LAYERED|TRANSPARENT|NOACTIVATE
        SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
        WM_DESTROY, WM_PAINT, WM_ERASEBKGND, WM_TIMER = 0x0002, 0x000F, 0x0014, 0x0113
        LWA_ALPHA = 0x02
        NULL_PEN, SRCCOPY = 8, 0x00CC0020
        MONITOR_DEFAULTTONEAREST = 2
        SWP = 0x0010 | 0x0004  # NOACTIVATE | NOZORDER

        def monitor_work_under_cursor():
            pt = POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcWork
                    return r.left, r.top, r.right - r.left, r.bottom - r.top
            return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

        def reposition(hwnd):
            wx, wy, ww, wh = monitor_work_under_cursor()
            x = wx + (ww - _W) // 2
            y = wy + wh - _H - _MARGIN_BOTTOM
            user32.SetWindowPos(hwnd, None, x, y, _W, _H, SWP)

        def bar_values():
            if self._cur == "recording":
                lv = list(self._get_levels() or [])[-_BARS:]
                return [0.05] * (_BARS - len(lv)) + lv
            return [max(0.12, 0.52 + 0.44 * math.sin(self._phase * 0.28 + i * 0.5)) for i in range(_BARS)]

        def draw(memdc, w, h):
            color = _REC if self._cur == "recording" else _PROC
            brush = gdi32.CreateSolidBrush(color)
            ob = gdi32.SelectObject(memdc, brush)
            op = gdi32.SelectObject(memdc, gdi32.GetStockObject(NULL_PEN))
            pad = 13
            slot = (w - 2 * pad) / _BARS
            bw = max(3, int(slot * 0.55))
            for i, lv in enumerate(bar_values()):
                lv = 0.0 if lv < 0 else 1.0 if lv > 1 else lv
                bh = int(4 + lv * (h - 10))
                cx = pad + i * slot + slot / 2
                x0 = int(cx - bw / 2)
                y0 = (h - bh) // 2
                gdi32.RoundRect(memdc, x0, y0, x0 + bw, y0 + bh, bw, bw)
            gdi32.SelectObject(memdc, ob)
            gdi32.SelectObject(memdc, op)
            gdi32.DeleteObject(brush)

        def on_paint(hwnd):
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            rc = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rc))
            w, h = rc.right, rc.bottom
            mem = gdi32.CreateCompatibleDC(hdc)
            bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
            old = gdi32.SelectObject(mem, bmp)
            bg = gdi32.CreateSolidBrush(_BG)
            user32.FillRect(mem, ctypes.byref(rc), bg)
            gdi32.DeleteObject(bg)
            draw(mem, w, h)
            gdi32.BitBlt(hdc, 0, 0, w, h, mem, 0, 0, SRCCOPY)
            gdi32.SelectObject(mem, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem)
            user32.EndPaint(hwnd, ctypes.byref(ps))

        def tick(hwnd):
            if self._stop.is_set():
                user32.DestroyWindow(hwnd)
                return
            try:
                state = self._get_state()
            except Exception:
                state = "idle"
            if state != self._cur:
                prev = self._cur
                self._cur = state
                if state == "recording":
                    if prev != "recording":
                        reposition(hwnd)
                    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                elif state == "processing":
                    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                else:
                    user32.ShowWindow(hwnd, SW_HIDE)
            if self._cur in ("recording", "processing"):
                self._phase += 1
                user32.InvalidateRect(hwnd, None, False)

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_PAINT:
                on_paint(hwnd)
                return 0
            if msg == WM_ERASEBKGND:
                return 1  # painted in WM_PAINT (double-buffered) — no flicker
            if msg == WM_TIMER:
                tick(hwnd)
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
        user32.RegisterClassW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(WS_EX, wc.lpszClassName, "typelessless", WS_POPUP,
                                      0, 0, _W, _H, None, None, hinst, None)
        if not hwnd:
            return
        user32.SetLayeredWindowAttributes(hwnd, 0, _ALPHA, LWA_ALPHA)
        rgn = gdi32.CreateRoundRectRgn(0, 0, _W + 1, _H + 1, _H, _H)  # capsule shape
        user32.SetWindowRgn(hwnd, rgn, True)
        user32.SetTimer(hwnd, 1, 40, None)  # ~25 fps

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
