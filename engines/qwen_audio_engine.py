"""Qwen2-Audio engine for Japanese STT via HuggingFace."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Generator, Optional

from loguru import logger

from engines.base_engine import BaseSTTEngine, EngineConfig, TranscriptionResult, TranscriptionSegment
from subtitle.srt_writer import split_long_segment

MODEL_ID = "Qwen/Qwen2-Audio-7B-Instruct"


class QwenAudioEngine(BaseSTTEngine):
    """
    Qwen2-Audio-7B-Instruct — multilingual audio understanding model.
    Supports Japanese transcription with high accuracy.
    Uses HuggingFace transformers pipeline.
    """

    MODEL_NAME = "qwen2-audio-7b"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._processor = None
        self._model = None

    def load_model(self) -> None:
        import torch
        from transformers import AutoProcessor, Qwen2AudioForConditionalGeneration

        logger.info(f"[Qwen2Audio] Loading {MODEL_ID} on {self.device} ({self.compute_dtype})")

        torch_dtype = (
            torch.bfloat16 if self.compute_dtype == "bfloat16" else
            torch.float16  if self.compute_dtype == "float16"  else
            torch.float32
        )

        self._processor = AutoProcessor.from_pretrained(
            MODEL_ID, cache_dir=".model_cache"
        )
        self._model = Qwen2AudioForConditionalGeneration.from_pretrained(
            MODEL_ID,
            torch_dtype=torch_dtype,
            device_map=self.device if self.device == "cuda" else "cpu",
            low_cpu_mem_usage=True,
            cache_dir=".model_cache",
        )
        self._model.eval()
        self.is_loaded = True
        logger.info("[Qwen2Audio] Model loaded")

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Generator[TranscriptionSegment, None, TranscriptionResult]:
        if not self.is_loaded:
            self.load_model()

        logger.info(f"[Qwen2Audio] Transcribing: {Path(audio_path).name}")
        t0 = time.perf_counter()

        import librosa
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_dur  = len(audio) / sr
        chunk_sec  = self.config.chunk_duration_seconds
        chunk_samp = int(chunk_sec * sr)
        chunks = [audio[i: i + chunk_samp] for i in range(0, len(audio), chunk_samp)]

        collected: list[TranscriptionSegment] = []
        for idx, chunk in enumerate(chunks):
            offset    = idx * chunk_sec
            chunk_dur = len(chunk) / sr
            try:
                text = self._transcribe_chunk_audio(chunk, sr)
            except Exception as exc:
                logger.warning(f"[Qwen2Audio] Chunk {idx} failed: {exc}")
                text = ""

            if text.strip():
                raw_seg = TranscriptionSegment(
                    start=offset,
                    end=offset + chunk_dur,
                    text=text.strip(),
                )
                for sub in split_long_segment(raw_seg, max_chars=40):
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
        self._model = None
        self._processor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.is_loaded = False
        logger.info("[Qwen2Audio] Unloaded")

    def _transcribe_chunk_audio(self, audio_array, sr: int) -> str:
        import torch
        import numpy as np

        # Build conversation prompt for transcription
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "audio", "audio_url": "placeholder"},
                    {"type": "text",  "text": "Please transcribe this Japanese audio accurately."},
                ],
            }
        ]

        text_prompt = self._processor.apply_chat_template(
            conversation, add_generation_prompt=True, tokenize=False
        )

        inputs = self._processor(
            text=text_prompt,
            audios=[audio_array],
            sampling_rate=sr,
            return_tensors="pt",
        )

        dtype = next(self._model.parameters()).dtype
        device = next(self._model.parameters()).device
        inputs = {
            k: v.to(device).to(dtype) if v.dtype.is_floating_point else v.to(device)
            for k, v in inputs.items()
        }

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
            )

        # Decode only the newly generated tokens
        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[:, input_len:]
        text = self._processor.batch_decode(
            generated, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        return text.strip()
