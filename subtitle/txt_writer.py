"""Plain-text and JSON subtitle writers."""

from __future__ import annotations

import json
from pathlib import Path

from engines.base_engine import TranscriptionSegment


class TXTWriter:
    def write(self, segments: list[TranscriptionSegment], output_path: str) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(seg.text.strip() for seg in segments if seg.text.strip())
        out.write_text(text, encoding="utf-8")
        return str(out)


class JSONWriter:
    def write(self, segments: list[TranscriptionSegment], output_path: str) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "index": i + 1,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "confidence": round(seg.confidence, 4),
                "words": seg.words,
            }
            for i, seg in enumerate(segments)
            if seg.text.strip()
        ]
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out)
