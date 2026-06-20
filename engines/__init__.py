"""STT engine registry - engines are registered only if their deps are available."""

from __future__ import annotations

from engines.base_engine import BaseSTTEngine, EngineConfig
from engines.kotoba_whisper_engine import KotobaWhisperEngine
from engines.parakeet_engine import ParakeetEngine
from engines.reazonspeech_engine import ReazonSpeechEngine

ENGINE_REGISTRY: dict[str, type[BaseSTTEngine]] = {
    "kotoba-whisper-v2":       KotobaWhisperEngine,
    "parakeet-tdt_ctc-0.6b-ja": ParakeetEngine,
    "reazonspeech-k2-v2":      ReazonSpeechEngine,
}

# Mark engines whose optional deps are missing so the UI can warn the user
UNAVAILABLE_ENGINES: dict[str, str] = {}

def _check_deps() -> None:
    checks = {
        "reazonspeech-k2-v2": ("reazonspeech", "pip install git+https://github.com/reazon-research/reazonspeech.git#subdirectory=espnet"),
        "parakeet-tdt_ctc-0.6b-ja": ("nemo", "pip install nemo_toolkit[asr]"),
    }
    for engine_name, (module, hint) in checks.items():
        try:
            __import__(module)
        except ImportError:
            UNAVAILABLE_ENGINES[engine_name] = hint

_check_deps()


def get_engine(name: str, config: EngineConfig) -> BaseSTTEngine:
    if name in UNAVAILABLE_ENGINES:
        raise RuntimeError(
            f"Engine '{name}' requires additional packages.\n"
            f"Install with: {UNAVAILABLE_ENGINES[name]}"
        )
    cls = ENGINE_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown engine: {name!r}. Available: {list(ENGINE_REGISTRY)}")
    return cls(config)
