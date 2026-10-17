from __future__ import annotations

from PySide6.QtWidgets import QTabWidget

from subloom.config import AppConfig
from subloom.languages import TARGET_LANGUAGES
from subloom.models import CaptionSegment
from subloom.ui.main_window import MainWindow
from subloom.ui.overlay import SubtitleOverlay
from subloom.ui.settings_dialog import SettingsDialog


def make_config() -> AppConfig:
    config = AppConfig()
    config.translation.provider = "off"
    config.overlay.enabled = False
    config.first_run = False
    return config


def test_main_window_builds(qtbot):
    window = MainWindow(make_config())
    qtbot.addWidget(window)
    assert window._target_combo.count() == len(TARGET_LANGUAGES)
    assert window._source_stack.count() == 3
    assert window._provider_combo.count() == 4
    assert not window._export_btn.isEnabled()


def test_main_window_renders_segment(qtbot):
    window = MainWindow(make_config())
    qtbot.addWidget(window)
    segment = CaptionSegment(
        id="x1",
        source_text="Hello world",
        translated_text="你好，世界",
        source_lang="en",
        target_lang="zh",
        start=0,
        end=1.2,
        is_final=True,
        revision=2,
    )
    window._on_segment(segment)
    assert "x1" in window._cards
    assert window._cards["x1"]._translation.text() == "你好，世界"
    assert window._export_btn.isEnabled()
    assert window._detected_label.text() == "英语"


def test_main_window_language_and_provider_switch(qtbot):
    window = MainWindow(make_config())
    qtbot.addWidget(window)
    window._target_combo.setCurrentIndex(window._target_combo.findData("ja"))
    assert window.config.translation.target_lang == "ja"
    window._provider_combo.setCurrentIndex(window._provider_combo.findData("local"))
    assert window.config.translation.provider == "local"
    assert "本地" in window._engine_hint.text() or "未下载" in window._engine_hint.text()


def test_settings_dialog_has_tabs(qtbot):
    dialog = SettingsDialog(make_config())
    qtbot.addWidget(dialog)
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 4


def test_overlay_updates(qtbot):
    config = make_config()
    config.overlay.width = 600
    config.overlay.font_size = 24
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    overlay.show()
    qtbot.wait(50)
    segment = CaptionSegment(
        id="x2",
        source_text="Hello",
        translated_text="你好",
        source_lang="en",
        target_lang="zh",
        start=0,
        end=1,
        is_final=False,
        revision=1,
    )
    overlay.set_segment(segment)
    qtbot.wait(50)
    assert overlay._translation.text() == "你好"
    assert overlay._source.text() == "Hello"
    assert "英语" in overlay._lang.text()
    overlay.close()
