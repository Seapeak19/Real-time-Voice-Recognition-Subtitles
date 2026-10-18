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
    assert tabs.count() == 5


def test_english_interface(qtbot):
    from subloom import i18n

    i18n.set_language("en")
    config = make_config()
    config.ui.language = "en"
    window = MainWindow(config)
    qtbot.addWidget(window)
    assert window._settings_btn.text() == "Settings"
    assert window._source_segment._buttons["system"].text() == "System audio"
    assert window._start_btn.text() == "Start subtitles"
    assert window._stats_label.text() == "0 lines"

    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.tabText(3) == "Interface"
    assert tabs.tabText(4) == "About"


def test_interface_language_can_be_saved(qtbot):
    config = make_config()
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)
    dialog._ui_language_combo.setCurrentIndex(
        dialog._ui_language_combo.findData("en")
    )
    dialog._apply()
    assert dialog.config.ui.language == "en"


def test_numeric_setting_inputs_sync_with_sliders(qtbot):
    config = make_config()
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)
    dialog._hold_input.setValue(2400)
    assert dialog._hold_slider.value() == 2400
    dialog._hold_slider.setValue(2000)
    assert dialog._hold_input.value() == 2000
    dialog._apply()
    assert dialog.config.overlay.hold_ms == 2000

    for slider_name, input_name in (
        ("_silence_slider", "_silence_input"),
        ("_max_segment_slider", "_max_segment_input"),
        ("_partial_slider", "_partial_input"),
        ("_font_slider", "_font_input"),
        ("_opacity_slider", "_opacity_input"),
        ("_width_slider", "_width_input"),
        ("_hold_slider", "_hold_input"),
    ):
        slider = getattr(dialog, slider_name)
        numeric_input = getattr(dialog, input_name)
        assert numeric_input.isEnabled()
        assert not numeric_input.lineEdit().isReadOnly()
        assert numeric_input.minimum() == slider.minimum()
        assert numeric_input.maximum() == slider.maximum()


def test_overlay_updates(qtbot):
    config = make_config()
    config.overlay.width = 600
    config.overlay.font_size = 24
    config.overlay.show_source = True
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


def test_overlay_does_not_show_source_while_translation_is_pending(qtbot):
    config = make_config()
    config.overlay.width = 600
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    segment = CaptionSegment(
        id="pending-1",
        source_text="This is English source text",
        source_lang="en",
        target_lang="zh",
        start=0,
        end=2,
        is_final=False,
        revision=1,
        translation_pending=True,
        translation_expected=True,
    )
    overlay.set_segment(segment)
    assert overlay._translation.text() == "正在翻译…"
    assert overlay._source.text() == ""
    assert not overlay._source.isVisible()


def test_overlay_keeps_previous_translation_while_next_one_is_pending(qtbot):
    config = make_config()
    config.overlay.width = 600
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    overlay.set_segment(
        CaptionSegment(
            id="old",
            source_text="First sentence",
            translated_text="第一句",
            source_lang="en",
            target_lang="zh",
            start=0,
            end=1,
            is_final=True,
            revision=2,
        )
    )
    overlay.set_segment(
        CaptionSegment(
            id="new",
            source_text="Second sentence",
            source_lang="en",
            target_lang="zh",
            start=1,
            end=2,
            is_final=False,
            revision=1,
            translation_pending=True,
            translation_expected=True,
        )
    )
    assert overlay._translation.text() == "第一句"
    assert overlay._hint.text() == ""
    assert overlay._source.text() == ""


def test_overlay_holds_final_before_showing_next(qtbot):
    config = make_config()
    config.overlay.hold_ms = 800
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    first = CaptionSegment(
        id="hold-1",
        source_text="First sentence",
        translated_text="第一句",
        source_lang="en",
        target_lang="zh",
        start=0,
        end=1,
        is_final=True,
        revision=1,
    )
    second = CaptionSegment(
        id="hold-2",
        source_text="Second sentence",
        translated_text="第二句",
        source_lang="en",
        target_lang="zh",
        start=1,
        end=2,
        is_final=True,
        revision=1,
    )
    overlay.set_segment(first)
    overlay.set_segment(second)
    assert overlay._translation.text() == "第一句"
    qtbot.wait(1000)
    assert overlay._translation.text() == "第二句"


def test_overlay_ignores_partial_updates_while_final_is_visible(qtbot):
    config = make_config()
    config.overlay.hold_ms = 800
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    overlay.set_segment(
        CaptionSegment(
            id="stable-1",
            source_text="First sentence",
            translated_text="第一句完整译文",
            source_lang="en",
            target_lang="zh",
            start=0,
            end=1,
            is_final=True,
            revision=1,
        )
    )
    overlay.set_segment(
        CaptionSegment(
            id="partial-2",
            source_text="Second partial",
            translated_text="第二句局部",
            source_lang="en",
            target_lang="zh",
            start=1,
            end=2,
            is_final=False,
            revision=1,
        )
    )
    assert overlay._translation.text() == "第一句完整译文"


def test_overlay_ignores_late_refinement_of_replaced_line(qtbot):
    config = make_config()
    config.overlay.hold_ms = 800
    overlay = SubtitleOverlay(config.overlay)
    qtbot.addWidget(overlay)
    first = CaptionSegment(
        id="late-refine",
        source_text="First sentence",
        translated_text="第一句",
        source_lang="en",
        target_lang="zh",
        start=0,
        end=1,
        is_final=True,
        revision=1,
    )
    second = CaptionSegment(
        id="late-refine-2",
        source_text="Second sentence",
        translated_text="第二句",
        source_lang="en",
        target_lang="zh",
        start=1,
        end=2,
        is_final=True,
        revision=1,
    )
    overlay.set_segment(first)
    qtbot.wait(900)
    overlay.set_segment(second)
    overlay.set_segment(
        CaptionSegment(
            id="late-refine",
            source_text="First sentence",
            translated_text="第一句精修后",
            source_lang="en",
            target_lang="zh",
            start=0,
            end=1,
            is_final=True,
            revision=2,
        )
    )
    assert overlay._translation.text() == "第二句"


def test_caption_card_pending_does_not_render_source_as_translation(qtbot):
    from subloom.ui.widgets import CaptionCard

    card = CaptionCard(
        CaptionSegment(
            id="pending-card",
            source_text="English words",
            source_lang="en",
            target_lang="zh",
            start=0,
            end=1,
            is_final=False,
            revision=1,
            translation_pending=True,
            translation_expected=True,
        )
    )
    qtbot.addWidget(card)
    assert card._translation.text() == "正在翻译…"
    assert not card._source.isVisible()
