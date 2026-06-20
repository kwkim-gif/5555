"""SRT subtitle writer with broadcast-quality segment merging."""

from __future__ import annotations

from pathlib import Path

from engines.base_engine import TranscriptionSegment


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _merge_segments(
    segments: list[TranscriptionSegment],
    max_chars: int = 40,
    max_duration: float = 7.0,
    merge_gap: float = 0.3,
) -> list[TranscriptionSegment]:
    """Merge short consecutive segments for broadcast-style subtitles."""
    if not segments:
        return []

    merged: list[TranscriptionSegment] = []
    buf = segments[0]

    for seg in segments[1:]:
        gap = seg.start - buf.end
        combined_text = buf.text + seg.text
        combined_dur = seg.end - buf.start

        if gap <= merge_gap and len(combined_text) <= max_chars and combined_dur <= max_duration:
            buf = TranscriptionSegment(
                start=buf.start,
                end=seg.end,
                text=combined_text,
                confidence=min(buf.confidence, seg.confidence),
                words=buf.words + seg.words,
            )
        else:
            merged.append(buf)
            buf = seg

    merged.append(buf)
    return merged


class SRTWriter:
    """Write TranscriptionSegment list to an SRT file."""

    def __init__(
        self,
        merge: bool = True,
        max_chars_per_line: int = 40,
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

        if self.merge:
            segments = _merge_segments(
                segments,
                max_chars=self.max_chars_per_line,
                max_duration=self.max_segment_duration,
                merge_gap=self.merge_gap,
            )

        lines: list[str] = []
        for i, seg in enumerate(segments, start=1):
            if not seg.text.strip():
                continue
            lines.append(str(i))
            lines.append(f"{_fmt_time(seg.start)} --> {_fmt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        return str(out)
