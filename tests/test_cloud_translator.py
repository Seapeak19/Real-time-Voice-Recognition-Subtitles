from __future__ import annotations

import json

import httpx
import pytest
import respx

from subloom.config import CloudConfig
from subloom.models import TranslationError
from subloom.translate.cloud import CloudTranslator, _clean_response


def make_config(**kwargs) -> CloudConfig:
    values = dict(
        base_url="https://example.test/v1",
        model="test-model",
        timeout_sec=3,
        max_retries=0,
    )
    values.update(kwargs)
    return CloudConfig(**values)


def test_translation_request_and_response(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    with respx.mock:
        route = respx.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "你好，世界。"}}]},
            )
        )
        client = CloudTranslator(make_config())
        try:
            result = client.translate("Hello, world.", "en", "zh")
        finally:
            client.close()
    assert result == "你好，世界。"
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer sk-test"
    assert b"test-model" in request.content


def test_missing_key_raises():
    client = CloudTranslator(make_config())
    try:
        with pytest.raises(TranslationError):
            client.translate("Hello", "en", "zh")
    finally:
        client.close()


def test_http_error_is_reported(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    with respx.mock:
        respx.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
        )
        client = CloudTranslator(make_config())
        try:
            with pytest.raises(TranslationError) as info:
                client.translate("Hello", "en", "zh")
        finally:
            client.close()
    assert "401" in str(info.value)


def test_retry_then_success(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    monkeypatch.setattr("subloom.translate.cloud.time.sleep", lambda _: None)
    with respx.mock:
        route = respx.post("https://example.test/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(500, text="server error"),
                httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
            ]
        )
        client = CloudTranslator(make_config(max_retries=1))
        try:
            assert client.translate("Hello", "en", "zh") == "ok"
        finally:
            client.close()
    assert route.call_count == 2


def test_partial_does_not_retry(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    with respx.mock:
        route = respx.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="server error")
        )
        client = CloudTranslator(make_config(max_retries=3))
        try:
            with pytest.raises(TranslationError):
                client.translate("Hello", "en", "zh", partial=True)
        finally:
            client.close()
    assert route.call_count == 1


def test_partial_omits_context(monkeypatch):
    monkeypatch.setenv("SUBLOOM_API_KEY", "sk-test")
    with respx.mock:
        route = respx.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "你好"}}]},
            )
        )
        client = CloudTranslator(make_config())
        try:
            client.translate(
                "Hello",
                "en",
                "zh",
                context=(("Previous line", "上一句"),),
                partial=True,
            )
        finally:
            client.close()
    payload = json.loads(route.calls[0].request.content)
    user_text = payload["messages"][1]["content"]
    assert "Recent context" not in user_text
    assert "Previous line" not in user_text


def test_clean_response_strips_labels_and_quotes():
    assert _clean_response('"你好"') == "你好"
    assert _clean_response("Translation: hello") == "hello"
    assert _clean_response("```text\nhi\n```") == "hi"
