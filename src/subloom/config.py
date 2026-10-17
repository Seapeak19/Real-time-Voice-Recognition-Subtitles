"""Persistent, forward-compatible application configuration."""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_type_hints

from . import paths
from .languages import BY_CODE, DEFAULT_TARGET

log = logging.getLogger(__name__)

CONFIG_VERSION = 1


@dataclass
class AudioConfig:
    source: str = "system"  # system | microphone | file
    system_device: str = ""  # device name, empty = default speaker loopback
    microphone_device: str = ""  # sounddevice index (as string)
    input_gain_db: float = 0.0
    vad_aggressiveness: int = 2
    file_realtime: bool = True


@dataclass
class ASRConfig:
    model: str = "auto"  # auto | tiny | base | small | medium | large-v3 | large-v3-turbo
    device: str = "auto"  # auto | cuda | cpu
    compute_type: str = "auto"
    language: str = "auto"  # auto or a code from languages.py
    model_dir: str = ""
    beam_size: int = 3
    partial_beam_size: int = 1
    max_segment_sec: float = 9.0
    silence_ms: int = 450
    min_speech_ms: int = 350
    partial_interval_ms: int = 650
    use_context_prompt: bool = True

    @property
    def language_mode(self) -> str:
        return "auto" if self.language in ("", "auto") else self.language


@dataclass
class CloudConfig:
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout_sec: float = 10.0
    max_retries: int = 1


@dataclass
class LocalTranslationConfig:
    model: str = "nllb-200-distilled-600M-ct2-int8"
    model_dir: str = ""
    compute_type: str = "auto"
    beam_size: int = 2
    max_input_tokens: int = 320


@dataclass
class TranslationConfig:
    provider: str = "auto"  # auto | cloud | local | off
    target_lang: str = DEFAULT_TARGET
    translate_partials: bool = True
    cloud: CloudConfig = field(default_factory=CloudConfig)
    local: LocalTranslationConfig = field(default_factory=LocalTranslationConfig)


@dataclass
class OverlayConfig:
    enabled: bool = True
    show_source: bool = False
    font_size: int = 26
    opacity: float = 0.84
    click_through: bool = False
    width: int = 1000
    x: int | None = None
    y: int | None = None


@dataclass
class UIConfig:
    show_source_in_main: bool = True
    compact_mode: bool = False


@dataclass
class AppConfig:
    version: int = CONFIG_VERSION
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    first_run: bool = True

    def validate(self) -> None:
        if self.audio.source not in {"system", "microphone", "file"}:
            self.audio.source = "system"
        if self.translation.provider not in {"auto", "cloud", "local", "off"}:
            self.translation.provider = "auto"
        if self.translation.target_lang not in BY_CODE:
            self.translation.target_lang = DEFAULT_TARGET
        if self.asr.device not in {"auto", "cuda", "cpu"}:
            self.asr.device = "auto"
        if self.asr.language_mode != "auto" and self.asr.language not in BY_CODE:
            self.asr.language = "auto"
        self.asr.silence_ms = min(2000, max(200, int(self.asr.silence_ms)))
        self.asr.min_speech_ms = min(2000, max(150, int(self.asr.min_speech_ms)))
        self.asr.max_segment_sec = min(30.0, max(3.0, float(self.asr.max_segment_sec)))
        self.asr.partial_interval_ms = min(2000, max(300, int(self.asr.partial_interval_ms)))
        self.asr.beam_size = min(10, max(1, int(self.asr.beam_size)))
        self.asr.partial_beam_size = min(5, max(1, int(self.asr.partial_beam_size)))
        self.audio.vad_aggressiveness = min(3, max(0, int(self.audio.vad_aggressiveness)))
        self.audio.input_gain_db = min(24.0, max(-24.0, float(self.audio.input_gain_db)))
        self.translation.translate_partials = bool(self.translation.translate_partials)
        self.translation.cloud.timeout_sec = min(60.0, max(2.0, float(self.translation.cloud.timeout_sec)))
        self.translation.cloud.max_retries = min(3, max(0, int(self.translation.cloud.max_retries)))
        self.translation.local.beam_size = min(8, max(1, int(self.translation.local.beam_size)))
        self.overlay.font_size = min(64, max(12, int(self.overlay.font_size)))
        self.overlay.opacity = min(1.0, max(0.2, float(self.overlay.opacity)))
        self.overlay.width = min(2400, max(420, int(self.overlay.width)))
        if self.overlay.x is not None:
            self.overlay.x = int(self.overlay.x)
        if self.overlay.y is not None:
            self.overlay.y = int(self.overlay.y)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _merge_dataclass(cls: type, raw: dict[str, Any]) -> Any:
    if not isinstance(raw, dict):
        raw = {}
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for item in fields(cls):
        if item.name not in raw:
            continue
        value = raw[item.name]
        hint = hints.get(item.name, item.type)
        if is_dataclass(hint):
            value = _merge_dataclass(hint, value)
        kwargs[item.name] = value
    return cls(**kwargs)


def _load_raw(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read config %s: %s", path, exc)
        try:
            shutil.copy2(path, path.with_suffix(".broken.json"))
        except OSError:
            pass
        return {}


def load_config(path: Path | None = None) -> AppConfig:
    config_file = path or paths.config_path()
    raw = _load_raw(config_file)
    cfg = AppConfig()
    try:
        if "audio" in raw and isinstance(raw["audio"], dict):
            cfg.audio = _merge_dataclass(AudioConfig, raw["audio"])
        if "asr" in raw and isinstance(raw["asr"], dict):
            cfg.asr = _merge_dataclass(ASRConfig, raw["asr"])
        if "translation" in raw and isinstance(raw["translation"], dict):
            cfg.translation = _merge_dataclass(TranslationConfig, raw["translation"])
        if "overlay" in raw and isinstance(raw["overlay"], dict):
            cfg.overlay = _merge_dataclass(OverlayConfig, raw["overlay"])
        if "ui" in raw and isinstance(raw["ui"], dict):
            cfg.ui = _merge_dataclass(UIConfig, raw["ui"])
        if isinstance(raw.get("first_run"), bool):
            cfg.first_run = raw["first_run"]
        if isinstance(raw.get("version"), int):
            cfg.version = raw["version"]
    except (TypeError, ValueError) as exc:
        log.warning("Invalid values in config, falling back to defaults: %s", exc)
        cfg = AppConfig()
    cfg.validate()
    return cfg


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config.validate()
    target = path or paths.config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    data = config.to_dict()
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def reset_config(path: Path | None = None) -> AppConfig:
    cfg = AppConfig()
    save_config(cfg, path)
    return cfg
