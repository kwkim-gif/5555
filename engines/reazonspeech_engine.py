"""ReazonSpeech K2-v2 engine."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from engines.base_engine import BaseSTTEngine, EngineConfig, TranscriptionResult, TranscriptionSegment


class ReazonSpeechEngine(BaseSTTEngine):
    """ReazonSpeech K2-v2 - high-accuracy Japanese ASR trained on broadcast data."""

    MODEL_NAME = "reazonspeech-k2-v2"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._transcriber = None

    def load_model(self) -> None:
        logger.info(f"[ReazonSpeech] Loading on {self.device}")
        try:
            from reazonspeech.k2.asr import load_model
            self._transcriber = load_model(device=self.device)
            self.is_loaded = True
            logger.info("[ReazonSpeech] Model loaded")
        except ImportError:
            logger.error("[ReazonSpeech] Package not found. Install: pip install reazonspeech-k2-v2")
            raise
        except Exception as exc:
            logger.error(f"[ReazonSpeech] Load failed: {exc}")
            raise

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        if not self.is_loaded:
            self.load_model()

        from reazonspeech.k2.asr import audio_from_path, transcribe

        logger.info(f"[ReazonSpeech] Transcribing: {Path(audio_path).name}")
        start_time = time.perf_counter()

        audio = audio_from_path(audio_path)
        total_duration = len(audio.waveform) / audio.samplerate if audio.samplerate else 0.0

        result = transcribe(self._transcriber, audio)
        segments_raw = getattr(result, "segments", []) or []
        if not segments_raw and hasattr(result, "subwords"):
            segments_raw = self._group_subwords(result.subwords)

        collected: list[TranscriptionSegment] = []
        for i, seg in enumerate(segments_raw):
            start = getattr(seg, "start_seconds", getattr(seg, "start", 0.0))
            end   = getattr(seg, "end_seconds",   getattr(seg, "end",   0.0))
            text  = getattr(seg, "text", "").strip()
            if not text:
                continue
            segment = TranscriptionSegment(start=start, end=end, text=text)
            collected.append(segment)
            if progress_callback and total_duration > 0:
                progress_callback(int(end / total_duration * 100))
            yield segment

        return TranscriptionResult(
            segments=collected, language="ja", duration=total_duration,
            model_name=self.MODEL_NAME, processing_time=time.perf_counter() - start_time,
        )

    def unload_model(self) -> None:
        import gc, torch
        self._transcriber = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[ReazonSpeech] Unloaded")

    def _group_subwords(self, subwords) -> list:
        groups: list[dict] = []
        cur_text = ""
        seg_start = 0.0
        for sw in subwords:
            token = getattr(sw, "token", "")
            ts    = getattr(sw, "time_seconds", 0.0)
            if not cur_text:
                seg_start = ts
            cur_text += token
            if token in ("。", "！", "？", "\n"):  # Japanese full-stop / exclamation / question
                groups.append({"start": seg_start, "end": ts, "text": cur_text.strip()})
                cur_text = ""
        if cur_text.strip():
            groups.append({"start": seg_start, "end": seg_start + 3.0, "text": cur_text.strip()})

        class _Seg:
            def __init__(self, d: dict) -> None:
                self.start = d["start"]
                self.end   = d["end"]
                self.text  = d["text"]

        return [_Seg(g) for g in groups]
