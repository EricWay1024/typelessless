from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help"):
        print(
            "typelessless — self-owned dictation\n\n"
            "  python -m typelessless              run the tray app (hold hotkey to dictate)\n"
            "  python -m typelessless filetest F   transcribe audio file F through STT + cleanup\n"
        )
        return

    if args and args[0] == "filetest":
        from .filetest import run_filetest

        run_filetest(args[1:])
        return

    from . import config as config_mod
    from .app import App

    App(config_mod.load()).run()


if __name__ == "__main__":
    main()
