from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path


def log_dir() -> Path:
    """A user-writable directory for logs (survives wherever the exe lives)."""
    base = os.environ.get("APPDATA") if sys.platform == "win32" else None
    root = Path(base) if base else (Path.home() / ".config")
    d = root / "typelessless"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def log_path() -> Path:
    return log_dir() / "dictations.log"


def append(tag: str, text: str) -> None:
    """Append one timestamped line: '2026-07-03 19:05:12  [working]  <text>'."""
    try:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        with log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  [{tag}]  {text}\n")
    except Exception:
        pass


def open_log() -> None:
    """Open the dictation log in the default editor (from the tray menu)."""
    p = log_path()
    try:
        if not p.exists():
            p.write_text("", encoding="utf-8")
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        pass
