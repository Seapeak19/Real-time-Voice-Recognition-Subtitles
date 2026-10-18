from __future__ import annotations

import pytest

from subloom.config import TranslationConfig
from subloom.models import TranslationError
from subloom.translate import service as service_module
from subloom.translate.service import TranslationService


def make_service(**kwargs) -> TranslationService:
    config = TranslationConfig(**kwargs)
    return TranslationService(config)


def test_readiness_cloud_requires_key(monkeypatch):
    monkeypatch.delenv("SUBLOOM_API_KEY", raising=False)
    service = make_service(provider="cloud")
    try:
        readiness = service.readiness()
        assert not readiness.ready
        assert "Key" in readiness.message
    finally:
        service.close()


def test_auto_uses_cloud_when_key_present(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    monkeypatch.setattr(service_module, "local_model_available", lambda cfg: True)
    service = make_service(provider="auto")
    try:
        assert service.selected_provider() == "cloud"
        assert service.readiness().ready
    finally:
        service.close()


def test_auto_uses_local_without_key(monkeypatch):
    monkeypatch.delenv("SUBLOOM_API_KEY", raising=False)
    monkeypatch.setattr(service_module, "local_model_available", lambda cfg: True)
    service = make_service(provider="auto")
    try:
        assert service.selected_provider() == "local"
        assert service.readiness().ready
    finally:
        service.close()


def test_cloud_failure_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    monkeypatch.setattr(service_module, "local_model_available", lambda cfg: True)
    service = make_service(provider="auto")
    monkeypatch.setattr(
        service.cloud,
        "translate",
        lambda *args, **kwargs: (_ for _ in ()).throw(TranslationError("network down")),
    )
    monkeypatch.setattr(service.local, "translate", lambda *args, **kwargs: "本地译文")
    try:
        text, provider, fallback, warning = service.translate("hello", "en", "zh")
    finally:
        service.close()
    assert text == "本地译文"
    assert provider == "local"
    assert fallback
    assert "network down" in warning


def test_same_language_is_not_translated(monkeypatch):
    service = make_service(provider="off")
    try:
        assert service.translate("hello", "en", "en")[0] == "hello"
        assert service.translate("hello", "en", "zh")[0] == ""
    finally:
        service.close()


def test_off_provider_readiness():
    service = make_service(provider="off")
    try:
        readiness = service.readiness()
        assert readiness.provider == "off"
        assert readiness.ready
    finally:
        service.close()


def test_cache_reuses_normalized_partial_text(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    service = make_service(provider="cloud")
    calls: list[str] = []

    def fake_translate(text, *args, **kwargs):
        calls.append(text)
        return "你好"

    monkeypatch.setattr(service.cloud, "translate", fake_translate)
    try:
        assert service.translate("Hello, world.", "en", "zh", partial=True)[0] == "你好"
        assert service.translate("hello, world", "en", "zh", partial=True)[0] == "你好"
        assert service.translate("Hello, world!", "en", "zh", partial=True)[0] == "你好"
        assert len(calls) == 1
        assert service.cache_hits == 2
    finally:
        service.close()


def test_final_still_refines_cached_partial(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    service = make_service(provider="cloud")
    calls: list[bool] = []

    def fake_translate(text, source, target, context, *, partial=False, glossary=()):
        calls.append(partial)
        return "局部预览" if partial else "上下文定稿"

    monkeypatch.setattr(service.cloud, "translate", fake_translate)
    try:
        assert service.translate("Hello", "en", "zh", partial=True)[0] == "局部预览"
        assert service.cached_translation("Hello", "en", "zh") == ("局部预览", "cloud")
        result = service.translate("Hello", "en", "zh", partial=False)
    finally:
        service.close()
    assert result[0] == "上下文定稿"
    assert calls == [True, False]


def test_partial_flag_is_forwarded(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    service = make_service(provider="cloud")
    seen: dict[str, bool] = {}

    def fake_translate(text, source, target, context, *, partial=False, glossary=()):
        seen["partial"] = partial
        return "你好"

    monkeypatch.setattr(service.cloud, "translate", fake_translate)
    try:
        service.translate("Hello", "en", "zh", partial=True)
    finally:
        service.close()
    assert seen["partial"] is True


def test_partial_failure_skips_local_fallback(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    monkeypatch.setattr(service_module, "local_model_available", lambda cfg: True)
    service = make_service(provider="auto")
    local_calls: list[str] = []
    monkeypatch.setattr(
        service.cloud,
        "translate",
        lambda *args, **kwargs: (_ for _ in ()).throw(TranslationError("timeout")),
    )
    monkeypatch.setattr(
        service.local,
        "translate",
        lambda text, *args, **kwargs: local_calls.append(text) or "本地译文",
    )
    try:
        with pytest.raises(TranslationError):
            service.translate("Hello", "en", "zh", partial=True)
    finally:
        service.close()
    assert local_calls == []


def test_custom_sentence_translation_bypasses_provider():
    service = make_service(
        provider="off",
        glossary={"Hello, world.": "你好，世界。"},
    )
    try:
        translated, provider, fallback, warning = service.translate(
            "Hello, world", "en", "zh"
        )
    finally:
        service.close()
    assert translated == "你好，世界。"
    assert provider == "custom"
    assert fallback is False
    assert warning == ""


def test_glossary_terms_are_forwarded_and_applied(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    service = make_service(provider="cloud", glossary={"API": "接口"})
    seen: dict[str, tuple[tuple[str, str], ...]] = {}

    def fake_translate(text, source, target, context, *, partial=False, glossary=()):
        seen["glossary"] = tuple(glossary)
        return "使用 API 完成。"

    monkeypatch.setattr(service.cloud, "translate", fake_translate)
    try:
        translated, provider, _, _ = service.translate("Use the API.", "en", "zh")
    finally:
        service.close()
    assert seen["glossary"] == (("API", "接口"),)
    assert translated == "使用 接口 完成。"
    assert provider == "cloud"
