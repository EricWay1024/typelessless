from __future__ import annotations

import sys


def main() -> None:
    # On Windows the console defaults to a non-UTF-8 code page, which renders
    # dictated 中文 in the log as mojibake. Force UTF-8 for readable logs.
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                if stream is not None:
                    stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

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

    App(config_mod.load()).run()


if __name__ == "__main__":
    main()
