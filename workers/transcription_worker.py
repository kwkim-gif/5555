"""QThread worker - runs preprocessing + transcription off the UI thread."""

from __future__ import annotations

import platform
import time
import traceback
from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import QThread, Signal

from audio.preprocess import AudioPreprocessor, PreprocessConfig
from engines import get_engine
from engines.base_engine import EngineConfig, TranscriptionResult, TranscriptionSegment
from subtitle.srt_writer import SRTWriter
from subtitle.txt_writer import JSONWriter, TXTWriter


class TranscriptionWorker(QThread):
    """
    Signals
    -------
    progress(int)              - 0-100 overall progress
    segment_ready(str, float, float) - text, start, end
    log_message(str)           - log line for UI log panel
    vram_usage(float)          - VRAM MB
    finished(str)              - output directory on success
    error(str)                 - error message on failure
    """

    progress     = Signal(int)
    segment_ready = Signal(str, float, float)
    log_message  = Signal(str)
    vram_usage   = Signal(float)
    finished     = Signal(str)
    error        = Signal(str)

    def __init__(
        self,
        input_path: str,
        model_name: str,
        output_dir: str,
        engine_config: EngineConfig,
        preprocess_config: PreprocessConfig,
        output_formats: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.model_name = model_name
        self.output_dir = output_dir
        self.engine_config = engine_config
        self.preprocess_config = preprocess_config
        self.output_formats = output_formats
        self._stop_requested = False
        self._engine = None

    def request_stop(self) -> None:
        self._stop_requested = True
        self._log("Stop requested")

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error(f"Worker error:\n{tb}")
            self._save_error_log(exc, tb)
            self.error.emit(str(exc))

    def _run(self) -> None:
        start_total = time.perf_counter()
        self._log(f"Transcription started: {Path(self.input_path).name}")
        self._log(f"  Model: {self.model_name}")

        # Step 1: Preprocess
        self._log("Extracting and preprocessing audio...")
        preprocessor = AudioPreprocessor(self.preprocess_config)
        processed_path = preprocessor.prepare(self.input_path, self.output_dir)
        self._log(f"Preprocessing done: {Path(processed_path).name}")
        self.progress.emit(5)

        if self._stop_requested:
            return

        # Step 2: Load model
        self._log("Loading model...")
        self._engine = get_engine(self.model_name, self.engine_config)
        self._engine.load_model()
        self._log(f"Model loaded (device={self._engine.device}, dtype={self._engine.compute_dtype})")
        self.progress.emit(10)

        # Step 3: Transcribe
        self._log("Transcription started...")
        segments: list[TranscriptionSegment] = []

        def on_progress(pct: int) -> None:
            self.progress.emit(10 + int(pct * 0.85))
            self._emit_vram()

        gen = self._engine.transcribe(processed_path, progress_callback=on_progress)
        result: Optional[TranscriptionResult] = None
        try:
            while True:
                if self._stop_requested:
                    self._log("Transcription stopped by user")
                    break
                seg = next(gen)
                segments.append(seg)
                self.segment_ready.emit(seg.text, seg.start, seg.end)
                self._log(f"[{seg.start:.1f}s] {seg.text}")
        except StopIteration as si:
            result = si.value

        if result is None:
            from engines.base_engine import TranscriptionResult as TR
            result = TR(segments=segments, language="ja")

        # Step 4: Save outputs
        stem = Path(self.input_path).stem
        out_dir = Path(self.output_dir)
        saved: list[str] = []

        if "srt" in self.output_formats:
            path = SRTWriter().write(result.segments, str(out_dir / f"{stem}.srt"))
            saved.append(path)
            self._log(f"SRT saved: {path}")

        if "txt" in self.output_formats:
            path = TXTWriter().write(result.segments, str(out_dir / f"{stem}.txt"))
            saved.append(path)
            self._log(f"TXT saved: {path}")

        if "json" in self.output_formats:
            path = JSONWriter().write(result.segments, str(out_dir / f"{stem}.json"))
            saved.append(path)
            self._log(f"JSON saved: {path}")

        elapsed = time.perf_counter() - start_total
        self._log(f"Done! Time: {elapsed:.1f}s, Segments: {len(result.segments)}")
        self.progress.emit(100)

        self._engine.unload_model()
        self.finished.emit(str(out_dir))

    def _log(self, msg: str) -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        logger.info(msg)
        self.log_message.emit(line)

    def _emit_vram(self) -> None:
        if self._engine:
            self.vram_usage.emit(self._engine.get_vram_usage_mb())

    def _save_error_log(self, exc: Exception, tb: str) -> None:
        import datetime
        import sys

        err_dir = Path("error_logs")
        err_dir.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = err_dir / f"error_{ts}.log"
        content = (
            f"Time: {datetime.datetime.now().isoformat()}\n"
            f"Model: {self.model_name}\n"
            f"Input: {self.input_path}\n"
            f"OS: {platform.platform()}\n"
            f"Python: {sys.version}\n"
            f"\n--- Exception ---\n{exc}\n"
            f"\n--- Traceback ---\n{tb}"
        )
        log_file.write_text(content, encoding="utf-8")
        logger.error(f"Error log saved: {log_file}")
