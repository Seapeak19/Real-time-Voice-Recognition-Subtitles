"""Small value objects shared across the application."""

from __future__ import annotations

from dataclasses import dataclass, field


class SubLoomError(Exception):
    """Base class for all user-facing SubLoom errors."""


class AudioError(SubLoomError):
    """Audio device or decoding failure."""


class ModelNotReadyError(SubLoomError):
    """A required local model is not available yet."""


class UnknownLanguageError(SubLoomError):
    """A language code is not supported."""


class TranslationError(SubLoomError):
    """A translation provider failed."""


@dataclass(slots=True)
class AudioDevice:
    id: str
    name: str
    kind: str  # "microphone" | "system"
    is_default: bool = False


@dataclass(slots=True)
class ASRResult:
    text: str
    language: str
    language_probability: float = 0.0
    duration: float = 0.0
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass(slots=True)
class TranslationResult:
    text: str
    provider: str
    source_lang: str
    target_lang: str
    fallback_used: bool = False
    warning: str = ""


@dataclass(slots=True)
class CaptionSegment:
    id: str
    source_text: str
    translated_text: str = ""
    source_lang: str = ""
    target_lang: str = ""
    start: float = 0.0
    end: float = 0.0
    is_final: bool = False
    revision: int = 0
    provider: str = ""
    warning: str = ""
    translation_pending: bool = False
    # True when this segment is expected to be translated but no translation
    # has arrived yet.  The overlay uses this to avoid showing source text as
    # if it were the translated subtitle.
    translation_expected: bool = False

    @property
    def text_for_display(self) -> str:
        return self.translated_text or self.source_text


@dataclass(slots=True)
class ModelStatus:
    name: str
    available: bool
    detail: str = ""
    size_hint: str = ""


@dataclass(slots=True)
class SessionStats:
    started_at: float | None = None
    segments: int = 0
    characters: int = 0
    dropped_audio_seconds: float = 0.0
    asr_seconds: float = 0.0
    translation_seconds: float = 0.0
    extra: dict[str, float] = field(default_factory=dict)
