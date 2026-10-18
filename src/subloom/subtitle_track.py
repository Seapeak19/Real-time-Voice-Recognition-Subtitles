"""Parse and play external subtitle files (SRT, VTT, ASS)."""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)

_TIME_RE = re.compile(
    r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*$"
)
_TAG_RE = re.compile(r"<[^>]+>")
_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    start: float
    end: float
    text: str


def parse_timestamp(value: str) -> float:
    match = _TIME_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value!r}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    fraction = match.group(4).ljust(3, "0")[:3]
    return hours * 3600 + minutes * 60 + seconds + int(fraction) / 1000.0


def _clean_text(value: str) -> str:
    value = value.replace("\\N", "\n").replace("\\n", "\n")
    value = _ASS_TAG_RE.sub("", value)
    value = _TAG_RE.sub("", value)
    value = html.unescape(value)
    lines = [line.strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _parse_blocks(text: str) -> list[SubtitleCue]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", text)
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines or lines[0].strip().upper().startswith("WEBVTT"):
            lines = lines[1:]
        arrow_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if arrow_index is None:
            continue
        try:
            start_raw, end_raw = lines[arrow_index].split("-->", 1)
            start = parse_timestamp(start_raw)
            end = parse_timestamp(end_raw.strip().split()[0])
        except (ValueError, IndexError):
            continue
        body = _clean_text(" ".join(lines[arrow_index + 1 :]))
        if body and end > start:
            cues.append(SubtitleCue(start, end, body))
    return cues


def _parse_ass(text: str) -> list[SubtitleCue]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    fields: list[str] = [
        "Layer",
        "Start",
        "End",
        "Style",
        "Name",
        "MarginL",
        "MarginR",
        "MarginV",
        "Effect",
        "Text",
    ]
    cues: list[SubtitleCue] = []
    in_events = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower() == "[events]":
            in_events = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_events = line.lower() == "[events]"
            continue
        if not in_events:
            continue
        if line.lower().startswith("format:"):
            fields = [part.strip() for part in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:"):
            continue
        payload = line.split(":", 1)[1].lstrip()
        parts = payload.split(",", max(0, len(fields) - 1))
        if len(parts) < len(fields):
            continue
        row = dict(zip(fields, parts, strict=False))
        try:
            start = parse_timestamp(row["Start"])
            end = parse_timestamp(row["End"])
        except (KeyError, ValueError):
            continue
        body = _clean_text(row.get("Text", ""))
        if body and end > start:
            cues.append(SubtitleCue(start, end, body))
    return cues


def _decode_subtitle(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    if raw and raw[0::2].count(0) > len(raw) // 4:
        return raw.decode("utf-16-le", errors="replace")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\ufffd" not in text:
            return text
    return raw.decode("utf-8", errors="replace")


def parse_subtitle_file(path: str | Path) -> list[SubtitleCue]:
    source = Path(path)
    text = _decode_subtitle(source)
    suffix = source.suffix.lower()
    if suffix == ".ass" or suffix == ".ssa" or "[events]" in text.lower():
        cues = _parse_ass(text)
    else:
        cues = _parse_blocks(text)
    cues.sort(key=lambda cue: (cue.start, cue.end))
    # Avoid duplicate cues from overlapping tracks.
    unique: list[SubtitleCue] = []
    for cue in cues:
        if unique and cue == unique[-1]:
            continue
        unique.append(cue)
    return unique


class SubtitleTrackPlayer(QObject):
    """Wall-clock subtitle player; the offset aligns it with a video."""

    cue_changed = Signal(str, int)
    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cues: list[SubtitleCue] = []
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)
        self._started_at = 0.0
        self._offset = 0.0
        self._index = -1
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def cues(self) -> list[SubtitleCue]:
        return list(self._cues)

    @property
    def duration(self) -> float:
        return self._cues[-1].end if self._cues else 0.0

    def set_cues(self, cues: list[SubtitleCue]) -> None:
        self.stop()
        self._cues = list(cues)
        self._index = -1

    def load(self, path: str | Path) -> int:
        cues = parse_subtitle_file(path)
        self.set_cues(cues)
        return len(cues)

    def start(self, offset_seconds: float = 0.0) -> None:
        if not self._cues:
            return
        self._offset = float(offset_seconds)
        self._started_at = time.monotonic()
        self._index = -1
        self._active = True
        self._timer.start()
        self._tick()

    def stop(self) -> None:
        self._timer.stop()
        self._active = False
        self._index = -1

    def cue_at(self, elapsed: float) -> tuple[int, SubtitleCue | None]:
        if elapsed < 0:
            return -1, None
        for index, cue in enumerate(self._cues):
            if cue.start <= elapsed < cue.end:
                return index, cue
        return -1, None

    def _tick(self) -> None:
        if not self._active:
            return
        elapsed = time.monotonic() - self._started_at + self._offset
        index, cue = self.cue_at(elapsed)
        if index != self._index:
            self._index = index
            self.cue_changed.emit(cue.text if cue else "", index)
        if elapsed > self.duration + 1.0:
            self.stop()
            self.finished.emit()
