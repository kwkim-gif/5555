"""Parakeet-TDT_CTC-0.6b-ja engine via NVIDIA NeMo."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from engines.base_engine import BaseSTTEngine, EngineConfig, TranscriptionResult, TranscriptionSegment

MODEL_NAME_NEMO = "nvidia/parakeet-tdt_ctc-0.6b-ja"


class ParakeetEngine(BaseSTTEngine):
    """
    NVIDIA Parakeet-TDT_CTC-0.6b-ja — excels at long-form audio with
    CUDA-optimised batched inference and FP16/BF16 support.
    """

    MODEL_NAME = "parakeet-tdt_ctc-0.6b-ja"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._asr_model = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        logger.info(f"[Parakeet] Loading {MODEL_NAME_NEMO} on {self.device}")
        try:
            import nemo.collections.asr as nemo_asr

            self._asr_model = nemo_asr.models.ASRModel.from_pretrained(
                model_name=MODEL_NAME_NEMO
            )
            if self.device == "cuda":
                self._asr_model = self._asr_model.cuda()
                if self.config.fp16:
                    self._asr_model = self._asr_model.half()
            self._asr_model.eval()
            self.is_loaded = True
            logger.info("[Parakeet] Model loaded successfully")
        except Exception as exc:
            logger.error(f"[Parakeet] Failed to load model: {exc}")
            raise

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        if not self.is_loaded:
            self.load_model()

        path = Path(audio_path)
        logger.info(f"[Parakeet] Transcribing: {path.name}")
        start_time = time.perf_counter()

        import librosa
        import numpy as np

        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_duration = len(audio) / sr
        chunk_samples = int(self.config.chunk_duration_seconds * sr)
        collected: list[TranscriptionSegment] = []

        chunks = [
            audio[i: i + chunk_samples]
            for i in range(0, len(audio), chunk_samples)
        ]

        for chunk_idx, chunk in enumerate(chunks):
            chunk_start_sec = chunk_idx * self.config.chunk_duration_seconds
            segments = self._transcribe_chunk(chunk, sr, chunk_start_sec)
            for seg in segments:
                collected.append(seg)
                yield seg
            if progress_callback:
                progress_callback(int((chunk_idx + 1) / len(chunks) * 100))

        return TranscriptionResult(
            segments=collected,
            language="ja",
            duration=total_duration,
            model_name=self.MODEL_NAME,
            processing_time=time.perf_counter() - start_time,
        )

    def unload_model(self) -> None:
        import gc
        import torch

        self._asr_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[Parakeet] Model unloaded")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transcribe_chunk(
        self,
        audio_array,
        sr: int,
        offset_sec: float,
    ) -> list[TranscriptionSegment]:
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio_array, sr)
            tmp_path = tmp.name

        try:
            output = self._asr_model.transcribe(
                [tmp_path],
                batch_size=self.config.batch_size,
                return_hypotheses=True,
                timestamps=True,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        segments: list[TranscriptionSegment] = []
        if not output:
            return segments

        hyp = output[0] if isinstance(output, list) else output
        text = hyp.text if hasattr(hyp, "text") else str(hyp)
        timestep_duration = getattr(hyp, "timestep_duration", None)
        timestamps = getattr(hyp, "timesteps", None)

        if timestamps is not None and timestep_duration:
            current_text = ""
            seg_start = offset_sec
            for i, (char, ts) in enumerate(zip(text, timestamps)):
                current_text += char
                if char in "。！？\n" or i == len(text) - 1:
                    seg_end = offset_sec + (ts + 1) * timestep_duration
                    if current_text.strip():
                        segments.append(TranscriptionSegment(
                            start=seg_start,
                            end=seg_end,
                            text=current_text.strip(),
                        ))
                    seg_start = seg_end
                    current_text = ""
        else:
            chunk_dur = len(audio_array) / sr
            if text.strip():
                segments.append(TranscriptionSegment(
                    start=offset_sec,
                    end=offset_sec + chunk_dur,
                    text=text.strip(),
                ))

        return segments
