from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_app_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUBLOOM_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SUBLOOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SUBLOOM_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.delenv("SUBLOOM_API_KEY", raising=False)
    yield
