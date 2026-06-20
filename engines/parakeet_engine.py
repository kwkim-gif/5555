"""Parakeet-TDT_CTC-0.6b-ja engine via NVIDIA NeMo."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from engines.base_engine import BaseSTTEngine, EngineConfig, TranscriptionResult, TranscriptionSegment
from subtitle.srt_writer import split_long_segment

MODEL_NAME_NEMO = "nvidia/parakeet-tdt_ctc-0.6b-ja"
_CHUNK_MAX_S = 60   # NeMo is unstable on very long audio; keep chunks short


class ParakeetEngine(BaseSTTEngine):
    """Parakeet-TDT_CTC-0.6b-ja via NVIDIA NeMo with stability fixes."""

    MODEL_NAME = "parakeet-tdt_ctc-0.6b-ja"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._asr_model = None

    def load_model(self) -> None:
        logger.info(f"[Parakeet] Loading on {self.device}")
        try:
            import nemo.collections.asr as nemo_asr
            self._asr_model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME_NEMO)
            if self.device == "cuda":
                import torch
                self._asr_model = self._asr_model.cuda()
                if self.config.fp16 and torch.cuda.is_available():
                    self._asr_model = self._asr_model.half()
            self._asr_model.eval()
            self.is_loaded = True
            logger.info("[Parakeet] Loaded")
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
        t0 = time.perf_counter()

        import librosa
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_dur = len(audio) / sr

        # Use smaller chunks (60 s) for NeMo stability
        chunk_sec  = min(self.config.chunk_duration_seconds, _CHUNK_MAX_S)
        chunk_samp = int(chunk_sec * sr)
        chunks = [audio[i: i + chunk_samp] for i in range(0, len(audio), chunk_samp)]

        collected: list[TranscriptionSegment] = []
        for idx, chunk in enumerate(chunks):
            offset = idx * chunk_sec
            chunk_dur = len(chunk) / sr
            try:
                segs = self._transcribe_chunk(chunk, sr, offset, chunk_dur)
            except Exception as exc:
                logger.warning(f"[Parakeet] Chunk {idx} failed: {exc} — skipping")
                segs = []

            for seg in segs:
                # Split large monolithic segments into subtitle-sized pieces
                for sub in split_long_segment(seg, max_chars=40):
                    collected.append(sub)
                    yield sub

            if progress_callback:
                progress_callback(int((idx + 1) / len(chunks) * 100))

        return TranscriptionResult(
            segments=collected, language="ja", duration=total_dur,
            model_name=self.MODEL_NAME,
            processing_time=time.perf_counter() - t0,
        )

    def unload_model(self) -> None:
        import gc
        import torch
        self._asr_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[Parakeet] Unloaded")

    # ------------------------------------------------------------------

    def _transcribe_chunk(
        self,
        audio_array,
        sr: int,
        offset_sec: float,
        chunk_dur: float,
    ) -> list[TranscriptionSegment]:
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio_array, sr)
            tmp_path = tmp.name

        try:
            output = self._asr_model.transcribe(
                [tmp_path],
                batch_size=1,               # batch=1 for stability
                return_hypotheses=True,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not output:
            return []

        hyp  = output[0] if isinstance(output, list) else output
        text = getattr(hyp, "text", None) or str(hyp)
        text = text.strip()
        if not text:
            return []

        # Try word-level timestamps if available
        word_ts = getattr(hyp, "timestamp", None) or getattr(hyp, "timesteps", None)
        ts_dur  = getattr(hyp, "timestep_duration", None)

        segments: list[TranscriptionSegment] = []

        if word_ts is not None and ts_dur:
            # Build segments from word timestamps
            words = getattr(hyp, "words", None) or []
            if words:
                segments = self._segments_from_words(words, offset_sec, ts_dur)
            else:
                segments = self._segments_from_chars(text, word_ts, offset_sec, ts_dur)
        else:
            # No timestamp info — return full chunk as one segment (split later)
            segments.append(TranscriptionSegment(
                start=offset_sec,
                end=offset_sec + chunk_dur,
                text=text,
            ))

        return segments

    def _segments_from_words(self, words, offset: float, ts_dur: float) -> list[TranscriptionSegment]:
        segs: list[TranscriptionSegment] = []
        buf_text = ""
        buf_start = offset
        for w in words:
            word_text  = getattr(w, "word", str(w))
            word_start = offset + getattr(w, "start_offset", 0) * ts_dur
            word_end   = offset + getattr(w, "end_offset", 1)  * ts_dur
            buf_text += word_text
            if len(buf_text) >= 20 or word_text.endswith(("。", "！", "？")):
                segs.append(TranscriptionSegment(start=buf_start, end=word_end, text=buf_text.strip()))
                buf_text  = ""
                buf_start = word_end
        if buf_text.strip():
            segs.append(TranscriptionSegment(start=buf_start, end=buf_start + 2.0, text=buf_text.strip()))
        return segs

    def _segments_from_chars(self, text: str, timestamps, offset: float, ts_dur: float) -> list[TranscriptionSegment]:
        segs: list[TranscriptionSegment] = []
        cur_text  = ""
        seg_start = offset
        for i, (char, ts) in enumerate(zip(text, timestamps)):
            cur_text += char
            seg_end   = offset + (ts + 1) * ts_dur
            end_of_sent = char in ("。", "！", "？", "!", "?", "\n") or len(cur_text) >= 40
            if end_of_sent or i == len(text) - 1:
                if cur_text.strip():
                    segs.append(TranscriptionSegment(start=seg_start, end=seg_end, text=cur_text.strip()))
                seg_start = seg_end
                cur_text  = ""
        return segs
