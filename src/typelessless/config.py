from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .modes import Mode


@dataclass
class Config:
    soniox_key: str
    anthropic_key: str
    stt_model: str
    sample_rate: int
    language_hints: list[str]
    hotkey: str
    inject_method: str
    restore_clipboard: bool
    vocab: list[str]
    cleanup_model: str
    default_mode: str
    modes: dict[str, Mode]


def _candidates(explicit: str | None) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(Path(explicit))
    out.append(Path.cwd() / "config.toml")
    out.append(Path(__file__).resolve().parents[2] / "config.toml")
    out.append(Path.home() / ".config" / "typelessless" / "config.toml")
    return out


def find_config(explicit: str | None = None) -> Path:
    for c in _candidates(explicit):
        if c.is_file():
            return c
    looked = "\n  ".join(str(c) for c in _candidates(explicit))
    raise FileNotFoundError(
        "No config.toml found. Copy config.example.toml to config.toml and add your keys.\n"
        f"Looked in:\n  {looked}"
    )


def load(path: str | None = None) -> Config:
    cfg_path = find_config(path)
    with cfg_path.open("rb") as fh:
        raw = tomllib.load(fh)

    keys = raw.get("keys", {})
    soniox = (keys.get("soniox") or "").strip() or os.environ.get("SONIOX_API_KEY", "")
    anthropic = (keys.get("anthropic") or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")

    stt = raw.get("stt", {})
    hotkey = raw.get("hotkey", {})
    inject = raw.get("inject", {})
    vocab = list(raw.get("vocab", {}).get("terms", []))
    cleanup = raw.get("cleanup", {})

    modes = {
        name: Mode(name=name, prompt=m.get("prompt", "").strip(), use_llm=bool(m.get("use_llm", True)))
        for name, m in raw.get("modes", {}).items()
    }
    if not modes:
        modes = {"working": Mode("working", "", use_llm=False)}

    default_mode = cleanup.get("default_mode") or next(iter(modes))
    if default_mode not in modes:
        default_mode = next(iter(modes))

    return Config(
        soniox_key=soniox,
        anthropic_key=anthropic,
        stt_model=stt.get("model", "stt-rt-v5"),
        sample_rate=int(stt.get("sample_rate", 16000)),
        language_hints=list(stt.get("language_hints", ["en", "zh"])),
        hotkey=str(hotkey.get("key", "f9")),
        inject_method=inject.get("method", "paste"),
        restore_clipboard=bool(inject.get("restore_clipboard", True)),
        vocab=vocab,
        cleanup_model=cleanup.get("model", "claude-haiku-4-5"),
        default_mode=default_mode,
        modes=modes,
    )
