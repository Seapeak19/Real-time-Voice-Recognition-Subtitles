"""Tracks and stabilizes automatic source-language detection."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from ..languages import from_whisper, normalize_code


@dataclass
class _Vote:
    code: str
    score: float
    count: int
    probability: float


class LanguageTracker:
    """Avoids flickering language labels on short Whisper chunks.

    Manual selection always wins.  In auto mode, two agreeing final chunks
    (or about three seconds of agreeing speech) lock the language.  The lock
    can be reset when a new session starts.
    """

    def __init__(self, manual: str = "auto", *, lock_after: int = 2) -> None:
        self.manual = manual if manual and manual != "auto" else ""
        self.lock_after = max(1, lock_after)
        self._votes: dict[str, _Vote] = {}
        self._locked: str = self.manual
        self._lock = threading.Lock()

    @property
    def locked(self) -> str:
        with self._lock:
            return self._locked

    @property
    def manual_mode(self) -> bool:
        return bool(self.manual)

    def reset(self) -> None:
        with self._lock:
            self._votes.clear()
            self._locked = self.manual

    def observe(
        self, code: str | None, probability: float = 0.0, duration: float = 0.0, *, final: bool = False
    ) -> str:
        with self._lock:
            if self._locked:
                return self._locked
            normalized = normalize_code(code)
            if not normalized:
                return ""
            lang = from_whisper(normalized) or from_whisper(code or "")
            canonical = lang.code if lang else normalized
            vote = self._votes.setdefault(canonical, _Vote(canonical, 0.0, 0, 0.0))
            weight = max(0.15, duration) * (1.0 if final else 0.55)
            vote.score += weight * max(0.2, probability)
            vote.count += 1 if final else 0
            vote.probability = max(vote.probability, probability)
            total_duration = sum(v.score for v in self._votes.values())
            best = max(self._votes.values(), key=lambda v: (v.score, v.count))
            if vote.count >= self.lock_after and best.probability >= 0.55 or total_duration >= 3.0 and best.probability >= 0.55 and best.count >= 1:
                self._locked = best.code
            return self._locked or canonical

    def display(self) -> str:
        return self._locked or "auto"
