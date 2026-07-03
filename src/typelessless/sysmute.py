from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"

# Core Audio COM identifiers.
_CLSID_ENUM = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"       # MMDeviceEnumerator
_IID_ENUM = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"         # IMMDeviceEnumerator
_IID_ENDPOINT_VOL = "{5CDF2C82-841E-4546-9722-0CF74078229A}"  # IAudioEndpointVolume


def _with_endpoint_volume(op):
    """Init COM, resolve the default render device's IAudioEndpointVolume, run
    op(vcall, vol), then release everything. Pure ctypes — no dependencies."""
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import POINTER, byref, c_int, c_void_p, wintypes

    ole32 = ctypes.WinDLL("ole32")
    HRESULT = ctypes.c_long

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    ole32.CoInitializeEx.restype = HRESULT
    ole32.CoInitializeEx.argtypes = [c_void_p, wintypes.DWORD]
    ole32.CoCreateInstance.restype = HRESULT
    ole32.CoCreateInstance.argtypes = [POINTER(GUID), c_void_p, wintypes.DWORD, POINTER(GUID), POINTER(c_void_p)]
    ole32.CLSIDFromString.argtypes = [ctypes.c_wchar_p, POINTER(GUID)]

    def guid(s):
        g = GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(s), byref(g))
        return g

    def vcall(ptr, index, *args, argtypes=()):
        vtbl = ctypes.cast(ptr, POINTER(c_void_p))[0]
        fnp = ctypes.cast(c_void_p(vtbl), POINTER(c_void_p))[index]
        proto = ctypes.WINFUNCTYPE(HRESULT, c_void_p, *argtypes)
        return proto(fnp)(ptr, *args)

    hr = ole32.CoInitializeEx(None, 0)
    did_init = hr in (0, 1)
    enum = c_void_p()
    dev = c_void_p()
    vol = c_void_p()
    try:
        clsid, iid_enum = guid(_CLSID_ENUM), guid(_IID_ENUM)
        if ole32.CoCreateInstance(byref(clsid), None, 23, byref(iid_enum), byref(enum)) != 0 or not enum:
            return None
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eConsole=0, &dev) — vtable 4
        if vcall(enum, 4, 0, 0, byref(dev),
                 argtypes=(c_int, c_int, POINTER(c_void_p))) != 0 or not dev:
            return None
        iid_vol = guid(_IID_ENDPOINT_VOL)
        # IMMDevice::Activate(iid, CLSCTX_ALL, params, &vol) — vtable 3
        if vcall(dev, 3, byref(iid_vol), 23, None, byref(vol),
                 argtypes=(POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p))) != 0 or not vol:
            return None
        return op(vcall, vol)
    finally:
        for p in (vol, dev, enum):
            if p:
                try:
                    vcall(p, 2)  # IUnknown::Release
                except Exception:
                    pass
        if did_init:
            ole32.CoUninitialize()


def get_mute():
    """Return True/False for the default output device, or None on failure."""
    def op(vcall, vol):
        import ctypes

        b = ctypes.c_int(0)
        hr = vcall(vol, 15, ctypes.byref(b), argtypes=(ctypes.POINTER(ctypes.c_int),))  # GetMute
        return bool(b.value) if hr == 0 else None

    try:
        return _with_endpoint_volume(op)
    except Exception:
        return None


def set_mute(mute: bool) -> None:
    def op(vcall, vol):
        import ctypes

        vcall(vol, 14, 1 if mute else 0, None, argtypes=(ctypes.c_int, ctypes.c_void_p))  # SetMute
        return True

    try:
        _with_endpoint_volume(op)
    except Exception:
        pass
