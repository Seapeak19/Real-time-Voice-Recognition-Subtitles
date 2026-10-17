"""In-memory transcript used by the UI and exports."""

from __future__ import annotations

from collections.abc import Iterable

from .models import CaptionSegment
from .subtitles import build_plain_text, build_srt


class TranscriptStore:
    def __init__(self) -> None:
        self._segments: list[CaptionSegment] = []
        self._index: dict[str, int] = {}

    @property
    def segments(self) -> list[CaptionSegment]:
        return list(self._segments)

    @property
    def finals(self) -> list[CaptionSegment]:
        return [segment for segment in self._segments if segment.is_final]

    def clear(self) -> None:
        self._segments.clear()
        self._index.clear()

    def upsert(self, incoming: CaptionSegment) -> CaptionSegment:
        """Merge an update, replacing stale partial translations when text changes."""
        index = self._index.get(incoming.id)
        if index is None:
            self._index[incoming.id] = len(self._segments)
            self._segments.append(incoming)
            return incoming
        current = self._segments[index]
        if incoming.revision < current.revision:
            return current
        if incoming.revision > current.revision:
            current.translated_text = ""
            current.provider = ""
            current.warning = ""
            current.translation_pending = incoming.translation_pending
        current.source_text = incoming.source_text
        current.source_lang = incoming.source_lang
        current.target_lang = incoming.target_lang
        current.start = incoming.start
        current.end = incoming.end
        current.is_final = incoming.is_final
        current.revision = incoming.revision
        if incoming.translated_text:
            current.translated_text = incoming.translated_text
        if incoming.provider:
            current.provider = incoming.provider
        if incoming.warning:
            current.warning = incoming.warning
        if not incoming.translation_pending:
            current.translation_pending = False
        return current

    def srt(self, bilingual: bool = False) -> str:
        return build_srt(self._segments, bilingual=bilingual)

    def text(self, bilingual: bool = False) -> str:
        return build_plain_text(self._segments, bilingual=bilingual)

    def latest(self, count: int = 1) -> list[CaptionSegment]:
        return self._segments[-max(1, count) :]

    def replace_all(self, segments: Iterable[CaptionSegment]) -> None:
        self.clear()
        for segment in segments:
            self.upsert(segment)
