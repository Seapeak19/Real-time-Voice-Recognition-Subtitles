from __future__ import annotations

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
