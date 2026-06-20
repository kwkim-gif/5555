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
    Parakeet-TDT_CTC-0.6b-ja - long-form audio with CUDA-optimised batched inference.
    """

    MODEL_NAME = "parakeet-tdt_ctc-0.6b-ja"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._asr_model = None

    def load_model(self) -> None:
        logger.info(f"[Parakeet] Loading {MODEL_NAME_NEMO} on {self.device}")
        try:
            import nemo.collections.asr as nemo_asr
            self._asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODEL_NAME_NEMO)
            if self.device == "cuda":
                self._asr_model = self._asr_model.cuda()
                if self.config.fp16:
                    self._asr_model = self._asr_model.half()
            self._asr_model.eval()
            self.is_loaded = True
            logger.info("[Parakeet] Model loaded")
        except Exception as exc:
            logger.error(f"[Parakeet] Load failed: {exc}")
            raise

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        if not self.is_loaded:
            self.load_model()

        logger.info(f"[Parakeet] Transcribing: {Path(audio_path).name}")
        start_time = time.perf_counter()

        import librosa
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_duration = len(audio) / sr
        chunk_samples = int(self.config.chunk_duration_seconds * sr)
        chunks = [audio[i: i + chunk_samples] for i in range(0, len(audio), chunk_samples)]
        collected: list[TranscriptionSegment] = []

        for idx, chunk in enumerate(chunks):
            offset = idx * self.config.chunk_duration_seconds
            for seg in self._transcribe_chunk(chunk, sr, offset):
                collected.append(seg)
                yield seg
            if progress_callback:
                progress_callback(int((idx + 1) / len(chunks) * 100))

        return TranscriptionResult(
            segments=collected, language="ja", duration=total_duration,
            model_name=self.MODEL_NAME, processing_time=time.perf_counter() - start_time,
        )

    def unload_model(self) -> None:
        import gc, torch
        self._asr_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[Parakeet] Unloaded")

    def _transcribe_chunk(self, audio_array, sr: int, offset_sec: float) -> list[TranscriptionSegment]:
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio_array, sr)
            tmp_path = tmp.name

        try:
            output = self._asr_model.transcribe(
                [tmp_path], batch_size=self.config.batch_size,
                return_hypotheses=True, timestamps=True,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        segments: list[TranscriptionSegment] = []
        if not output:
            return segments

        hyp = output[0] if isinstance(output, list) else output
        text = hyp.text if hasattr(hyp, "text") else str(hyp)
        ts_duration = getattr(hyp, "timestep_duration", None)
        timestamps  = getattr(hyp, "timesteps", None)

        if timestamps is not None and ts_duration:
            cur_text = ""
            seg_start = offset_sec
            for i, (char, ts) in enumerate(zip(text, timestamps)):
                cur_text += char
                if char in (".", "!", "?", "\n") or i == len(text) - 1:
                    seg_end = offset_sec + (ts + 1) * ts_duration
                    if cur_text.strip():
                        segments.append(TranscriptionSegment(start=seg_start, end=seg_end, text=cur_text.strip()))
                    seg_start = seg_end
                    cur_text = ""
        else:
            chunk_dur = len(audio_array) / sr
            if text.strip():
                segments.append(TranscriptionSegment(start=offset_sec, end=offset_sec + chunk_dur, text=text.strip()))

        return segments
