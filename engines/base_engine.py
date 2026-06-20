"""Base STT engine interface - all engines must implement this contract."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Generator, Optional

import torch


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    confidence: float = 1.0
    words: list[dict] = field(default_factory=list)
    speaker: Optional[str] = None


@dataclass
class TranscriptionResult:
    segments: list[TranscriptionSegment]
    language: str = "ja"
    duration: float = 0.0
    model_name: str = ""
    processing_time: float = 0.0


@dataclass
class EngineConfig:
    device: str = "auto"
    fp16: bool = True
    bf16: bool = False
    batch_size: int = 8
    beam_size: int = 5
    temperature: float = 0.0
    best_of: int = 5
    patience: float = 1.0
    no_speech_threshold: float = 0.6
    logprob_threshold: float = -1.0
    compression_ratio_threshold: float = 2.4
    condition_on_previous_text: bool = False
    word_timestamps: bool = True
    min_segment_duration: float = 0.5
    max_segment_duration: float = 15.0
    hallucination_silence_threshold: float = 2.0
    chunk_duration_seconds: int = 600
    vad_enabled: bool = True
    language: str = "ja"


class BaseSTTEngine(abc.ABC):
    """Abstract base class for all STT engines."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model = None
        self.is_loaded: bool = False
        self._resolve_device()

    def _resolve_device(self) -> None:
        if self.config.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = self.config.device

    @property
    def compute_dtype(self) -> str:
        if self.device == "cuda":
            if self.config.bf16 and torch.cuda.is_bf16_supported():
                return "bfloat16"
            if self.config.fp16:
                return "float16"
        return "float32"

    @abc.abstractmethod
    def load_model(self) -> None:
        """Load the model into memory."""

    @abc.abstractmethod
    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        """Yield segments as they are decoded; return final TranscriptionResult."""

    @abc.abstractmethod
    def unload_model(self) -> None:
        """Release model from memory / VRAM."""

    def get_vram_usage_mb(self) -> float:
        if self.device != "cuda" or not torch.cuda.is_available():
            return 0.0
        return torch.cuda.memory_allocated() / 1024 ** 2

    def get_model_info(self) -> dict:
        return {
            "name": self.__class__.__name__,
            "device": self.device,
            "compute_dtype": self.compute_dtype,
            "is_loaded": self.is_loaded,
        }
