from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

# Called with the best-so-far transcript (final + provisional) as it grows.
PartialCallback = Callable[[str], None]


class SttSession(ABC):
    """A single streaming transcription. Feed audio, then finish() to get text."""

    @abstractmethod
    def feed(self, pcm: bytes) -> None:
        ...

    @abstractmethod
    def finish(self, timeout: float = 15.0) -> str:
        """Signal end-of-stream, wait for the final transcript, return it."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class SttClient(ABC):
    """A provider. Swap this out to change engines without touching the app."""

    @abstractmethod
    def open_session(
        self,
        on_partial: Optional[PartialCallback] = None,
        audio_format: str = "pcm_s16le",
    ) -> SttSession:
        ...
