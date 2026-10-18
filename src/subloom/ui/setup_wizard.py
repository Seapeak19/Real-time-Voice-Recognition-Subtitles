"""First-run setup wizard for audio, translation and recognition."""

from __future__ import annotations

import copy
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from ..asr.cuda_runtime import cuda_device_count, cuda_ready, install_hint
from ..asr.whisper_engine import WHISPER_MODELS
from ..audio.devices import list_microphones, list_system_devices, system_audio_hint
from ..config import AppConfig, save_config
from ..i18n import language_choice_label, tr
from ..languages import TARGET_LANGUAGES
from ..secrets import get_api_key, mask_key, set_api_key
from . import theme
from .widgets import LogoMark

log = logging.getLogger(__name__)


class SetupWizard(QWizard):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = copy.deepcopy(config)
        self.setWindowTitle(tr("SubLoom 设置向导"))
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.HaveHelpButton, False)
        self.resize(780, 620)
        self.setButtonText(QWizard.NextButton, tr("下一步"))
        self.setButtonText(QWizard.BackButton, tr("上一步"))
        self.setButtonText(QWizard.FinishButton, tr("完成"))
        self.setButtonText(QWizard.CancelButton, tr("取消"))
        self._build_pages()

    # ------------------------------------------------------------------ pages
    def _build_pages(self) -> None:
        self.addPage(self._build_welcome_page())
        self.addPage(self._build_audio_page())
        self.addPage(self._build_translation_page())
        self.addPage(self._build_recognition_page())
        self.addPage(self._build_finish_page())

    def _build_welcome_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle(tr("欢迎使用 SubLoom 织幕"))
        page.setSubTitle(
            tr("三步完成设置：选择声音、配置翻译、确认识别设备。之后都可以在设置中修改。")
        )
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(14)

        mark = LogoMark(72)
        layout.addWidget(mark, 0, Qt.AlignHCenter)
        intro = QLabel(
            tr("实时识别语音，并把翻译字幕显示在置顶悬浮窗中。")
        )
        intro.setAlignment(Qt.AlignCenter)
        intro.setStyleSheet(f"color: {theme.TEXT}; font-size: 16px; font-weight: 600;")
        layout.addWidget(intro)

        for text in (
            tr("音频默认不上传，语音识别在本机完成。"),
            tr("翻译可使用云端 API，也可以下载本地模型离线运行。"),
            tr("悬浮字幕可以拖动、调字体/颜色，并停留足够时间供阅读。"),
        ):
            label = QLabel("•  " + text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
            layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _build_audio_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle(tr("选择音频来源"))
        page.setSubTitle(tr("先选系统声音或麦克风；也可以稍后在主界面切换到媒体文件。"))
        form = QFormLayout(page)
        form.setContentsMargins(12, 18, 12, 12)
        form.setSpacing(10)

        self._source_combo = QComboBox()
        self._source_combo.addItem(tr("系统声音（推荐）"), "system")
        self._source_combo.addItem(tr("麦克风"), "microphone")
        self._source_combo.addItem(tr("媒体文件（稍后选择）"), "file")
        index = self._source_combo.findData(self.config.audio.source)
        self._source_combo.setCurrentIndex(index if index >= 0 else 0)
        self._source_combo.currentIndexChanged.connect(self._refresh_devices)
        form.addRow(tr("音频来源"), self._source_combo)

        device_row = QHBoxLayout()
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(360)
        refresh = QPushButton(tr("刷新设备"))
        refresh.setObjectName("GhostButton")
        refresh.clicked.connect(self._refresh_devices)
        device_row.addWidget(self._device_combo, 1)
        device_row.addWidget(refresh)
        form.addRow(tr("设备"), device_row)

        self._audio_hint = QLabel()
        self._audio_hint.setObjectName("Hint")
        self._audio_hint.setWordWrap(True)
        form.addRow(self._audio_hint)
        self._refresh_devices()
        return page

    def _refresh_devices(self) -> None:
        if not hasattr(self, "_device_combo"):
            return
        source = self._source_combo.currentData() or "system"
        self._device_combo.clear()
        if source == "file":
            self._device_combo.setEnabled(False)
            self._device_combo.addItem(tr("在主界面选择媒体文件"), "__file__")
            self._audio_hint.setText(tr("向导只保存文件模式；具体文件在主界面选择。"))
            return
        self._device_combo.setEnabled(True)
        if source == "system":
            devices = list_system_devices()
            saved = self.config.audio.system_device
            self._audio_hint.setText(system_audio_hint())
        else:
            devices = list_microphones()
            saved = self.config.audio.microphone_device
            self._audio_hint.setText(
                tr("适合现场讲话、会议发言和课堂；请在系统设置中确认麦克风权限。")
            )
        if not devices:
            label = tr("未检测到系统音频设备") if source == "system" else tr("未检测到麦克风")
            self._device_combo.addItem(label, "__missing__")
            return
        for device in devices:
            suffix = (
                "  · " + tr("默认")
                if device.is_default and tr("默认") not in device.name
                else ""
            )
            self._device_combo.addItem(device.name + suffix, device.id)
        index = self._device_combo.findData(saved)
        self._device_combo.setCurrentIndex(index if index >= 0 else 0)

    def _build_translation_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle(tr("配置翻译"))
        page.setSubTitle(tr("推荐使用云端 API；没有 API 时可下载本地模型完全离线运行。"))
        form = QFormLayout(page)
        form.setContentsMargins(12, 18, 12, 12)
        form.setSpacing(10)

        self._target_combo = QComboBox()
        for lang in TARGET_LANGUAGES:
            self._target_combo.addItem(language_choice_label(lang.code), lang.code)
        index = self._target_combo.findData(self.config.translation.target_lang)
        self._target_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(tr("目标语言"), self._target_combo)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem(tr("自动（有云端 Key 时优先云端）"), "auto")
        self._provider_combo.addItem(tr("云端 API"), "cloud")
        self._provider_combo.addItem(tr("本地 NLLB 模型"), "local")
        self._provider_combo.addItem(tr("仅识别，不翻译"), "off")
        index = self._provider_combo.findData(self.config.translation.provider)
        self._provider_combo.setCurrentIndex(index if index >= 0 else 0)
        self._provider_combo.currentIndexChanged.connect(self._sync_provider)
        form.addRow(tr("翻译方式"), self._provider_combo)

        self._cloud_box = QGroupBox(tr("云端翻译"))
        cloud_form = QFormLayout(self._cloud_box)
        cloud_form.setContentsMargins(14, 18, 14, 12)
        cloud_form.setSpacing(9)
        self._base_url_edit = QLineEdit(self.config.translation.cloud.base_url)
        self._base_url_edit.setPlaceholderText("https://api.deepseek.com/v1")
        cloud_form.addRow(tr("API 地址"), self._base_url_edit)
        self._cloud_model_edit = QLineEdit(self.config.translation.cloud.model)
        self._cloud_model_edit.setPlaceholderText("deepseek-chat")
        cloud_form.addRow(tr("模型"), self._cloud_model_edit)
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.Password)
        existing = get_api_key()
        self._key_edit.setPlaceholderText(
            tr("已保存：{mask}（留空不修改）", mask=mask_key(existing))
            if existing
            else tr("sk-…（保存到系统钥匙串）")
        )
        cloud_form.addRow("API Key", self._key_edit)
        key_note = QLabel(
            tr("Key 只保存在系统钥匙串；翻译时只发送识别后的文本。")
        )
        key_note.setObjectName("Hint")
        key_note.setWordWrap(True)
        cloud_form.addRow("", key_note)
        form.addRow(self._cloud_box)

        self._local_note = QLabel(
            tr("本地模型约 650MB，需要单独下载；不下载也可以先使用云端。")
        )
        self._local_note.setObjectName("Hint")
        self._local_note.setWordWrap(True)
        form.addRow(self._local_note)
        self._sync_provider()
        return page

    def _sync_provider(self) -> None:
        if not hasattr(self, "_cloud_box"):
            return
        provider = self._provider_combo.currentData() or "auto"
        self._cloud_box.setEnabled(provider in {"auto", "cloud"})

    def _build_recognition_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle(tr("识别与性能"))
        page.setSubTitle(tr("第一次开始字幕时会自动下载识别模型。"))
        form = QFormLayout(page)
        form.setContentsMargins(12, 18, 12, 12)
        form.setSpacing(10)

        self._device_combo_asr = QComboBox()
        self._device_combo_asr.addItem(tr("自动选择"), "auto")
        self._device_combo_asr.addItem("NVIDIA GPU (CUDA)", "cuda")
        self._device_combo_asr.addItem("CPU", "cpu")
        index = self._device_combo_asr.findData(self.config.asr.device)
        self._device_combo_asr.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(tr("计算设备"), self._device_combo_asr)

        self._model_combo = QComboBox()
        labels = {
            "auto": tr("自动（GPU 用 large-v3-turbo）"),
            "large-v3-turbo": tr("Large v3 Turbo · 快且准（约 1.6 GB）"),
            "small": tr("Small · 轻量（约 484 MB）"),
            "base": tr("Base · 更快（约 145 MB）"),
        }
        for value in ("auto", "large-v3-turbo", "small", "base"):
            if value == "auto" or value in WHISPER_MODELS:
                self._model_combo.addItem(labels[value], value)
        index = self._model_combo.findData(self.config.asr.model)
        self._model_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow(tr("识别模型"), self._model_combo)

        ready, reason = cuda_ready()
        devices = cuda_device_count()
        if ready:
            status = tr("● CUDA 可用，识别将使用 NVIDIA GPU 加速。")
            color = theme.ACCENT
        elif devices > 0:
            status = tr("⚠ 检测到 NVIDIA GPU，但 CUDA 运行库不可用，将回退 CPU。")
            color = theme.WARN
        else:
            status = tr("○ 未检测到可用的 NVIDIA GPU，将使用 CPU。")
            color = theme.MUTED
        status_label = QLabel(status)
        status_label.setWordWrap(True)
        status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        form.addRow(status_label)
        if reason:
            detail = QLabel(reason + "\n\n" + install_hint())
            detail.setObjectName("Hint")
            detail.setWordWrap(True)
            form.addRow(detail)
        note = QLabel(
            tr("保持“自动选择”即可；模型会保存到用户数据目录，不会进入 Git 仓库。")
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def _build_finish_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle(tr("准备完成"))
        page.setSubTitle(tr("确认下面的设置，之后可以随时在设置中修改。"))
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(10)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 12px; background: {theme.PANEL};"
            " border: 1px solid #2E2644; border-radius: 10px;"
            " padding: 14px 16px;"
        )
        layout.addWidget(self._summary)
        note = QLabel(
            tr("点击“完成”后，选择音频来源并点击主界面的“开始字幕”。")
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ flow
    def initializePage(self, page_id: int) -> None:  # noqa: N802
        super().initializePage(page_id)
        if page_id == 4:
            self._summary.setText(
                tr(
                    "音频来源：{source}\n目标语言：{target}\n翻译方式：{provider}\n计算设备：{device}",
                    source=self._source_combo.currentText(),
                    target=self._target_combo.currentText(),
                    provider=self._provider_combo.currentText(),
                    device=self._device_combo_asr.currentText(),
                )
            )

    def _apply(self) -> bool:
        cfg = self.config
        source = self._source_combo.currentData() or "system"
        cfg.audio.source = source
        device_id = self._device_combo.currentData()
        if device_id in (None, "__missing__", "__file__"):
            device_id = ""
        if source == "system":
            cfg.audio.system_device = str(device_id or "")
        elif source == "microphone":
            cfg.audio.microphone_device = str(device_id or "")
        cfg.translation.target_lang = self._target_combo.currentData() or "zh"
        cfg.translation.provider = self._provider_combo.currentData() or "auto"
        cfg.translation.cloud.base_url = (
            self._base_url_edit.text().strip() or "https://api.deepseek.com/v1"
        )
        cfg.translation.cloud.model = (
            self._cloud_model_edit.text().strip() or "deepseek-chat"
        )
        cfg.asr.device = self._device_combo_asr.currentData() or "auto"
        cfg.asr.model = self._model_combo.currentData() or "auto"
        if cfg.asr.device == "cpu" and cfg.asr.compute_type in {"float16", "int8_float16"}:
            cfg.asr.compute_type = "int8"
        cfg.first_run = False
        cfg.validate()
        if cfg.translation.provider in {"cloud", "auto"}:
            if not cfg.translation.cloud.base_url or not cfg.translation.cloud.model:
                QMessageBox.warning(
                    self, tr("设置无效"), tr("请填写云端 API 地址和模型名。")
                )
                return False
        return True

    def accept(self) -> None:
        if not self._apply():
            return
        typed_key = self._key_edit.text().strip()
        if typed_key:
            ok, error = set_api_key(typed_key)
            if not ok:
                QMessageBox.warning(
                    self,
                    tr("无法保存 API Key"),
                    tr("无法写入系统钥匙串：{error}", error=error),
                )
                return
        try:
            save_config(self.config)
        except OSError as exc:
            QMessageBox.warning(self, tr("保存失败"), str(exc))
            return
        log.info("Setup wizard completed")
        super().accept()
