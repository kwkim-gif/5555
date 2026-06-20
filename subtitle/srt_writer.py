"""SRT writer with Japanese-aware sentence splitting for long/monolithic segments."""

from __future__ import annotations

import re
from pathlib import Path

from engines.base_engine import TranscriptionSegment

# Japanese sentence-ending characters used as split points
_JP_ENDS = re.compile(r'([。！？!?]+|[\n]{1,})')
_MAX_CHARS = 40       # broadcast standard per subtitle card


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int((seconds % 1) * 1000)
    s  = int(seconds) % 60
    m  = int(seconds // 60) % 60
    h  = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_by_punctuation(text: str) -> list[str]:
    """Split Japanese text at sentence boundaries, keeping punctuation attached."""
    parts = _JP_ENDS.split(text)
    sentences: list[str] = []
    buf = ""
    for part in parts:
        if _JP_ENDS.match(part):
            buf += part
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
        else:
            buf += part
    if buf.strip():
        sentences.append(buf.strip())
    return sentences or [text]


def _split_long_text(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """First split by punctuation, then by char limit."""
    sentences = _split_by_punctuation(text)
    result: list[str] = []
    for sent in sentences:
        while len(sent) > max_chars:
            result.append(sent[:max_chars])
            sent = sent[max_chars:]
        if sent:
            result.append(sent)
    return result or [text]


def split_long_segment(seg: TranscriptionSegment, max_chars: int = _MAX_CHARS) -> list[TranscriptionSegment]:
    """
    Break a monolithic segment (e.g. Parakeet single-chunk output) into
    multiple subtitle-sized pieces with linearly interpolated timestamps.
    """
    if len(seg.text) <= max_chars:
        return [seg]

    pieces = _split_long_text(seg.text, max_chars)
    total_chars = sum(len(p) for p in pieces)
    duration = max(seg.end - seg.start, 0.1)
    result: list[TranscriptionSegment] = []
    cursor = seg.start

    for piece in pieces:
        proportion = len(piece) / total_chars
        piece_dur  = duration * proportion
        result.append(TranscriptionSegment(
            start=round(cursor, 3),
            end=round(cursor + piece_dur, 3),
            text=piece,
            confidence=seg.confidence,
        ))
        cursor += piece_dur

    return result


def _merge_segments(
    segments: list[TranscriptionSegment],
    max_chars: int = _MAX_CHARS,
    max_duration: float = 7.0,
    merge_gap: float = 0.3,
) -> list[TranscriptionSegment]:
    if not segments:
        return []

    merged: list[TranscriptionSegment] = []
    buf = segments[0]

    for seg in segments[1:]:
        gap          = seg.start - buf.end
        combined     = buf.text + seg.text
        combined_dur = seg.end - buf.start

        if gap <= merge_gap and len(combined) <= max_chars and combined_dur <= max_duration:
            buf = TranscriptionSegment(
                start=buf.start, end=seg.end, text=combined,
                confidence=min(buf.confidence, seg.confidence),
                words=buf.words + seg.words,
            )
        else:
            merged.append(buf)
            buf = seg

    merged.append(buf)
    return merged


class SRTWriter:
    def __init__(
        self,
        merge: bool = True,
        max_chars_per_line: int = _MAX_CHARS,
        max_segment_duration: float = 7.0,
        merge_gap: float = 0.3,
    ) -> None:
        self.merge = merge
        self.max_chars_per_line = max_chars_per_line
        self.max_segment_duration = max_segment_duration
        self.merge_gap = merge_gap

    def write(self, segments: list[TranscriptionSegment], output_path: str) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: split any monolithic (too-long) segments
        expanded: list[TranscriptionSegment] = []
        for seg in segments:
            expanded.extend(split_long_segment(seg, self.max_chars_per_line))

        # Step 2: merge very short adjacent segments
        if self.merge:
            expanded = _merge_segments(
                expanded,
                max_chars=self.max_chars_per_line,
                max_duration=self.max_segment_duration,
                merge_gap=self.merge_gap,
            )

        lines: list[str] = []
        idx = 1
        for seg in expanded:
            if not seg.text.strip():
                continue
            lines.append(str(idx))
            lines.append(f"{_fmt_time(seg.start)} --> {_fmt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
            idx += 1

        out.write_text("\n".join(lines), encoding="utf-8")
        return str(out)
