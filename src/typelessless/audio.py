from __future__ import annotations

from typing import Callable


class Microphone:
    """Captures 16-bit mono PCM from the default input device and pushes raw
    bytes to a callback. sounddevice is imported lazily so the package stays
    importable on machines without PortAudio (e.g. a Linux dev box)."""

    def __init__(self, samplerate: int, on_audio: Callable[[bytes], None]):
        self._samplerate = samplerate
        self._on_audio = on_audio
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        blocksize = max(160, self._samplerate // 10)  # ~100 ms per block

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            # indata is a raw CFFI buffer for RawInputStream; copy to bytes.
            self._on_audio(bytes(indata))

        self._stream = sd.RawInputStream(
            samplerate=self._samplerate,
            channels=1,
            dtype="int16",
            blocksize=blocksize,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
