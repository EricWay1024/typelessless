from __future__ import annotations

import json
import threading

from .dictlog import log_dir

_LOCK = threading.Lock()


def _path():
    return log_dir() / "settings.json"


def _normalize(d: dict | None) -> dict:
    d = dict(d or {})
    modes = []
    seen = set()
    for m in d.get("modes", []):
        name = str(m.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        modes.append({"name": name, "prompt": str(m.get("prompt", "")), "use_llm": bool(m.get("use_llm", True))})
    if not modes:
        modes = [{"name": "working", "prompt": "", "use_llm": True}]
    names = {m["name"] for m in modes}

    default = str(d.get("default_mode", "")).strip()
    if default not in names:
        default = modes[0]["name"]

    rules = []
    for r in d.get("rules", []):
        match = str(r.get("match", "")).strip()
        mode = str(r.get("mode", "")).strip()
        if match and mode in names:
            rules.append({"match": match, "mode": mode})

    vocab = [str(x).strip() for x in d.get("vocab", []) if str(x).strip()]

    return {
        "global_prompt": str(d.get("global_prompt", "")),
        "vocab": vocab,
        "default_mode": default,
        "modes": modes,
        "rules": rules,
    }


def _write(data: dict) -> None:
    try:
        _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load(seed: dict | None = None) -> dict:
    """Load settings.json; on first run seed it (e.g. from config.toml)."""
    with _LOCK:
        p = _path()
        if p.is_file():
            try:
                return _normalize(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        data = _normalize(seed)
        _write(data)
        return data


def save(data: dict) -> dict:
    data = _normalize(data)
    with _LOCK:
        _write(data)
    return data
