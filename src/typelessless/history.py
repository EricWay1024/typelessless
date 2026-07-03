from __future__ import annotations

import json
import threading
import wave
from datetime import datetime
from pathlib import Path

from .dictlog import log_dir

_LOCK = threading.Lock()
_MAX_ENTRIES = 300   # metadata rows kept in history.json
_KEEP_WAVS = 60      # recent non-failed wavs kept (failed ones are always kept)


def _hist_path() -> Path:
    return log_dir() / "history.json"


def _rec_dir() -> Path:
    d = log_dir() / "recordings"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _load() -> list[dict]:
    try:
        return json.loads(_hist_path().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data: list[dict]) -> None:
    try:
        _hist_path().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(pcm)


def create_entry(pcm: bytes, sample_rate: int, mode: str) -> dict:
    """Persist the raw audio immediately, then return a 'processing' entry.
    Called before any network request so the recording can never be lost."""
    ts = datetime.now().astimezone()
    eid = ts.strftime("%Y%m%d-%H%M%S-") + f"{ts.microsecond // 1000:03d}"
    wav = ""
    try:
        _write_wav(_rec_dir() / f"{eid}.wav", pcm, sample_rate)
        wav = f"{eid}.wav"
    except Exception:
        pass
    entry = {
        "id": eid,
        "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "status": "processing",
        "transcript": "",
        "text": "",
        "error": "",
        "wav": wav,
        "sample_rate": sample_rate,
    }
    with _LOCK:
        data = _load()
        data.append(entry)
        _prune(data)
        _save(data)
    return entry


def mark(eid: str, **fields) -> None:
    with _LOCK:
        data = _load()
        for e in data:
            if e.get("id") == eid:
                e.update(fields)
                break
        _save(data)


def get(eid: str) -> dict | None:
    with _LOCK:
        for e in _load():
            if e.get("id") == eid:
                return e
    return None


def entries(limit: int = 200) -> list[dict]:
    with _LOCK:
        data = _load()
    return list(reversed(data))[:limit]  # newest first


def wav_path(entry: dict | None) -> Path | None:
    if not entry or not entry.get("wav"):
        return None
    p = _rec_dir() / entry["wav"]
    return p if p.exists() else None


def _prune(data: list[dict]) -> None:
    if len(data) > _MAX_ENTRIES:
        for e in data[: len(data) - _MAX_ENTRIES]:
            _delete_wav(e)
        del data[: len(data) - _MAX_ENTRIES]
    kept = 0
    for e in reversed(data):
        if not e.get("wav"):
            continue
        if e.get("status") == "failed":
            continue  # always keep failed audio for retry
        if kept < _KEEP_WAVS:
            kept += 1
            continue
        _delete_wav(e)


def _delete_wav(entry: dict) -> None:
    if entry.get("wav"):
        try:
            (_rec_dir() / entry["wav"]).unlink(missing_ok=True)
        except Exception:
            pass
        entry["wav"] = ""
