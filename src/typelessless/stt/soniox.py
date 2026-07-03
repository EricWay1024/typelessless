from __future__ import annotations

import json
import queue
import threading
from typing import Optional

from .base import PartialCallback, SttClient, SttSession

WEBSOCKET_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
_SENTINEL = object()  # queued to tell the sender thread to end the stream


class SonioxSession(SttSession):
    def __init__(
        self,
        api_key: str,
        model: str,
        sample_rate: int,
        language_hints: list[str],
        vocab: list[str],
        audio_format: str,
        on_partial: Optional[PartialCallback],
    ):
        from websockets.sync.client import connect  # lazy import

        self._on_partial = on_partial
        self._final_parts: list[str] = []
        self._finished = threading.Event()
        self._error: Optional[str] = None
        self._send_q: "queue.Queue" = queue.Queue()

        config: dict = {
            "api_key": api_key,
            "model": model,
            "language_hints": language_hints,
            "enable_language_identification": True,
        }
        if audio_format == "pcm_s16le":
            config["audio_format"] = "pcm_s16le"
            config["sample_rate"] = sample_rate
            config["num_channels"] = 1
        else:
            config["audio_format"] = "auto"
        if vocab:
            # Biases recognition toward these terms (names, jargon, math).
            config["context"] = {"terms": list(vocab)}

        self._ws = connect(WEBSOCKET_URL)
        self._ws.send(json.dumps(config))

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._sender = threading.Thread(target=self._send_loop, daemon=True)
        self._reader.start()
        self._sender.start()

    # --- audio in -------------------------------------------------------
    def feed(self, pcm: bytes) -> None:
        self._send_q.put(pcm)

    def _send_loop(self) -> None:
        try:
            while True:
                item = self._send_q.get()
                if item is _SENTINEL:
                    self._ws.send("")  # Soniox end-of-stream marker
                    return
                self._ws.send(item)
        except Exception:
            return

    # --- transcript out -------------------------------------------------
    def _read_loop(self) -> None:
        from websockets import ConnectionClosed

        try:
            while True:
                res = json.loads(self._ws.recv())
                if res.get("error_code") is not None:
                    self._error = f"{res.get('error_code')}: {res.get('error_message')}"
                    self._finished.set()
                    return
                nonfinal: list[str] = []
                for tok in res.get("tokens", []):
                    text = tok.get("text")
                    if not text:
                        continue
                    if tok.get("is_final"):
                        self._final_parts.append(text)
                    else:
                        nonfinal.append(text)
                if self._on_partial:
                    self._on_partial("".join(self._final_parts) + "".join(nonfinal))
                if res.get("finished"):
                    self._finished.set()
                    return
        except ConnectionClosed:
            self._finished.set()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._finished.set()

    def finish(self, timeout: float = 15.0) -> str:
        self._send_q.put(_SENTINEL)
        self._finished.wait(timeout)
        self.close()
        if self._error:
            raise RuntimeError(f"Soniox error: {self._error}")
        return "".join(self._final_parts).strip()

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


class SonioxClient(SttClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        sample_rate: int,
        language_hints: list[str],
        vocab: list[str],
    ):
        if not api_key:
            raise ValueError("Missing Soniox API key (set it in config.toml or $SONIOX_API_KEY).")
        self._api_key = api_key
        self._model = model
        self._sample_rate = sample_rate
        self._language_hints = language_hints
        self._vocab = vocab

    def open_session(self, on_partial=None, audio_format="pcm_s16le") -> SttSession:
        return SonioxSession(
            self._api_key,
            self._model,
            self._sample_rate,
            self._language_hints,
            self._vocab,
            audio_format,
            on_partial,
        )
