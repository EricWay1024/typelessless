from __future__ import annotations

from ..modes import Mode
from .base import Cleaner


class Passthrough(Cleaner):
    """No LLM: return the transcript as-is. Used when a mode sets use_llm=false
    or when no Anthropic key is configured."""

    def clean(self, text: str, mode: Mode, vocab: list[str]) -> str:
        return text.strip()
