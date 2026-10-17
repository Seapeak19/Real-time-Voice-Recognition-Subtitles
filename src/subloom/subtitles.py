"""SRT/TXT export helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .models import CaptionSegment


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _text_for(segment: CaptionSegment, bilingual: bool) -> str:
    translated = (segment.translated_text or "").strip()
    source = (segment.source_text or "").strip()
    if bilingual and translated and source and translated != source:
        return f"{translated}\n{source}"
    return translated or source


def _dedupe_final(segments: Iterable[CaptionSegment]) -> list[CaptionSegment]:
    by_id: dict[str, CaptionSegment] = {}
    for segment in segments:
        if not segment.is_final:
            continue
        previous = by_id.get(segment.id)
        if previous is None or segment.revision >= previous.revision:
            by_id[segment.id] = segment
    return sorted(by_id.values(), key=lambda item: (item.start, item.end))


def build_srt(segments: Iterable[CaptionSegment], *, bilingual: bool = False) -> str:
    finals = _dedupe_final(segments)
    blocks: list[str] = []
    index = 0
    for segment in finals:
        text = _text_for(segment, bilingual)
        if not text:
            continue
        index += 1
        start = max(0.0, segment.start)
        end = max(start + 0.2, segment.end)
        blocks.append(f"{index}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{text}\n")
    return "\n".join(blocks)


def build_plain_text(segments: Iterable[CaptionSegment], *, bilingual: bool = False) -> str:
    finals = _dedupe_final(segments)
    lines = [_text_for(segment, bilingual) for segment in finals]
    return "\n".join(line for line in lines if line).strip() + ("\n" if any(lines) else "")


def save_srt(
    path: str | Path,
    segments: Iterable[CaptionSegment],
    *,
    bilingual: bool = False,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = build_srt(segments, bilingual=bilingual)
    target.write_text(content, encoding="utf-8-sig")
    return target


def safe_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return value[:80] or "transcript"
