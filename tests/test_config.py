from __future__ import annotations

from pathlib import Path

from subloom.config import AppConfig, load_config, save_config


def test_defaults_roundtrip(tmp_path: Path):
    target = tmp_path / "config.json"
    config = AppConfig()
    config.translation.target_lang = "ja"
    config.translation.cloud.model = "test-model"
    config.overlay.font_size = 31
    save_config(config, target)
    loaded = load_config(target)
    assert loaded.translation.target_lang == "ja"
    assert loaded.translation.cloud.model == "test-model"
    assert loaded.overlay.font_size == 31


def test_nested_cloud_values_survive(tmp_path: Path):
    target = tmp_path / "config.json"
    target.write_text(
        '{"translation": {"provider": "cloud", "cloud": {"base_url": "http://x/v1",'
        ' "model": "m", "timeout_sec": 4.5}, "local": {"beam_size": 4}}}',
        encoding="utf-8",
    )
    config = load_config(target)
    assert config.translation.provider == "cloud"
    assert config.translation.cloud.base_url == "http://x/v1"
    assert config.translation.cloud.timeout_sec == 4.5
    assert config.translation.local.beam_size == 4


def test_invalid_values_are_clamped(tmp_path: Path):
    target = tmp_path / "config.json"
    target.write_text(
        '{"translation": {"target_lang": "xx", "provider": "bogus"},'
        ' "overlay": {"font_size": 999, "opacity": 4},'
        ' "asr": {"silence_ms": 10}}',
        encoding="utf-8",
    )
    config = load_config(target)
    assert config.translation.target_lang == "zh"
    assert config.translation.provider == "auto"
    assert config.overlay.font_size == 64
    assert config.overlay.opacity == 1.0
    assert config.asr.silence_ms == 200


def test_corrupt_config_falls_back(tmp_path: Path):
    target = tmp_path / "config.json"
    target.write_text("{not json", encoding="utf-8")
    config = load_config(target)
    assert config.translation.target_lang == "zh"
    assert (tmp_path / "config.broken.json").exists()
