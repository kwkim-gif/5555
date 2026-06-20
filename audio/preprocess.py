"""Audio preprocessing pipeline - noise reduction, normalization, VAD, resampling."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger


@dataclass
class PreprocessConfig:
    noise_reduction: bool = False
    volume_normalization: bool = True
    silence_removal: bool = False
    vad_enabled: bool = True
    resample_16k: bool = True
    target_sr: int = 16000
    noise_reduce_prop_decrease: float = 0.75
    silence_thresh_db: float = -40.0


class AudioPreprocessor:
    """Convert any supported media file to a clean 16 kHz mono WAV for STT."""

    SUPPORTED_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".ts"}
    SUPPORTED_AUDIO = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

    def __init__(self, config: PreprocessConfig) -> None:
        self.config = config

    def prepare(self, input_path: str, output_dir: Optional[str] = None) -> str:
        src = Path(input_path)
        if not src.exists():
            raise FileNotFoundError(f"Input not found: {src}")

        out_dir = Path(output_dir) if output_dir else src.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[Preprocess] Start: {src.name}")

        wav_path = self._extract_audio(src, out_dir)
        audio, sr = self._load_audio(wav_path)
        audio = self._apply_pipeline(audio, sr)

        final_path = out_dir / f"{src.stem}_processed.wav"
        self._save_audio(audio, sr, final_path)

        logger.info(f"[Preprocess] Done: {final_path}")
        return str(final_path)

    def get_duration(self, audio_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            return float(out.strip())
        except Exception:
            return 0.0

    def _extract_audio(self, src: Path, out_dir: Path) -> Path:
        raw_wav = out_dir / f"{src.stem}_raw.wav"
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(self.config.target_sr) if self.config.resample_16k else "48000",
            "-ac", "1",
            str(raw_wav),
        ]
        logger.debug(f"[Preprocess] ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")
        return raw_wav

    def _load_audio(self, wav_path: Path):
        import librosa
        return librosa.load(str(wav_path), sr=self.config.target_sr, mono=True)

    def _apply_pipeline(self, audio: np.ndarray, sr: int) -> np.ndarray:
        if self.config.noise_reduction:
            audio = self._reduce_noise(audio, sr)
        if self.config.volume_normalization:
            audio = self._normalize_volume(audio)
        if self.config.silence_removal:
            audio = self._remove_silence(audio, sr)
        if self.config.vad_enabled:
            audio = self._apply_vad(audio, sr)
        return audio

    def _reduce_noise(self, audio: np.ndarray, sr: int) -> np.ndarray:
        try:
            import noisereduce as nr
            logger.debug("[Preprocess] Noise reduction")
            return nr.reduce_noise(y=audio, sr=sr, prop_decrease=self.config.noise_reduce_prop_decrease, stationary=False)
        except ImportError:
            logger.warning("[Preprocess] noisereduce not installed, skipping")
            return audio

    def _normalize_volume(self, audio: np.ndarray) -> np.ndarray:
        import librosa
        logger.debug("[Preprocess] Volume normalization")
        return librosa.util.normalize(audio)

    def _remove_silence(self, audio: np.ndarray, sr: int) -> np.ndarray:
        import librosa
        logger.debug("[Preprocess] Silence removal")
        non_silent = librosa.effects.split(audio, top_db=abs(self.config.silence_thresh_db), frame_length=512, hop_length=128)
        if len(non_silent) == 0:
            return audio
        return np.concatenate([audio[s:e] for s, e in non_silent])

    def _apply_vad(self, audio: np.ndarray, sr: int) -> np.ndarray:
        try:
            import torch
            vad_model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad",
                force_reload=False, trust_repo=True,
            )
            (get_speech_ts, _, _, _, _) = utils
            tensor = torch.FloatTensor(audio)
            speech_ts = get_speech_ts(tensor, vad_model, sampling_rate=sr)
            if not speech_ts:
                return audio
            mask = np.zeros(len(audio), dtype=np.float32)
            for ts in speech_ts:
                mask[ts["start"]: ts["end"]] = 1.0
            logger.debug(f"[Preprocess] VAD: {mask.sum() / sr:.1f}s speech retained")
            return audio * mask
        except Exception as exc:
            logger.warning(f"[Preprocess] VAD failed ({exc}), skipping")
            return audio

    def _save_audio(self, audio: np.ndarray, sr: int, path: Path) -> None:
        import soundfile as sf
        sf.write(str(path), audio.astype(np.float32), sr, subtype="PCM_16")
