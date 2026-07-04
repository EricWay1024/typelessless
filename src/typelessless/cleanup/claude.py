from __future__ import annotations

from ..modes import Mode
from .base import Cleaner


class ClaudeCleaner(Cleaner):
    """Cleanup via Claude Haiku. The per-mode prompt + vocab form a cached
    system prompt, so repeated calls are cheap. Anthropic is imported lazily."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    def _system(self, mode: Mode, vocab: list[str]) -> str:
        parts = [mode.prompt.strip()]
        if vocab:
            parts.append(
                "Preferred spellings for domain terms (normalize to these when clearly intended): "
                + ", ".join(vocab)
                + "."
            )
        return "\n\n".join(p for p in parts if p)

    def clean(self, text: str, mode: Mode, vocab: list[str]) -> str:
        text = text.strip()
        if not text:
            return ""
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            temperature=0,  # cleanup is a deterministic transform; curbs no-translate drift
            system=[
                {
                    "type": "text",
                    "text": self._system(mode, vocab),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            # Wrap the transcript so the model treats it strictly as data, not as
            # instructions addressed to it (see the global prompt's <transcript> rule).
            messages=[{"role": "user", "content": f"<transcript>\n{text}\n</transcript>"}],
        )
        out = "".join(b.text for b in resp.content if b.type == "text").strip()
        return out or text
