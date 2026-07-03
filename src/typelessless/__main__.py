from __future__ import annotations

import sys


def _setup_windows_output() -> None:
    """Make prints safe and readable on Windows. In a windowed (console=False)
    frozen build, sys.stdout/stderr are None and any print() would crash — so
    tee them to a debug log. Otherwise just force UTF-8 for 中文 logs."""
    if sys.platform != "win32":
        return
    if sys.stdout is None or sys.stderr is None:
        try:
            from typelessless.dictlog import log_dir

            fh = open(log_dir() / "debug.log", "a", encoding="utf-8", buffering=1)
            if sys.stdout is None:
                sys.stdout = fh
            if sys.stderr is None:
                sys.stderr = fh
        except Exception:
            pass
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    _setup_windows_output()

    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help"):
        print(
            "typelessless — self-owned dictation\n\n"
            "  typelessless             run the tray app (press hotkey to dictate)\n"
            "  typelessless check       verify config + that all components load\n"
            "  typelessless filetest F  transcribe audio file F through STT + cleanup\n"
        )
        return

    if args and args[0] in ("check", "doctor", "--check"):
        from typelessless.selfcheck import run_check

        sys.exit(0 if run_check() else 1)

    # Absolute imports (not relative): when frozen by PyInstaller this file runs
    # as top-level "__main__" with no package context, so `from .x import` fails.
    if args and args[0] == "filetest":
        from typelessless.filetest import run_filetest

        run_filetest(args[1:])
        return

    from typelessless import config as config_mod
    from typelessless.app import App

    try:
        App(config_mod.load()).run()
    except Exception:
        import traceback

        _fatal(traceback.format_exc())


def _fatal(message: str) -> None:
    """Show a startup error that survives a double-click (no vanishing console)."""
    sys.stderr.write(message + "\n")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message[-1800:], "typelessless — error", 0x10)
        except Exception:
            pass
    sys.exit(1)


if __name__ == "__main__":
    main()
