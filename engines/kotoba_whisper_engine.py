"""Kotoba-Whisper-v2 engine using Faster-Whisper backend."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from engines.base_engine import BaseSTTEngine, EngineConfig, TranscriptionResult, TranscriptionSegment

MODEL_ID = "kotoba-tech/kotoba-whisper-v2.0"
MODEL_ID_FASTER = "kotoba-tech/kotoba-whisper-v2.0-faster"


class KotobaWhisperEngine(BaseSTTEngine):
    """
    Kotoba-Whisper-v2 — optimised for broadcast-quality Japanese subtitles.
    Uses Faster-Whisper (CTranslate2) backend when available for speed and
    lower VRAM consumption.  Falls back to HuggingFace pipeline otherwise.
    """

    MODEL_NAME = "kotoba-whisper-v2"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._use_faster: bool = False
        self._pipeline = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        logger.info(f"[KotobaWhisper] Loading model on {self.device} ({self.compute_dtype})")
        try:
            self._load_faster_whisper()
            self._use_faster = True
            logger.info("[KotobaWhisper] Faster-Whisper backend loaded")
        except Exception as exc:
            logger.warning(f"[KotobaWhisper] Faster-Whisper unavailable ({exc}), falling back to HF pipeline")
            self._load_hf_pipeline()
            self._use_faster = False
        self.is_loaded = True

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        if not self.is_loaded:
            self.load_model()

        path = Path(audio_path)
        logger.info(f"[KotobaWhisper] Transcribing: {path.name}")
        start_time = time.perf_counter()

        if self._use_faster:
            result = yield from self._transcribe_faster(audio_path, progress_callback)
        else:
            result = yield from self._transcribe_hf(audio_path, progress_callback)

        result.processing_time = time.perf_counter() - start_time
        result.model_name = self.MODEL_NAME
        return result

    def unload_model(self) -> None:
        import gc
        import torch

        self.model = None
        self._pipeline = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[KotobaWhisper] Model unloaded")

    # ------------------------------------------------------------------
    # Faster-Whisper path
    # ------------------------------------------------------------------

    def _load_faster_whisper(self) -> None:
        from faster_whisper import WhisperModel

        ct2_device = "cuda" if self.device == "cuda" else "cpu"
        self.model = WhisperModel(
            MODEL_ID_FASTER,
            device=ct2_device,
            compute_type=self.compute_dtype,
            num_workers=2,
            download_root=".model_cache",
        )

    def _transcribe_faster(
        self,
        audio_path: str,
        progress_callback: Optional[callable],
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        import soundfile as sf

        audio_info = sf.info(audio_path)
        total_duration = audio_info.duration

        segments_iter, info = self.model.transcribe(
            audio_path,
            language=self.config.language,
            beam_size=self.config.beam_size,
            temperature=self.config.temperature,
            best_of=self.config.best_of,
            patience=self.config.patience,
            no_speech_threshold=self.config.no_speech_threshold,
            log_prob_threshold=self.config.logprob_threshold,
            compression_ratio_threshold=self.config.compression_ratio_threshold,
            condition_on_previous_text=self.config.condition_on_previous_text,
            word_timestamps=self.config.word_timestamps,
            hallucination_silence_threshold=self.config.hallucination_silence_threshold,
            vad_filter=self.config.vad_enabled,
            vad_parameters={
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "min_silence_duration_ms": 500,
            },
            chunk_length=30,
            batch_size=self.config.batch_size,
        )

        collected: list[TranscriptionSegment] = []
        for seg in segments_iter:
            words = []
            if self.config.word_timestamps and seg.words:
                words = [
                    {"start": w.start, "end": w.end, "word": w.word, "prob": w.probability}
                    for w in seg.words
                ]
            segment = TranscriptionSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                confidence=seg.avg_logprob,
                words=words,
            )
            collected.append(segment)
            if progress_callback and total_duration > 0:
                progress_callback(int(seg.end / total_duration * 100))
            yield segment

        return TranscriptionResult(
            segments=collected,
            language=info.language,
            duration=total_duration,
        )

    # ------------------------------------------------------------------
    # HuggingFace pipeline path (fallback)
    # ------------------------------------------------------------------

    def _load_hf_pipeline(self) -> None:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        torch_dtype = (
            torch.bfloat16 if self.compute_dtype == "bfloat16"
            else torch.float16 if self.compute_dtype == "float16"
            else torch.float32
        )
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            MODEL_ID,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            cache_dir=".model_cache",
        )
        model.to(self.device)
        processor = AutoProcessor.from_pretrained(MODEL_ID, cache_dir=".model_cache")
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            chunk_length_s=30,
            batch_size=self.config.batch_size,
            torch_dtype=torch_dtype,
            device=self.device,
            return_timestamps=True,
        )

    def _transcribe_hf(
        self,
        audio_path: str,
        progress_callback: Optional[callable],
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        import librosa

        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_duration = len(audio) / sr

        result = self._pipeline(
            {"array": audio, "sampling_rate": sr},
            generate_kwargs={"language": "japanese", "task": "transcribe"},
            return_timestamps=True,
        )

        collected: list[TranscriptionSegment] = []
        chunks = result.get("chunks", [])
        for i, chunk in enumerate(chunks):
            ts = chunk.get("timestamp", (0.0, 0.0)) or (0.0, 0.0)
            segment = TranscriptionSegment(
                start=float(ts[0] or 0.0),
                end=float(ts[1] or ts[0] or 0.0),
                text=chunk["text"].strip(),
            )
            collected.append(segment)
            if progress_callback:
                progress_callback(int((i + 1) / max(len(chunks), 1) * 100))
            yield segment

        return TranscriptionResult(
            segments=collected,
            language="ja",
            duration=total_duration,
        )
