from __future__ import annotations

from . import config as config_mod
from .cleanup.claude import ClaudeCleaner
from .cleanup.passthrough import Passthrough
from .stt.soniox import SonioxClient


def run_filetest(argv: list[str]) -> None:
    """Transcribe an audio file (wav/mp3/flac/…) through the real Soniox +
    cleanup pipeline. Works on any OS — no mic or Windows needed. Use it to
    verify your keys, language_hints, vocab, and mode prompts."""
    if not argv:
        print("usage: python -m typelessless filetest <audio-file> [mode]")
        return

    path = argv[0]
    cfg = config_mod.load()
    mode_name = argv[1] if len(argv) > 1 else cfg.default_mode
    mode = cfg.modes.get(mode_name) or next(iter(cfg.modes.values()))

    client = SonioxClient(cfg.soniox_key, cfg.stt_model, cfg.sample_rate, cfg.language_hints, cfg.vocab)
    session = client.open_session(audio_format="auto")
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(3840)
            if not chunk:
                break
            session.feed(chunk)
    transcript = session.finish(timeout=60.0)

    print("=== transcript ===")
    print(transcript)

    if cfg.anthropic_key and mode.use_llm:
        cleaner = ClaudeCleaner(cfg.anthropic_key, cfg.cleanup_model)
    else:
        cleaner = Passthrough()
    print(f"\n=== cleaned ({mode.name}) ===")
    print(cleaner.clean(transcript, mode, cfg.vocab))
