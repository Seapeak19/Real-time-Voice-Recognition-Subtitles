"""Main SubLoom window."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QSettings, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, APP_NAME_ZH
from ..asr.cuda_runtime import cuda_device_count, cuda_ready, install_hint
from ..asr.whisper_engine import resolve_device, resolve_model
from ..audio.devices import list_microphones, list_system_devices, system_audio_hint
from ..config import AppConfig, save_config
from ..languages import language_name
from ..models import CaptionSegment
from ..pipeline import CaptionPipeline, PipelineCallbacks
from ..transcript import TranscriptStore
from ..translate import Readiness, TranslationService
from . import theme
from .overlay import SubtitleOverlay
from .settings_dialog import SettingsDialog
from .widgets import (
    CaptionCard,
    EmptyState,
    LevelMeter,
    LogoMark,
    SegmentedControl,
    StatusPill,
    ToggleSwitch,
)

log = logging.getLogger(__name__)


class PipelineBridge(QObject):
    segment = Signal(object)
    status = Signal(str)
    error = Signal(str)
    finished = Signal()
    language = Signal(str, float)
    level = Signal(float)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.transcript = TranscriptStore()
        self._bridge = PipelineBridge(self)
        self._pipeline: CaptionPipeline | None = None
        self._running = False
        self._stopping = False
        self._closing = False
        self._session_started: float | None = None
        self._selected_file: Path | None = None
        self._cards: dict[str, CaptionCard] = {}
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(lambda: self._error_banner.hide())
        self._position_timer = QTimer(self)
        self._position_timer.setSingleShot(True)
        self._position_timer.setInterval(400)
        self._position_timer.timeout.connect(self._save_position)
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000)
        self._session_timer.timeout.connect(self._update_stats)

        self._build_ui()
        self._build_overlay()
        self._connect_bridge()
        self._apply_config_to_ui()
        self._restore_geometry()
        self._refresh_engine_hint()
        self._update_model_badge()
        QTimer.singleShot(350, self._maybe_first_run)

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME}  {APP_NAME_ZH}  —  实时语音翻译字幕")
        self.setMinimumSize(1040, 700)
        screen = self.screen()
        width, height = 1210, 790
        if screen:
            available = screen.availableGeometry()
            width = min(width, max(1040, available.width() - 80))
            height = min(height, max(700, available.height() - 70))
        self.resize(width, height)
        self.setWindowIcon(make_app_icon())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(14)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(16)
        self._side = self._build_side_panel()
        body.addWidget(self._side, 0)
        body.addWidget(self._build_transcript_panel(), 1)
        root.addLayout(body, 1)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(12)
        layout.addWidget(LogoMark(42))
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        zh = QLabel(APP_NAME_ZH)
        zh.setObjectName("AppTitleZh")
        title_row.addWidget(title)
        title_row.addWidget(zh)
        title_row.addStretch(1)
        tagline = QLabel("实时语音 · 自动识别 · 即时翻译")
        tagline.setObjectName("Tagline")
        title_box.addLayout(title_row)
        title_box.addWidget(tagline)
        layout.addLayout(title_box)
        layout.addStretch(1)
        self._status_pill = StatusPill("就绪")
        layout.addWidget(self._status_pill)
        help_btn = QPushButton("快速开始")
        help_btn.setObjectName("GhostButton")
        help_btn.clicked.connect(self._show_help)
        layout.addWidget(help_btn)
        self._settings_btn = QPushButton("设置")
        self._settings_btn.setObjectName("SecondaryButton")
        self._settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self._settings_btn)
        return header

    def _build_side_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SidePanel")
        panel.setFixedWidth(332)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(11)

        layout.addWidget(self._section_label("音频来源"))
        self._source_segment = SegmentedControl(
            (("system", "系统声音"), ("microphone", "麦克风"), ("file", "文件"))
        )
        self._source_segment.changed.connect(self._on_source_changed)
        layout.addWidget(self._source_segment)
        self._source_stack = QStackedWidget()
        self._system_page = self._build_system_page()
        self._mic_page = self._build_mic_page()
        self._file_page = self._build_file_page()
        self._source_stack.addWidget(self._system_page)
        self._source_stack.addWidget(self._mic_page)
        self._source_stack.addWidget(self._file_page)
        self._source_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self._source_stack)
        layout.addSpacing(3)

        layout.addWidget(self._section_label("翻译"))
        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_label = QLabel("目标语言")
        target_label.setObjectName("Hint")
        target_label.setFixedWidth(58)
        self._target_combo = QComboBox()
        self._target_combo.setMaxVisibleItems(14)
        self._populate_targets()
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        target_row.addWidget(target_label)
        target_row.addWidget(self._target_combo, 1)
        layout.addLayout(target_row)

        provider_row = QHBoxLayout()
        provider_label = QLabel("翻译方式")
        provider_label.setObjectName("Hint")
        provider_label.setFixedWidth(58)
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("自动选择", "auto")
        self._provider_combo.addItem("云端 API", "cloud")
        self._provider_combo.addItem("本地模型", "local")
        self._provider_combo.addItem("仅显示原文", "off")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self._provider_combo, 1)
        layout.addLayout(provider_row)
        self._engine_hint = QLabel("")
        self._engine_hint.setObjectName("Hint")
        self._engine_hint.setWordWrap(True)
        layout.addWidget(self._engine_hint)

        layout.addSpacing(4)
        self._start_btn = QPushButton("开始字幕")
        self._start_btn.setObjectName("PrimaryButton")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.clicked.connect(self._toggle_session)
        layout.addWidget(self._start_btn)

        level_row = QHBoxLayout()
        level_label = QLabel("输入电平")
        level_label.setObjectName("Hint")
        level_label.setFixedWidth(58)
        self._level_meter = LevelMeter()
        level_row.addWidget(level_label)
        level_row.addWidget(self._level_meter, 1)
        layout.addLayout(level_row)

        overlay_card = QFrame()
        overlay_card.setObjectName("OverlayToggleCard")
        overlay_layout = QHBoxLayout(overlay_card)
        overlay_layout.setContentsMargins(12, 10, 12, 10)
        overlay_layout.setSpacing(10)
        overlay_text = QVBoxLayout()
        overlay_text.setSpacing(2)
        overlay_title = QLabel("悬浮字幕")
        overlay_title.setStyleSheet(f"color: {theme.TEXT}; font-weight: 600; font-size: 12px;")
        overlay_hint = QLabel("置顶显示，可拖动")
        overlay_hint.setObjectName("Hint")
        overlay_text.addWidget(overlay_title)
        overlay_text.addWidget(overlay_hint)
        overlay_layout.addLayout(overlay_text, 1)
        self._overlay_toggle = ToggleSwitch(self.config.overlay.enabled)
        self._overlay_toggle.toggled.connect(self._toggle_overlay)
        overlay_layout.addWidget(self._overlay_toggle)
        layout.addWidget(overlay_card)
        layout.addStretch(1)

        footer = QLabel(f"本地识别 · {resolve_model(self.config.asr)}")
        footer.setObjectName("Mono")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        self._side_footer = footer
        return panel

    def _build_system_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self._system_combo = QComboBox()
        self._system_combo.currentIndexChanged.connect(self._on_device_changed)
        refresh = QPushButton("刷新")
        refresh.setObjectName("GhostButton")
        refresh.clicked.connect(self._reload_devices)
        row.addWidget(self._system_combo, 1)
        row.addWidget(refresh)
        layout.addLayout(row)
        self._system_hint = QLabel(system_audio_hint())
        self._system_hint.setObjectName("Hint")
        self._system_hint.setWordWrap(True)
        layout.addWidget(self._system_hint)
        return page

    def _build_mic_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self._mic_combo = QComboBox()
        self._mic_combo.currentIndexChanged.connect(self._on_device_changed)
        refresh = QPushButton("刷新")
        refresh.setObjectName("GhostButton")
        refresh.clicked.connect(self._reload_devices)
        row.addWidget(self._mic_combo, 1)
        row.addWidget(refresh)
        layout.addLayout(row)
        hint = QLabel("适合现场讲话、会议发言和课堂。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    def _build_file_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("选择音频或视频文件…")
        self._file_edit.setReadOnly(True)
        browse = QPushButton("浏览")
        browse.setObjectName("SecondaryButton")
        browse.clicked.connect(self._browse_file)
        row.addWidget(self._file_edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        hint = QLabel("按原速播放并生成字幕；支持 WAV / MP3 / M4A / MP4 / MKV 等。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    def _build_transcript_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("TranscriptPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("实时字幕")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 16px; font-weight: 700;")
        top.addWidget(title)
        self._detected_label = QLabel("等待音频")
        self._detected_label.setStyleSheet(
            f"color: {theme.MUTED}; font-size: 10px; background: {theme.BG};"
            " border-radius: 6px; padding: 3px 7px;"
        )
        top.addWidget(self._detected_label)
        self._provider_label = QLabel("")
        self._provider_label.setStyleSheet(f"color: {theme.DIM}; font-size: 10px;")
        top.addWidget(self._provider_label)
        top.addStretch(1)
        self._export_btn = QPushButton("导出")
        self._export_btn.setObjectName("SecondaryButton")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_menu)
        self._clear_btn = QPushButton("清空")
        self._clear_btn.setObjectName("GhostButton")
        self._clear_btn.clicked.connect(self._clear_captions)
        top.addWidget(self._export_btn)
        top.addWidget(self._clear_btn)
        layout.addLayout(top)

        self._error_banner = QFrame()
        self._error_banner.setStyleSheet(
            "QFrame { background: rgba(255, 123, 123, 0.08);"
            " border: 1px solid rgba(255, 123, 123, 0.24); border-radius: 9px; }"
        )
        error_layout = QHBoxLayout(self._error_banner)
        error_layout.setContentsMargins(10, 7, 10, 7)
        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(f"color: {theme.ERROR}; font-size: 11px;")
        error_layout.addWidget(self._error_label, 1)
        close_error = QPushButton("×")
        close_error.setObjectName("GhostButton")
        close_error.setFixedWidth(28)
        close_error.clicked.connect(self._error_banner.hide)
        error_layout.addWidget(close_error)
        self._error_banner.hide()
        layout.addWidget(self._error_banner)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._caption_host = QWidget()
        self._caption_layout = QVBoxLayout(self._caption_host)
        self._caption_layout.setContentsMargins(2, 4, 6, 4)
        self._caption_layout.setSpacing(9)
        self._empty = EmptyState()
        self._caption_layout.addWidget(self._empty)
        self._caption_layout.addStretch(1)
        self._scroll.setWidget(self._caption_host)
        layout.addWidget(self._scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self._status_text = QLabel("就绪")
        self._status_text.setObjectName("Mono")
        self._elapsed_label = QLabel("00:00")
        self._elapsed_label.setObjectName("Mono")
        self._stats_label = QLabel("0 句")
        self._stats_label.setObjectName("Mono")
        self._model_badge = QLabel("")
        self._model_badge.setStyleSheet(
            f"color: {theme.MUTED}; font-size: 10px; background: {theme.BG_SOFT};"
            " border-radius: 5px; padding: 2px 6px;"
        )
        footer.addWidget(self._status_text)
        footer.addWidget(self._elapsed_label)
        footer.addWidget(self._stats_label)
        footer.addStretch(1)
        footer.addWidget(self._model_badge)
        layout.addLayout(footer)
        return panel

    def _build_overlay(self) -> None:
        self._overlay = SubtitleOverlay(self.config.overlay)
        self._overlay.settings_requested.connect(self._open_settings)
        self._overlay.hide_requested.connect(self._hide_overlay_from_overlay)
        self._overlay.position_changed.connect(self._on_overlay_moved)
        self._overlay.font_size_changed.connect(self._on_overlay_font_size)

    def _connect_bridge(self) -> None:
        self._bridge.segment.connect(self._on_segment)
        self._bridge.status.connect(self._on_status)
        self._bridge.error.connect(self._on_error)
        self._bridge.finished.connect(self._on_finished)
        self._bridge.language.connect(self._on_language)
        self._bridge.level.connect(self._on_level)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("SectionLabel")
        return label

    # ------------------------------------------------------------------ config/ui
    def _apply_config_to_ui(self) -> None:
        self._source_segment.set_value(self.config.audio.source, emit=False)
        self._source_stack.setCurrentIndex({"system": 0, "microphone": 1, "file": 2}.get(
            self.config.audio.source, 0
        ))
        self._reload_devices()
        self._set_combo(self._target_combo, self.config.translation.target_lang)
        self._set_combo(self._provider_combo, self.config.translation.provider)
        self._overlay_toggle.blockSignals(True)
        self._overlay_toggle.setChecked(self.config.overlay.enabled)
        self._overlay_toggle.blockSignals(False)
        self._overlay.apply_config(self.config.overlay)
        if not self.config.overlay.enabled:
            self._overlay.hide()
        self._refresh_engine_hint()
        self._update_model_badge()

    def _populate_targets(self) -> None:
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        from ..languages import TARGET_LANGUAGES

        for lang in TARGET_LANGUAGES:
            self._target_combo.addItem(lang.name_zh, lang.code)
            self._target_combo.setItemData(
                self._target_combo.count() - 1,
                f"{lang.name_zh}  ·  {lang.name_en}",
                Qt.ToolTipRole,
            )
        self._target_combo.blockSignals(False)

    def _reload_devices(self) -> None:
        current_system = self._system_combo.currentData() if self._system_combo.count() else ""
        current_mic = self._mic_combo.currentData() if self._mic_combo.count() else ""
        system_devices = list_system_devices()
        mic_devices = list_microphones()

        self._system_combo.blockSignals(True)
        self._system_combo.clear()
        if system_devices:
            for device in system_devices:
                self._system_combo.addItem(device.name, device.id)
                self._system_combo.setItemData(
                    self._system_combo.count() - 1, device.name, Qt.ToolTipRole
                )
            wanted = self.config.audio.system_device or current_system
            index = self._system_combo.findData(wanted)
            self._system_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self._system_combo.addItem("未检测到系统音频设备", "__missing__")
        self._system_combo.blockSignals(False)

        self._mic_combo.blockSignals(True)
        self._mic_combo.clear()
        if mic_devices:
            for device in mic_devices:
                label = device.name + ("  · 默认" if device.is_default else "")
                self._mic_combo.addItem(label, device.id)
            wanted = self.config.audio.microphone_device or current_mic
            index = self._mic_combo.findData(wanted)
            self._mic_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self._mic_combo.addItem("未检测到麦克风", "__missing__")
        self._mic_combo.blockSignals(False)

        if self.config.audio.source == "system" and self._system_combo.currentData() not in (None, "__missing__"):
            self.config.audio.system_device = str(self._system_combo.currentData() or "")
        if self.config.audio.source == "microphone" and self._mic_combo.currentData() not in (None, "__missing__"):
            self.config.audio.microphone_device = str(self._mic_combo.currentData() or "")

    def _set_combo(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.blockSignals(True)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _sync_config_from_ui(self, *, save: bool = True) -> None:
        self.config.audio.source = self._source_segment.value
        system = self._system_combo.currentData()
        mic = self._mic_combo.currentData()
        self.config.audio.system_device = "" if system in (None, "__missing__") else str(system)
        self.config.audio.microphone_device = "" if mic in (None, "__missing__") else str(mic)
        self.config.translation.target_lang = self._target_combo.currentData() or "zh"
        self.config.translation.provider = self._provider_combo.currentData() or "auto"
        self.config.overlay.enabled = self._overlay_toggle.isChecked()
        self.config.validate()
        if save:
            try:
                save_config(self.config)
            except OSError as exc:
                log.warning("Could not save config: %s", exc)

    def _refresh_engine_hint(self) -> None:
        service = TranslationService(self.config.translation)
        readiness = service.readiness()
        service.close()
        if readiness.ready:
            self._engine_hint.setText(readiness.message)
            self._engine_hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        else:
            self._engine_hint.setText(readiness.message)
            self._engine_hint.setStyleSheet(f"color: {theme.WARN}; font-size: 11px;")
        self._provider_label.setText(
            {
                "cloud": "云端翻译",
                "local": "本地翻译",
                "off": "仅原文",
                "none": "未配置翻译",
            }.get(readiness.provider, "")
        )

    def _update_model_badge(self) -> None:
        model = resolve_model(self.config.asr)
        try:
            device = resolve_device(self.config.asr)
        except Exception:
            device = "cpu"
        ready, reason = cuda_ready()
        devices = cuda_device_count()
        if device == "cuda":
            label = "GPU"
            tooltip = "NVIDIA CUDA 加速已启用"
        elif devices > 0 and not ready:
            label = "CPU · CUDA 缺失"
            tooltip = f"{reason}\n\n{install_hint()}"
        else:
            label = "CPU"
            tooltip = "未使用 GPU 加速"
        self._model_badge.setText(f"{model} · {label}")
        self._model_badge.setToolTip(tooltip)
        self._side_footer.setText(f"本地识别 · {model} · {label}")
        self._side_footer.setToolTip(tooltip)

    # ------------------------------------------------------------------ sources
    def _on_source_changed(self, value: str) -> None:
        self.config.audio.source = value
        self._source_stack.setCurrentIndex({"system": 0, "microphone": 1, "file": 2}.get(value, 0))
        try:
            save_config(self.config)
        except OSError:
            pass

    def _on_device_changed(self, _index: int | None = None) -> None:
        self._sync_config_from_ui()

    def _browse_file(self) -> None:
        start = str(self._selected_file.parent) if self._selected_file else ""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择要生成字幕的媒体文件",
            start,
            "媒体文件 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mkv *.mov *.webm);;所有文件 (*.*)",
        )
        if filename:
            self._selected_file = Path(filename)
            self._file_edit.setText(filename)
            self._file_edit.setToolTip(filename)

    def _on_target_changed(self, _index: int | None = None) -> None:
        code = self._target_combo.currentData()
        if code:
            self.config.translation.target_lang = code
            try:
                save_config(self.config)
            except OSError:
                pass
            self._refresh_engine_hint()

    def _on_language(self, code: str, probability: float) -> None:
        if not code:
            return
        if probability and probability > 0:
            self._detected_label.setText(f"{language_name(code)} · {probability * 100:.0f}%")
        else:
            self._detected_label.setText(language_name(code))

    def _on_level(self, db: float) -> None:
        self._level_meter.set_level(db)

    def _on_provider_changed(self, _index: int | None = None) -> None:
        code = self._provider_combo.currentData()
        if code:
            self.config.translation.provider = code
            try:
                save_config(self.config)
            except OSError:
                pass
            self._refresh_engine_hint()

    def _toggle_overlay(self, checked: bool) -> None:
        self.config.overlay.enabled = checked
        try:
            save_config(self.config)
        except OSError:
            pass
        if checked:
            self._overlay.apply_config(self.config.overlay)
            if not self._running:
                self._overlay.set_session_hint("字幕窗已就绪，开始后显示字幕")
            self._overlay.show_overlay()
        else:
            self._overlay.hide()

    def _hide_overlay_from_overlay(self) -> None:
        self._overlay.hide()
        self._overlay_toggle.blockSignals(True)
        self._overlay_toggle.setChecked(False)
        self._overlay_toggle.blockSignals(False)
        self.config.overlay.enabled = False
        try:
            save_config(self.config)
        except OSError:
            pass

    def _on_overlay_moved(self, x: int, y: int) -> None:
        self.config.overlay.x = x
        self.config.overlay.y = y
        self._position_timer.start()

    def _save_position(self) -> None:
        try:
            save_config(self.config)
        except OSError:
            pass

    def _on_overlay_font_size(self, size: int) -> None:
        self.config.overlay.font_size = max(14, min(48, size))
        self._overlay.apply_config(self.config.overlay)
        try:
            save_config(self.config)
        except OSError:
            pass

    # ------------------------------------------------------------------ session
    def _toggle_session(self) -> None:
        if self._running or self._stopping:
            self._stop_session()
        else:
            self._start_session()

    def _validate_source(self) -> str | None:
        source = self._source_segment.value
        if source == "system":
            if self._system_combo.currentData() in (None, "__missing__"):
                return "没有检测到系统音频设备。\n\n" + system_audio_hint()
        elif source == "microphone":
            if self._mic_combo.currentData() in (None, "__missing__"):
                return "没有检测到麦克风。请连接设备后点击“刷新”。"
        elif source == "file":
            if self._selected_file is None or not self._selected_file.is_file():
                return "请先选择要生成字幕的音视频文件。"
        return None

    def _start_session(self) -> None:
        if self._stopping:
            return
        error = self._validate_source()
        if error:
            QMessageBox.warning(self, "无法开始", error)
            return
        self._sync_config_from_ui()
        if self._pipeline is None:
            callbacks = PipelineCallbacks(
                on_segment=self._bridge.segment.emit,
                on_status=self._bridge.status.emit,
                on_error=self._bridge.error.emit,
                on_finished=self._bridge.finished.emit,
                on_language=self._bridge.language.emit,
                on_level=self._bridge.level.emit,
            )
            try:
                self._pipeline = CaptionPipeline(self.config, callbacks)
            except Exception as exc:
                log.exception("Could not construct pipeline")
                QMessageBox.critical(self, "初始化失败", str(exc))
                self._status_pill.set_state("error", "初始化失败")
                self._status_text.setText(str(exc))
                return
        readiness = self._pipeline.readiness()
        allow_source_only = False
        if not readiness.ready:
            choice = self._ask_translation_setup(readiness)
            if choice == "settings":
                self._open_settings()
                return
            if choice == "source":
                allow_source_only = True
            else:
                return
        self._clear_captions(silent=True)
        self._session_started = time.monotonic()
        self._elapsed_label.setText("00:00")
        self._status_pill.set_state("loading", "启动中")
        self._status_text.setText("正在准备…")
        self._provider_label.setText("")
        self._detected_label.setText("等待音频")
        self._error_banner.hide()
        try:
            self._pipeline.start(
                file_path=self._selected_file if self._source_segment.value == "file" else None,
                allow_source_only=allow_source_only,
            )
        except Exception as exc:
            log.exception("Could not start pipeline")
            QMessageBox.critical(self, "启动失败", str(exc))
            self._status_pill.set_state("error", "启动失败")
            self._status_text.setText(str(exc))
            return
        self._overlay.clear()
        if self.config.overlay.enabled:
            self._overlay.apply_config(self.config.overlay)
            self._overlay.show_overlay()
        self._set_running(True)
        self._session_timer.start()

    def _ask_translation_setup(self, readiness: Readiness) -> str:
        box = QMessageBox(self)
        box.setWindowTitle("翻译服务尚未就绪")
        box.setIcon(QMessageBox.Information)
        box.setText("现在还没有可用的翻译服务。")
        box.setInformativeText(
            f"{readiness.message}\n\n"
            "你可以先配置云端 API 或下载本地模型，也可以先只显示识别原文。"
        )
        settings_btn = box.addButton("配置翻译", QMessageBox.AcceptRole)
        source_btn = box.addButton("仅显示原文", QMessageBox.ActionRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is settings_btn:
            return "settings"
        if clicked is source_btn:
            return "source"
        return "cancel"

    def _stop_session(self) -> None:
        if self._pipeline is None:
            return
        self._stopping = True
        self._start_btn.setEnabled(False)
        self._start_btn.setText("正在停止…")
        self._status_pill.set_state("loading", "停止中")
        self._status_text.setText("正在停止…")

        def worker() -> None:
            try:
                self._pipeline.stop(timeout=8.0)
            except Exception:
                log.exception("Pipeline stop failed")

        threading.Thread(target=worker, name="subloom-stop", daemon=True).start()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self._start_btn.setEnabled(not self._stopping)
        self._start_btn.setText("停止字幕" if running else ("正在停止…" if self._stopping else "开始字幕"))
        self._start_btn.setProperty("running", running)
        self._start_btn.style().unpolish(self._start_btn)
        self._start_btn.style().polish(self._start_btn)
        for widget in (
            self._source_segment,
            self._source_stack,
            self._target_combo,
            self._provider_combo,
            self._settings_btn,
        ):
            widget.setEnabled(not running)
        if not running:
            self._session_timer.stop()

    def _on_finished(self) -> None:
        if self._closing:
            return
        self._stopping = False
        self._set_running(False)
        self._status_pill.set_state("ready", "就绪")
        self._status_text.setText("已停止")
        self._start_btn.setEnabled(True)
        self._update_stats()
        self._export_btn.setEnabled(bool(self.transcript.finals))
        if self.config.overlay.enabled:
            self._overlay.set_session_hint("字幕已停止")

    def _on_status(self, message: str) -> None:
        self._status_text.setText(message)
        if not self._running:
            return
        if any(token in message for token in ("准备", "加载", "下载", "启动", "完成最后")):
            self._status_pill.set_state("loading", "准备中")
        elif "聆听" in message:
            self._status_pill.set_state("listening", "聆听中")
        elif "停止" in message:
            self._status_pill.set_state("ready", "停止中")

    def _on_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_banner.show()
        self._error_timer.start(12000)
        self._status_pill.set_state("error", "发生错误")
        self._status_text.setText(message.splitlines()[0][:120])
        self._stopping = True
        self._start_btn.setEnabled(False)
        self._start_btn.setText("正在停止…")

    def _on_segment(self, segment: CaptionSegment) -> None:
        stored = self.transcript.upsert(segment)
        self._render_segment(stored)
        if self.config.overlay.enabled:
            self._overlay.set_segment(stored)
        self._export_btn.setEnabled(bool(self.transcript.finals))
        self._stats_label.setText(f"{len(self.transcript.finals)} 句")
        if stored.source_lang:
            self._detected_label.setText(language_name(stored.source_lang))
        if stored.provider:
            self._provider_label.setText(
                {"cloud": "云端翻译", "local": "本地翻译"}.get(stored.provider, "")
            )
        if stored.is_final:
            self._status_text.setText("已识别一句，继续聆听…")
        elif stored.translation_pending:
            self._status_text.setText("翻译中…")

    def _render_segment(self, segment: CaptionSegment) -> None:
        card = self._cards.get(segment.id)
        if card is None:
            card = CaptionCard(segment, self.config.ui.show_source_in_main)
            self._cards[segment.id] = card
            self._empty.hide()
            self._caption_layout.insertWidget(self._caption_layout.count() - 1, card)
            self._trim_cards()
        else:
            card.update_segment(segment, self.config.ui.show_source_in_main)
        if self._is_near_bottom():
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _trim_cards(self) -> None:
        if len(self._cards) <= 260:
            return
        oldest_id = next(iter(self._cards))
        card = self._cards.pop(oldest_id)
        self._caption_layout.removeWidget(card)
        card.deleteLater()

    def _is_near_bottom(self) -> bool:
        bar = self._scroll.verticalScrollBar()
        return bar.value() >= bar.maximum() - 120

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_captions(self, silent: bool = False) -> None:
        if not silent and self.transcript.finals:
            answer = QMessageBox.question(
                self,
                "清空字幕",
                "确定清空当前字幕吗？已导出的文件不会受影响。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.transcript.clear()
        for card in self._cards.values():
            self._caption_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._empty.show()
        self._export_btn.setEnabled(False)
        self._stats_label.setText("0 句")
        if not self._running:
            self._overlay.clear()
        self._status_text.setText("就绪")

    def _update_stats(self) -> None:
        if self._session_started is None:
            return
        if self._running:
            elapsed = int(time.monotonic() - self._session_started)
            self._elapsed_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self._stats_label.setText(f"{len(self.transcript.finals)} 句")

    # ------------------------------------------------------------------ actions
    def _export_menu(self) -> None:
        if not self.transcript.finals:
            QMessageBox.information(self, "导出", "还没有已完成识别和翻译的句子。")
            return
        menu = QMenu(self)
        translated = menu.addAction("导出译文 SRT")
        bilingual = menu.addAction("导出双语 SRT")
        menu.addAction("导出纯文本")
        action = menu.exec(self._export_btn.mapToGlobal(QPoint(0, self._export_btn.height() + 4)))
        if action is None:
            return
        if action is translated:
            self._save_export("srt", False)
        elif action is bilingual:
            self._save_export("srt", True)
        else:
            self._save_export("txt", False)

    def _save_export(self, kind: str, bilingual: bool) -> None:
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or str(Path.home())
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        suffix = "srt" if kind == "srt" else "txt"
        suggested = str(Path(docs) / f"subloom-{stamp}.{suffix}")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出字幕",
            suggested,
            "SRT 字幕 (*.srt)" if kind == "srt" else "文本文件 (*.txt)",
        )
        if not filename:
            return
        try:
            if kind == "srt":
                from ..subtitles import save_srt

                save_srt(filename, self.transcript.segments, bilingual=bilingual)
            else:
                Path(filename).write_text(
                    self.transcript.text(bilingual=bilingual), encoding="utf-8-sig"
                )
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self._status_text.setText(f"已导出：{Path(filename).name}")
        self._status_pill.set_state("ready", "已导出")

    def _open_settings(self) -> None:
        if self._running or self._stopping:
            QMessageBox.information(self, "请先停止", "请先停止当前字幕，再修改设置。")
            return
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != SettingsDialog.Accepted:
            return
        self.config = dialog.config
        try:
            save_config(self.config)
        except OSError as exc:
            log.warning("Could not save settings: %s", exc)
        if self._pipeline is not None:
            self._pipeline.close()
            self._pipeline = None
        self._apply_config_to_ui()
        self._refresh_engine_hint()
        self._update_model_badge()
        if self.config.overlay.enabled:
            self._overlay.apply_config(self.config.overlay)
            if self._running:
                self._overlay.show_overlay()
        else:
            self._overlay.hide()

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "快速开始",
            "1. 选择音频来源：系统声音、麦克风或一个媒体文件。\n\n"
            "2. 选择目标语言和翻译方式。推荐先配置云端 API；没有 API 时可下载本地 NLLB 模型。\n\n"
            "3. 点击「开始字幕」。识别在本机完成，悬浮字幕窗会置顶显示翻译。\n\n"
            "4. 结束后点击「导出」保存 SRT 或纯文本。\n\n"
            "提示：首次使用需要下载识别模型；模型保存在用户数据目录，不会进入 Git 仓库。",
        )

    def _maybe_first_run(self) -> None:
        if not self.config.first_run:
            return
        self.config.first_run = False
        try:
            save_config(self.config)
        except OSError:
            pass
        self._status_text.setText("首次使用：建议先在「设置 → 翻译」中配置服务")

    # ------------------------------------------------------------------ geometry
    def _restore_geometry(self) -> None:
        settings = QSettings("SubLoom", "SubLoom")
        geometry = settings.value("window_geometry")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass

    def _save_geometry(self) -> None:
        settings = QSettings("SubLoom", "SubLoom")
        settings.setValue("window_geometry", self.saveGeometry())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._running or self._stopping:
            answer = QMessageBox.question(
                self,
                "退出 SubLoom",
                "字幕仍在运行，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self._closing = True
        self._sync_config_from_ui()
        if self._pipeline is not None:
            try:
                self._pipeline.close()
            except Exception:
                log.debug("Pipeline close failed", exc_info=True)
        self._overlay.close()
        self._save_geometry()
        event.accept()


def make_app_icon() -> QIcon:
    from ..paths import resource_path

    icon_path = resource_path("assets", "icon.png")
    if icon_path.is_file():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    mark = LogoMark(64)
    mark.render(pixmap)
    return QIcon(pixmap)
