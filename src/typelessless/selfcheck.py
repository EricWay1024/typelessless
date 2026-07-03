from __future__ import annotations

import importlib
import platform
import sys


def run_check() -> bool:
    """Import every runtime component and report. In a frozen build this proves
    the bundled backends (PortAudio, pynput/pystray win32, pyperclip) actually
    load — the parts most likely to be missing from a PyInstaller bundle."""
    print("typelessless self-check")
    print(f"  python  {sys.version.split()[0]}  ({platform.platform()})")
    print(f"  frozen  {bool(getattr(sys, 'frozen', False))}")

    modules = [
        "sounddevice",            # loads the bundled PortAudio DLL
        "pynput.keyboard",        # loads the win32 keyboard backend
        "pystray",                # loads the win32 tray backend
        "PIL.Image",
        "anthropic",
        "websockets.sync.client",
        "pyperclip",
        "typelessless.audio",
        "typelessless.inject",
        "typelessless.hotkey",
        "typelessless.tray",
        "typelessless.overlay",
        "typelessless.dictlog",
        "typelessless.startup",
        "typelessless.sysmute",
        "typelessless.history",
        "typelessless.webui",
        "typelessless.stt.soniox",
        "typelessless.cleanup.claude",
        "typelessless.app",
    ]
    ok = True
    for m in modules:
        try:
            importlib.import_module(m)
            print(f"  ok   {m}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  FAIL {m}: {exc}")

    try:
        from typelessless import config

        c = config.load()
        print(
            f"  ok   config.toml (hotkey={c.hotkey}/{c.hotkey_mode}, "
            f"soniox={'set' if c.soniox_key else 'MISSING'}, "
            f"anthropic={'set' if c.anthropic_key else 'blank'})"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  warn config.toml: {exc}")

    print("  => OK" if ok else "  => SOME IMPORTS FAILED")
    return ok
