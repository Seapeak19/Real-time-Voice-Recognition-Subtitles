"""Translation backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class Translator(ABC):
    name = "base"

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Sequence[tuple[str, str]] = (),
    ) -> str:
        """Translate one subtitle line.  Implementations may raise TranslationError."""

    def close(self) -> None:
        """Release model/network resources."""
