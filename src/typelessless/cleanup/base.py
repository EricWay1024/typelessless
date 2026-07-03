from __future__ import annotations

from abc import ABC, abstractmethod

from ..modes import Mode


class Cleaner(ABC):
    """Post-processes a raw transcript according to the active mode."""

    @abstractmethod
    def clean(self, text: str, mode: Mode, vocab: list[str]) -> str:
        ...
