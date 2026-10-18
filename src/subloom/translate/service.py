"""Translation providers and selection/fallback logic."""

from __future__ import annotations

import logging
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
        del partial
        text = (text or "").strip()
        if not text:
            return "", "none", False, ""
        source = normalize_code(source_lang)
        target = normalize_code(target_lang)
        if not source or source == target:
            return text, "none", False, ""
        provider = self.selected_provider()
        if provider == "off":
            return "", "off", False, ""
        if provider == "none":
            raise TranslationError(
                tr("没有可用的翻译服务。\n请配置云端 API Key，或在设置中下载本地翻译模型。")
            )
        if provider == "cloud":
            try:
                translated = self.cloud.translate(text, source, target, context)
                return translated, "cloud", False, ""
            except TranslationError as exc:
                if not local_model_available(self.config.local):
                    raise
                log.warning("Cloud translation failed, falling back to local: %s", exc)
                translated = self.local.translate(text, source, target, context)
                return translated, "local", True, tr(
                    "云端失败，已切换本地翻译：{error}", error=exc
                )
        translated = self.local.translate(text, source, target, context)
        return translated, "local", False, ""

    def provider_label(self, provider: str) -> str:
        labels = {
            "cloud": tr("云端翻译"),
            "local": tr("本地翻译"),
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
        if self._cloud is not None:
            self._cloud.close()
        if self._local is not None:
            self._local.close()
