"""Filesystem locations used by SubLoom.

Everything writable lives outside the repository.  Model weights are never
bundled; they are downloaded into the per-user data directory on demand.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

from . import APP_NAME

_ENV_CONFIG = "SUBLOOM_CONFIG_DIR"
_ENV_DATA = "SUBLOOM_DATA_DIR"
_ENV_MODELS = "SUBLOOM_MODEL_DIR"


def config_dir() -> Path:
    override = os.environ.get(_ENV_CONFIG)
    return Path(override).expanduser() if override else Path(user_config_dir(APP_NAME, appauthor=False))


def data_dir() -> Path:
    override = os.environ.get(_ENV_DATA)
    return Path(override).expanduser() if override else Path(user_data_dir(APP_NAME, appauthor=False))


def cache_dir() -> Path:
    override = os.environ.get(_ENV_DATA)
    if override:
        return Path(override).expanduser() / "cache"
    return Path(user_cache_dir(APP_NAME, appauthor=False))


def models_dir() -> Path:
    override = os.environ.get(_ENV_MODELS)
    if override:
        return Path(override).expanduser()
    return data_dir() / "models"


def logs_dir() -> Path:
    return data_dir() / "logs"


def config_path() -> Path:
    return config_dir() / "config.json"


def ensure_dirs() -> None:
    for path in (config_dir(), data_dir(), models_dir(), logs_dir(), cache_dir()):
        path.mkdir(parents=True, exist_ok=True)


def resource_path(*parts: str) -> Path:
    """Return a path to a bundled read-only resource (works in PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "subloom"
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)
