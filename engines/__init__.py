"""STT engine registry."""

from __future__ import annotations

from engines.base_engine import BaseSTTEngine, EngineConfig
from engines.kotoba_whisper_engine import KotobaWhisperEngine
from engines.parakeet_engine import ParakeetEngine
from engines.reazonspeech_engine import ReazonSpeechEngine

ENGINE_REGISTRY: dict[str, type[BaseSTTEngine]] = {
    "kotoba-whisper-v2": KotobaWhisperEngine,
    "parakeet-tdt_ctc-0.6b-ja": ParakeetEngine,
    "reazonspeech-k2-v2": ReazonSpeechEngine,
}


def get_engine(name: str, config: EngineConfig) -> BaseSTTEngine:
    cls = ENGINE_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown engine: {name!r}. Available: {list(ENGINE_REGISTRY)}")
    return cls(config)
