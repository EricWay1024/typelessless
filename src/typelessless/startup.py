from __future__ import annotations

import sys

APP_NAME = "typelessless"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    """The command Windows should run at login."""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    # running from source: relaunch the module through this interpreter
    return f'"{exe}" -m typelessless'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except OSError:
        return False


def enable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())


def disable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass


def toggle() -> bool:
    """Flip autostart; return the new enabled state."""
    if is_enabled():
        disable()
        return False
    enable()
    return True
