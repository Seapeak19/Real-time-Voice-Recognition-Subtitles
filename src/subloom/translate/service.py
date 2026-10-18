"""Translation providers and selection/fallback logic."""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass

from ..config import TranslationConfig
from ..i18n import display_language, tr
from ..languages import normalize_code
from ..models import TranslationError
from ..secrets import get_api_key
from .cloud import CloudTranslator
from .nllb import (
    NLLB_LICENSE,
    NLLB_SIZE_HINT,
    NLLBTranslator,
    download_local_model,
    local_model_available,
)

log = logging.getLogger(__name__)

_CACHE_LIMIT = 256
_TRAILING_PUNCTUATION = re.compile(r"[\s.,!?;:，。！？；：、]+$")


def _normalize_phrase(text: str) -> str:
    normalized = " ".join((text or "").split())
    return _TRAILING_PUNCTUATION.sub("", normalized).casefold()


def _cache_key(text: str, source: str, target: str) -> tuple[str, str, str]:
    """Normalize harmless differences so final text can reuse a partial result."""
    return _normalize_phrase(text), source, target


@dataclass(slots=True)
class Readiness:
    provider: str
    ready: bool
    message: str


class TranslationService:
    def __init__(self, config: TranslationConfig):
        self.config = config
        self._cloud: CloudTranslator | None = None
        self._local: NLLBTranslator | None = None
        self._closed = False
        self._cache: OrderedDict[tuple[str, str, str], tuple[str, str]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_hits = 0
        self._glossary = tuple(
            (str(source).strip(), str(target).strip())
            for source, target in (self.config.glossary or {}).items()
            if str(source).strip() and str(target).strip()
        )
        self._custom = {
            _normalize_phrase(source): target for source, target in self._glossary
        }

    def _custom_translation(self, text: str) -> str | None:
        key = _normalize_phrase(text)
        return self._custom.get(key) if key else None

    def _apply_glossary(self, translated: str) -> str:
        for source, target in self._glossary:
            if source and source in translated:
                translated = translated.replace(source, target)
        return translated

    @property
    def cache_hits(self) -> int:
        with self._cache_lock:
            return self._cache_hits

    def _cache_get(self, key: tuple[str, str, str]) -> tuple[str, str] | None:
        with self._cache_lock:
            try:
                value = self._cache.pop(key)
            except KeyError:
                return None
            self._cache[key] = value
            self._cache_hits += 1
            return value

    def _cache_put(self, key: tuple[str, str, str], value: tuple[str, str]) -> None:
        with self._cache_lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > _CACHE_LIMIT:
                self._cache.popitem(last=False)

    def cached_translation(
        self, text: str, source_lang: str, target_lang: str
    ) -> tuple[str, str] | None:
        """Return a cached line for immediate display, without a network call."""
        text = (text or "").strip()
        if not text:
            return None
        source = normalize_code(source_lang)
        target = normalize_code(target_lang)
        if not source or not target or source == target:
            return None
        return self._cache_get(_cache_key(text, source, target))

    def _cloud_configured(self) -> bool:
        return bool(
            self.config.cloud.base_url.strip()
            and self.config.cloud.model.strip()
            and get_api_key()
        )

    def selected_provider(self) -> str:
        provider = self.config.provider
        if provider == "off":
            return "off"
        if provider == "cloud":
            return "cloud"
        if provider == "local":
            return "local"
        if self._cloud_configured():
            return "cloud"
        if local_model_available(self.config.local):
            return "local"
        return "none"

    def readiness(self) -> Readiness:
        provider = self.selected_provider()
        if provider == "off":
            return Readiness("off", True, tr("仅显示原文，不翻译"))
        if provider == "cloud":
            if not self.config.cloud.base_url.strip() or not self.config.cloud.model.strip():
                return Readiness("cloud", False, tr("云端 API 地址或模型未填写"))
            if not get_api_key():
                return Readiness("cloud", False, tr("未配置云端 API Key"))
            return Readiness(
                "cloud",
                True,
                tr("云端翻译 · {model}", model=self.config.cloud.model),
            )
        if provider == "local":
            if not local_model_available(self.config.local):
                return Readiness(
                    "local",
                    False,
                    tr(
                        "本地翻译模型未下载（{size}，{license}）",
                        size=tr(NLLB_SIZE_HINT),
                        license=tr(NLLB_LICENSE),
                    ),
                )
            return Readiness("local", True, tr("本地翻译 · NLLB-200 600M"))
        return Readiness(
            "none",
            False,
            tr("未配置翻译：请填写云端 API Key，或下载本地模型"),
        )

    @property
    def cloud(self) -> CloudTranslator:
        if self._cloud is None:
            self._cloud = CloudTranslator(self.config.cloud)
        return self._cloud

    @property
    def local(self) -> NLLBTranslator:
        if self._local is None:
            self._local = NLLBTranslator(self.config.local)
        return self._local

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        context: Sequence[tuple[str, str]] = (),
        partial: bool = False,
    ) -> tuple[str, str, bool, str]:
        """Return ``(translation, provider, fallback_used, warning)``."""
        text = (text or "").strip()
        if not text:
            return "", "none", False, ""
        source = normalize_code(source_lang)
        target = normalize_code(target_lang)
        if not source or source == target:
            return text, "none", False, ""
        custom = self._custom_translation(text)
        if custom is not None:
            return custom, "custom", False, ""
        provider = self.selected_provider()
        if provider == "off":
            return "", "off", False, ""
        if provider == "none":
            raise TranslationError(
                tr("没有可用的翻译服务。\n请配置云端 API Key，或在设置中下载本地翻译模型。")
            )

        key = _cache_key(text, source, target)
        # Partials are disposable and can safely reuse each other. Finals keep
        # their context-aware request; the pipeline may still show a cached
        # partial immediately while the refined final translation is generated.
        if partial:
            cached = self._cache_get(key)
            if cached is not None:
                translated, cached_provider = cached
                log.debug("Translation cache hit (%s -> %s, %s)", source, target, cached_provider)
                return translated, cached_provider, False, ""

        if provider == "cloud":
            try:
                translated = self.cloud.translate(
                    text,
                    source,
                    target,
                    context,
                    partial=partial,
                    glossary=self._glossary,
                )
                translated = self._apply_glossary(translated)
                self._cache_put(key, (translated, "cloud"))
                return translated, "cloud", False, ""
            except TranslationError as exc:
                # A partial request is disposable; do not spend seconds loading
                # or running the local model just to rescue it. The final line
                # will still use the normal fallback path.
                if partial or not local_model_available(self.config.local):
                    raise
                log.warning("Cloud translation failed, falling back to local: %s", exc)
                translated = self._apply_glossary(
                    self.local.translate(text, source, target, context)
                )
                self._cache_put(key, (translated, "local"))
                return translated, "local", True, tr(
                    "云端失败，已切换本地翻译：{error}", error=exc
                )
        translated = self._apply_glossary(
            self.local.translate(text, source, target, context)
        )
        self._cache_put(key, (translated, "local"))
        return translated, "local", False, ""

    def provider_label(self, provider: str) -> str:
        labels = {
            "cloud": tr("云端翻译"),
            "local": tr("本地翻译"),
            "custom": tr("自定义字幕"),
            "off": tr("仅原文"),
            "none": tr("未配置"),
        }
        return labels.get(provider, provider)

    def target_label(self) -> str:
        return display_language(self.config.target_lang)

    def warm_local(self, progress=None) -> None:
        self.local.load(progress)

    def download_local(self, progress=None) -> None:
        download_local_model(progress, self.config.local)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._cache_lock:
            self._cache.clear()
        if self._cloud is not None:
            self._cloud.close()
        if self._local is not None:
            self._local.close()
