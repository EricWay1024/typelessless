from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Mode:
    """A dictation mode: a named cleanup behaviour you toggle from the tray."""

    name: str
    prompt: str = ""
    use_llm: bool = True
