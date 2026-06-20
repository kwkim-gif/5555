"""Model benchmark runner - measures RTF, WER/CER on a reference audio + transcript."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class BenchmarkResult:
    model_name: str
    audio_duration: float
    processing_time: float
    rtf: float
    wer: Optional[float] = None
    cer: Optional[float] = None
    vram_peak_mb: float = 0.0
    segment_count: int = 0
    hypothesis: str = ""


class BenchmarkRunner:
    def __init__(self, engine_config, preprocess_config) -> None:
        self.engine_config    = engine_config
        self.preprocess_config = preprocess_config

    def run(
        self,
        model_name: str,
        audio_path: str,
        reference_text: Optional[str] = None,
        progress_callback=None,
    ) -> BenchmarkResult:
        from audio.preprocess import AudioPreprocessor
        from engines import get_engine

        logger.info(f"[Benchmark] {model_name} on {Path(audio_path).name}")

        preprocessor = AudioPreprocessor(self.preprocess_config)
        processed    = preprocessor.prepare(audio_path, str(Path(audio_path).parent / "bench_tmp"))
        duration     = preprocessor.get_duration(processed)

        engine = get_engine(model_name, self.engine_config)
        engine.load_model()

        import torch
        vram_before = torch.cuda.memory_allocated() / 1024 ** 2 if torch.cuda.is_available() else 0.0

        segments = []
        t0 = time.perf_counter()
        gen = engine.transcribe(processed, progress_callback=progress_callback)
        try:
            while True:
                seg = next(gen)
                segments.append(seg)
        except StopIteration:
            pass

        elapsed   = time.perf_counter() - t0
        vram_peak = (
            torch.cuda.max_memory_allocated() / 1024 ** 2 - vram_before
            if torch.cuda.is_available() else 0.0
        )
        engine.unload_model()

        hypothesis = " ".join(s.text for s in segments)
        wer = cer = None

        if reference_text:
            try:
                import jiwer
                wer = jiwer.wer(reference_text.strip(), hypothesis.strip())
                cer = jiwer.cer(reference_text.strip(), hypothesis.strip())
            except Exception as exc:
                logger.warning(f"[Benchmark] WER/CER failed: {exc}")

        return BenchmarkResult(
            model_name=model_name,
            audio_duration=duration,
            processing_time=elapsed,
            rtf=elapsed / max(duration, 0.001),
            wer=wer, cer=cer,
            vram_peak_mb=vram_peak,
            segment_count=len(segments),
            hypothesis=hypothesis,
        )
