"""Settings dialog for recognition, translation, and overlay preferences."""

from __future__ import annotations

import copy
import logging
from dataclasses import replace

from PySide6.QtCore import QEventLoop, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..asr.cuda_runtime import cuda_device_count, cuda_ready, install_hint
from ..asr.whisper_engine import (
    WHISPER_MODELS,
    download_model,
    model_available,
    resolve_model,
)
from ..config import AppConfig, CloudConfig
from ..i18n import UI_LANGUAGES, language_choice_label, tr
from ..languages import TARGET_LANGUAGES
from ..secrets import get_api_key, mask_key, set_api_key
from ..translate.cloud import CloudTranslator
from ..translate.nllb import (
    NLLB_LICENSE,
    NLLB_SIZE_HINT,
    download_local_model,
    local_model_available,
)
from . import theme

log = logging.getLogger(__name__)


class _TaskThread(QThread):
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn(self.progress.emit)
            self.done.emit(True, "" if result is None else str(result))
        except Exception as exc:
            log.exception("Background task failed")
            self.done.emit(False, str(exc))


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = copy.deepcopy(config)
        self._clear_key = False
        self._threads: list[_TaskThread] = []
        self.setWindowTitle(tr("SubLoom 设置"))
        self.setMinimumSize(790, 700)
        self.resize(810, 720)
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)
        title = QLabel(tr("设置"))
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT};")
        subtitle = QLabel(tr("调整识别、翻译与字幕显示。修改会在下次开始字幕时生效。"))
        subtitle.setObjectName("Hint")
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._wrap(self._build_asr_tab()), tr("识别"))
        tabs.addTab(self._wrap(self._build_translation_tab()), tr("翻译"))
        tabs.addTab(self._wrap(self._build_overlay_tab()), tr("字幕"))
        tabs.addTab(self._wrap(self._build_interface_tab()), tr("界面"))
        tabs.addTab(self._wrap(self._build_about_tab()), tr("关于"))
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        save = buttons.button(QDialogButtonBox.Save)
        save.setText(tr("保存"))
        save.setObjectName("PrimaryButton")
        save.setMinimumWidth(110)
        cancel = buttons.button(QDialogButtonBox.Cancel)
        cancel.setText(tr("取消"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _wrap(self, widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(widget)
        return area

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return form

    # ------------------------------------------------------------------ ASR
    def _build_asr_tab(self) -> QWidget:
        page = QWidget()
        form = self._form()
        page.setLayout(form)

        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        labels = {
            "auto": tr("自动（推荐：GPU 用 large-v3-turbo）"),
            "large-v3-turbo": tr("Large v3 Turbo · 快且准（约 1.6 GB）"),
            "large-v3": tr("Large v3 · 最高准确率（约 3.1 GB）"),
            "distil-large-v3.5": tr("Distil Large v3.5 · 英文优先（约 1.5 GB）"),
            "distil-large-v3": tr("Distil Large v3 · 英文优先（约 1.5 GB）"),
            "medium": tr("Medium · 均衡（约 1.5 GB）"),
            "small": tr("Small · 轻量（约 484 MB）"),
            "base": tr("Base · 更快（约 145 MB）"),
            "tiny": tr("Tiny · 仅测试（约 75 MB）"),
        }
        for value in WHISPER_MODELS:
            self._model_combo.addItem(labels.get(value, value), value)
        self._set_combo(self._model_combo, self.config.asr.model)
        model_row.addWidget(self._model_combo, 1)
        self._download_whisper_btn = QPushButton(tr("预下载"))
        self._download_whisper_btn.setObjectName("SecondaryButton")
        self._download_whisper_btn.clicked.connect(self._download_whisper)
        model_row.addWidget(self._download_whisper_btn)
        form.addRow(tr("识别模型"), model_row)
        self._asr_status = QLabel()
        self._asr_status.setObjectName("Hint")
        self._asr_status.setWordWrap(True)
        form.addRow("", self._asr_status)

        self._device_combo = QComboBox()
        for value, label in (
            ("auto", tr("自动选择")),
            ("cuda", "NVIDIA GPU (CUDA)"),
            ("cpu", "CPU"),
        ):
            self._device_combo.addItem(label, value)
        self._set_combo(self._device_combo, self.config.asr.device)
        form.addRow(tr("计算设备"), self._device_combo)

        self._compute_combo = QComboBox()
        for value, label in (
            ("auto", tr("自动")),
            ("float16", tr("float16 · GPU 推荐")),
            ("int8_float16", "int8_float16"),
            ("int8", tr("int8 · CPU 推荐")),
            ("float32", tr("float32 · 兼容性最好")),
        ):
            self._compute_combo.addItem(label, value)
        self._set_combo(self._compute_combo, self.config.asr.compute_type)
        form.addRow(tr("计算精度"), self._compute_combo)
        self._gpu_status = QLabel()
        self._gpu_status.setWordWrap(True)
        self._gpu_status.setObjectName("Hint")
        form.addRow("GPU", self._gpu_status)
        self._model_combo.currentIndexChanged.connect(self._refresh_asr_status)
        self._refresh_gpu_status()

        self._source_lang_combo = QComboBox()
        self._source_lang_combo.addItem(tr("自动检测（推荐）"), "auto")
        for lang in TARGET_LANGUAGES:
            if lang.code == "zh-Hant":
                continue
            self._source_lang_combo.addItem(
                language_choice_label(lang.code), lang.code
            )
        self._set_combo(self._source_lang_combo, self.config.asr.language)
        form.addRow(tr("源语言"), self._source_lang_combo)
        source_hint = QLabel(tr("保持自动检测即可；锁定源语言可以避免短句误判。"))
        source_hint.setObjectName("Hint")
        form.addRow("", source_hint)

        self._silence_slider, self._silence_label = self._slider_row(
            form,
            tr("断句静音"),
            200,
            1500,
            self.config.asr.silence_ms,
            " ms",
            tr("越短越实时，但句子可能被切碎。"),
        )
        self._max_segment_slider, self._max_segment_label = self._slider_row(
            form,
            tr("最长句长"),
            3,
            20,
            int(self.config.asr.max_segment_sec),
            " s" if tr("秒") == "s" else " 秒",
            tr("连续讲话时强制断句，避免字幕过长。"),
        )
        self._partial_slider, self._partial_label = self._slider_row(
            form,
            tr("局部刷新"),
            300,
            1500,
            self.config.asr.partial_interval_ms,
            " ms",
            tr("说话过程中更新字幕的频率。"),
        )
        self._context_check = QCheckBox(tr("用上一句作为识别上下文（提升专有名词准确率）"))
        self._context_check.setChecked(self.config.asr.use_context_prompt)
        form.addRow("", self._context_check)
        form.addRow("", QLabel(""))
        self._refresh_asr_status()

        note = QLabel(
            tr(
                "识别完全在本机完成，音频不会上传。首次使用会下载模型；下载后保存在用户数据目录，"
                "不进入 Git 仓库。"
            )
        )
        note.setWordWrap(True)
        note.setObjectName("Hint")
        form.addRow(note)
        return page

    def _slider_row(
        self,
        form: QFormLayout,
        label: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
        hint: str = "",
    ) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        value_label = QLabel(f"{value}{suffix}")
        value_label.setFixedWidth(62)
        value_label.setStyleSheet(f"color: {theme.ACCENT}; font-weight: 600;")
        slider.valueChanged.connect(lambda v: value_label.setText(f"{v}{suffix}"))
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        form.addRow(label, row)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("Hint")
            hint_label.setWordWrap(True)
            form.addRow("", hint_label)
        return slider, value_label

    # ------------------------------------------------------------------ translation
    def _build_translation_tab(self) -> QWidget:
        page = QWidget()
        form = self._form()
        page.setLayout(form)

        self._provider_combo = QComboBox()
        for value, label in (
            ("auto", tr("自动（有云端 Key 时优先云端）")),
            ("cloud", tr("云端 API")),
            ("local", tr("本地 NLLB 模型")),
            ("off", tr("仅识别，不翻译")),
        ):
            self._provider_combo.addItem(label, value)
        self._set_combo(self._provider_combo, self.config.translation.provider)
        self._provider_combo.currentIndexChanged.connect(self._refresh_translation_status)
        form.addRow(tr("翻译方式"), self._provider_combo)

        self._target_lang_combo = QComboBox()
        for lang in TARGET_LANGUAGES:
            self._target_lang_combo.addItem(language_choice_label(lang.code), lang.code)
        self._set_combo(self._target_lang_combo, self.config.translation.target_lang)
        form.addRow(tr("目标语言"), self._target_lang_combo)

        self._partials_check = QCheckBox(tr("说话过程中也翻译（更实时，云端会增加调用次数）"))
        self._partials_check.setChecked(self.config.translation.translate_partials)
        form.addRow("", self._partials_check)

        cloud_box = QGroupBox(tr("云端翻译"))
        cloud_form = QFormLayout(cloud_box)
        cloud_form.setContentsMargins(14, 18, 14, 12)
        cloud_form.setSpacing(10)
        self._base_url_edit = QLineEdit(self.config.translation.cloud.base_url)
        self._base_url_edit.setPlaceholderText("https://api.deepseek.com/v1")
        cloud_form.addRow(tr("API 地址"), self._base_url_edit)
        self._cloud_model_edit = QLineEdit(self.config.translation.cloud.model)
        self._cloud_model_edit.setPlaceholderText("deepseek-chat")
        cloud_form.addRow(tr("模型"), self._cloud_model_edit)
        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.Password)
        existing = get_api_key()
        self._key_edit.setPlaceholderText(
            tr("已保存：{mask}（留空不修改）", mask=mask_key(existing))
            if existing
            else tr("sk-…（保存到系统钥匙串）")
        )
        self._show_key_btn = QPushButton(tr("显示"))
        self._show_key_btn.setObjectName("GhostButton")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(
            lambda checked: self._key_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        clear_btn = QPushButton(tr("清除"))
        clear_btn.setObjectName("DangerGhostButton")
        clear_btn.clicked.connect(self._clear_saved_key)
        key_row.addWidget(self._key_edit, 1)
        key_row.addWidget(self._show_key_btn)
        key_row.addWidget(clear_btn)
        cloud_form.addRow("API Key", key_row)
        timeout_row = QHBoxLayout()
        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(2.0, 60.0)
        self._timeout_spin.setDecimals(1)
        self._timeout_spin.setSuffix(tr(" 秒"))
        self._timeout_spin.setMinimumWidth(120)
        self._timeout_spin.setValue(self.config.translation.cloud.timeout_sec)
        self._retries_spin = QSpinBox()
        self._retries_spin.setRange(0, 3)
        self._retries_spin.setMinimumWidth(90)
        self._retries_spin.setValue(self.config.translation.cloud.max_retries)
        timeout_row.addWidget(QLabel(tr("超时")))
        timeout_row.addWidget(self._timeout_spin)
        timeout_row.addSpacing(10)
        timeout_row.addWidget(QLabel(tr("重试")))
        timeout_row.addWidget(self._retries_spin)
        timeout_row.addStretch(1)
        cloud_form.addRow(tr("请求"), timeout_row)
        self._test_cloud_btn = QPushButton(tr("测试云端翻译"))
        self._test_cloud_btn.setObjectName("SecondaryButton")
        self._test_cloud_btn.clicked.connect(self._test_cloud)
        cloud_form.addRow("", self._test_cloud_btn)
        self._cloud_test_status = QLabel("")
        self._cloud_test_status.setWordWrap(True)
        self._cloud_test_status.setObjectName("Hint")
        cloud_form.addRow("", self._cloud_test_status)
        form.addRow(cloud_box)

        local_box = QGroupBox(tr("本地翻译（离线兜底）"))
        local_layout = QVBoxLayout(local_box)
        local_layout.setContentsMargins(14, 18, 14, 12)
        local_layout.setSpacing(8)
        self._local_status = QLabel()
        self._local_status.setWordWrap(True)
        local_layout.addWidget(self._local_status)
        local_note = QLabel(
            tr(
                "NLLB-200 distilled 600M · {size}。模型许可为 {license}，"
                "请根据你的使用场景确认是否可用。模型不随仓库分发。",
                size=tr(NLLB_SIZE_HINT),
                license=tr(NLLB_LICENSE),
            )
        )
        local_note.setWordWrap(True)
        local_note.setObjectName("Hint")
        local_layout.addWidget(local_note)
        local_row = QHBoxLayout()
        self._download_local_btn = QPushButton(tr("下载本地模型"))
        self._download_local_btn.setObjectName("SecondaryButton")
        self._download_local_btn.clicked.connect(self._download_local)
        local_row.addWidget(self._download_local_btn)
        local_row.addStretch(1)
        local_layout.addLayout(local_row)
        form.addRow(local_box)

        self._translation_status = QLabel("")
        self._translation_status.setWordWrap(True)
        self._translation_status.setObjectName("Hint")
        form.addRow(self._translation_status)
        form.addRow("", QLabel(""))
        self._refresh_local_status()
        self._refresh_translation_status()
        return page

    # ------------------------------------------------------------------ overlay
    def _build_overlay_tab(self) -> QWidget:
        page = QWidget()
        form = self._form()
        page.setLayout(form)
        self._overlay_enabled = QCheckBox(tr("启动字幕时显示悬浮字幕窗"))
        self._overlay_enabled.setChecked(self.config.overlay.enabled)
        form.addRow("", self._overlay_enabled)
        self._overlay_source = QCheckBox(tr("同时显示原文"))
        self._overlay_source.setChecked(self.config.overlay.show_source)
        form.addRow("", self._overlay_source)
        self._overlay_click = QCheckBox(
            tr("鼠标穿透（字幕窗不挡操作；启用后需从主界面修改设置）")
        )
        self._overlay_click.setChecked(self.config.overlay.click_through)
        form.addRow("", self._overlay_click)
        self._font_slider, self._font_label = self._slider_row(
            form, tr("正文字号"), 14, 48, self.config.overlay.font_size, " px"
        )
        self._opacity_slider, self._opacity_label = self._slider_row(
            form, tr("背景不透明度"), 30, 100, int(self.config.overlay.opacity * 100), " %"
        )
        self._width_slider, self._width_label = self._slider_row(
            form, tr("字幕窗宽度"), 600, 1600, self.config.overlay.width, " px"
        )
        self._hold_slider, self._hold_label = self._slider_row(
            form,
            tr("最短停留"),
            800,
            3000,
            self.config.overlay.hold_ms,
            " ms",
            tr("保证一句译文至少显示这么久，避免还没看完就被下一句替换。"),
        )
        reset = QPushButton(tr("恢复默认位置"))
        reset.setObjectName("SecondaryButton")
        reset.clicked.connect(lambda: self._reset_position(True))
        form.addRow(tr("位置"), reset)
        self._reset_pos_requested = False
        hint = QLabel(tr("提示：可以直接拖动悬浮字幕窗；右键可快速调整字号或隐藏。"))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page

    def _reset_position(self, requested: bool) -> None:
        self._reset_pos_requested = requested

    # ------------------------------------------------------------------ interface
    def _build_interface_tab(self) -> QWidget:
        page = QWidget()
        form = self._form()
        page.setLayout(form)
        self._ui_language_combo = QComboBox()
        for code, label in UI_LANGUAGES:
            self._ui_language_combo.addItem(label, code)
        self._set_combo(self._ui_language_combo, self.config.ui.language)
        form.addRow(tr("界面语言"), self._ui_language_combo)
        hint = QLabel(tr("切换后需要重启 SubLoom 才会生效。"))
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow("", hint)
        form.addRow("", QLabel(""))
        return page

    # ------------------------------------------------------------------ about
    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        title = QLabel("SubLoom · 织幕")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {theme.ACCENT};")
        layout.addWidget(title)
        desc = QLabel(
            tr(
                "跨平台实时语音翻译字幕。识别在本机完成，翻译可选择云端或本地模型；"
                "音频默认不离开设备。"
            )
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        info = QLabel(
            tr(
                "版本 {version}\n代码许可：MIT\n识别模型：faster-whisper（MIT）\n本地翻译模型：NLLB-200（CC BY-NC 4.0，模型单独下载）\n云端翻译：由你配置的服务商提供，费用与隐私政策以其条款为准。",
                version=__version__,
            )
        )
        info.setWordWrap(True)
        info.setObjectName("Hint")
        layout.addWidget(info)
        link = QLabel(
            '<a href="https://github.com/Seapeak19/Real-time-Voice-Recognition-Subtitles">'
            f"{tr('项目主页 / 问题反馈')}</a>"
        )
        link.setOpenExternalLinks(True)
        link.setStyleSheet(f"color: {theme.ACCENT};")
        layout.addWidget(link)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ status
    def _refresh_asr_status(self) -> None:
        model = self._selected_model()
        available = model_available(replace(self.config.asr, model=model))
        if available:
            self._asr_status.setText(tr("● {model} 已下载，启动时直接加载。", model=model))
            self._asr_status.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px;")
        else:
            self._asr_status.setText(tr("○ 尚未下载，首次开始时会自动下载（也可点“预下载”）。"))
            self._asr_status.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")

    def _selected_model(self) -> str:
        value = self._model_combo.currentData() or "auto"
        if value != "auto":
            return value
        return resolve_model(self.config.asr)

    def _refresh_gpu_status(self) -> None:
        ready, reason = cuda_ready()
        devices = cuda_device_count()
        if ready:
            self._gpu_status.setText(tr("● CUDA 可用，识别将使用 NVIDIA GPU 加速。"))
            self._gpu_status.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px;")
            self._gpu_status.setToolTip("")
        elif devices > 0:
            self._gpu_status.setText(tr("⚠ 检测到 NVIDIA GPU，但 CUDA 运行库不可用，将回退 CPU。"))
            self._gpu_status.setStyleSheet(f"color: {theme.WARN}; font-size: 11px;")
            self._gpu_status.setToolTip(f"{reason}\n\n{install_hint()}")
        else:
            self._gpu_status.setText(tr("○ 未检测到可用的 NVIDIA GPU，将使用 CPU。"))
            self._gpu_status.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            self._gpu_status.setToolTip("")

    def _refresh_local_status(self) -> None:
        if local_model_available(self.config.translation.local):
            self._local_status.setText(tr("● 本地模型已下载，可用于离线翻译和云端失败兜底。"))
            self._local_status.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px;")
            self._download_local_btn.setText(tr("重新检查"))
        else:
            self._local_status.setText(tr("○ 本地模型未下载。"))
            self._local_status.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            self._download_local_btn.setText(tr("下载本地模型"))

    def _refresh_translation_status(self) -> None:
        provider = self._provider_combo.currentData() or "auto"
        has_key = bool(get_api_key()) or bool(self._key_edit.text().strip())
        local_ok = local_model_available(self.config.translation.local)
        if provider == "auto":
            text = tr("将优先使用云端；云端失败或未配置时使用本地模型。")
        elif provider == "cloud":
            text = tr("需要云端 API Key；失败时若本地模型存在会自动兜底。")
        elif provider == "local":
            text = tr("完全离线。若模型未下载，开始时会提示。")
        else:
            text = tr("只显示识别原文，不调用翻译。")
        if provider in {"auto", "cloud"} and not has_key:
            text += tr(" 当前未配置云端 Key。")
        if provider in {"auto", "local"} and not local_ok:
            text += tr(" 当前未下载本地模型。")
        self._translation_status.setText(text)

    # ------------------------------------------------------------------ key
    def _clear_saved_key(self) -> None:
        self._clear_key = True
        self._key_edit.clear()
        self._key_edit.setPlaceholderText(tr("保存后将清除已存 Key"))
        self._refresh_translation_status()

    def _commit_key(self) -> tuple[bool, str]:
        typed = self._key_edit.text().strip()
        if typed:
            ok, error = set_api_key(typed)
            if not ok:
                return False, tr(
                    "无法写入系统钥匙串：{error}\n可改用 SUBLOOM_API_KEY 环境变量。",
                    error=error,
                )
            self._clear_key = False
        elif self._clear_key:
            ok, error = set_api_key("")
            if not ok:
                return False, tr("无法清除系统钥匙串：{error}", error=error)
            self._clear_key = False
        return True, ""

    # ------------------------------------------------------------------ tasks
    def _run_task(self, title: str, fn) -> tuple[bool, str]:
        progress = QProgressDialog(title, "", 0, 0, self)
        progress.setWindowTitle("SubLoom")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setMinimumWidth(420)
        progress.show()
        outcome = {"ok": False, "message": tr("任务未完成")}
        thread = _TaskThread(fn, self)
        self._threads.append(thread)
        thread.progress.connect(progress.setLabelText)
        thread.done.connect(lambda ok, message: outcome.update(ok=ok, message=message))
        loop = QEventLoop()
        thread.done.connect(lambda *_: loop.quit())
        thread.start()
        loop.exec()
        thread.wait(1500)
        progress.close()
        return outcome["ok"], outcome["message"]

    def _download_whisper(self) -> None:
        self._download_whisper_btn.setEnabled(False)
        model = self._selected_model()
        ok, message = self._run_task(
            tr("正在下载 {model}…", model=model),
            lambda emit: download_model(model, progress=emit),
        )
        self._download_whisper_btn.setEnabled(True)
        self._refresh_asr_status()
        if not ok:
            QMessageBox.warning(self, tr("下载失败"), message)

    def _download_local(self) -> None:
        if local_model_available(self.config.translation.local):
            self._refresh_local_status()
            QMessageBox.information(self, tr("本地模型"), tr("本地翻译模型已就绪。"))
            return
        self._download_local_btn.setEnabled(False)
        ok, message = self._run_task(
            tr("正在下载本地翻译模型…"),
            lambda emit: download_local_model(emit, self.config.translation.local),
        )
        self._download_local_btn.setEnabled(True)
        self._refresh_local_status()
        self._refresh_translation_status()
        if not ok:
            QMessageBox.warning(self, tr("下载失败"), message)

    def _test_cloud(self) -> None:
        ok, error = self._commit_key()
        if not ok:
            QMessageBox.warning(self, "API Key", error)
            return
        if not get_api_key():
            QMessageBox.warning(self, tr("缺少 Key"), tr("请先填写云端翻译 API Key。"))
            return
        self._test_cloud_btn.setEnabled(False)
        self._cloud_test_status.setText(tr("正在测试…"))
        self._cloud_test_status.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        target = self._target_lang_combo.currentData() or "zh"
        cloud_config = CloudConfig(
            base_url=self._base_url_edit.text().strip(),
            model=self._cloud_model_edit.text().strip(),
            timeout_sec=self._timeout_spin.value(),
            max_retries=0,
        )

        def test(emit):
            translator = CloudTranslator(cloud_config)
            try:
                emit(tr("正在请求云端翻译…"))
                return translator.translate(
                    "Hello, this is a SubLoom subtitle test.",
                    "en",
                    target,
                    (),
                )
            finally:
                translator.close()

        ok, message = self._run_task(tr("正在测试云端翻译…"), test)
        self._test_cloud_btn.setEnabled(True)
        if ok:
            self._cloud_test_status.setText(tr("● 成功：{text}", text=message))
            self._cloud_test_status.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px;")
        else:
            self._cloud_test_status.setText(tr("✕ 失败：{error}", error=message))
            self._cloud_test_status.setStyleSheet(f"color: {theme.ERROR}; font-size: 11px;")

    # ------------------------------------------------------------------ save
    def _save(self) -> None:
        try:
            self._apply()
        except ValueError as exc:
            QMessageBox.warning(self, tr("设置无效"), str(exc))
            return
        ok, error = self._commit_key()
        if not ok:
            QMessageBox.warning(self, "API Key", error)
            return
        self.accept()

    def _apply(self) -> None:
        asr = self.config.asr
        asr.model = self._model_combo.currentData() or "auto"
        asr.device = self._device_combo.currentData() or "auto"
        asr.compute_type = self._compute_combo.currentData() or "auto"
        asr.language = self._source_lang_combo.currentData() or "auto"
        asr.silence_ms = int(self._silence_slider.value())
        asr.max_segment_sec = float(self._max_segment_slider.value())
        asr.partial_interval_ms = int(self._partial_slider.value())
        asr.use_context_prompt = self._context_check.isChecked()

        translation = self.config.translation
        translation.provider = self._provider_combo.currentData() or "auto"
        translation.target_lang = self._target_lang_combo.currentData() or "zh"
        translation.translate_partials = self._partials_check.isChecked()
        translation.cloud.base_url = self._base_url_edit.text().strip() or "https://api.deepseek.com/v1"
        translation.cloud.model = self._cloud_model_edit.text().strip() or "deepseek-chat"
        translation.cloud.timeout_sec = float(self._timeout_spin.value())
        translation.cloud.max_retries = int(self._retries_spin.value())

        ov = self.config.overlay
        ov.enabled = self._overlay_enabled.isChecked()
        ov.show_source = self._overlay_source.isChecked()
        ov.click_through = self._overlay_click.isChecked()
        ov.font_size = int(self._font_slider.value())
        ov.opacity = max(0.3, min(1.0, self._opacity_slider.value() / 100.0))
        ov.width = int(self._width_slider.value())
        ov.hold_ms = int(self._hold_slider.value())
        if getattr(self, "_reset_pos_requested", False):
            ov.x = None
            ov.y = None
        self.config.ui.language = self._ui_language_combo.currentData() or "zh"
        self.config.validate()
        if (
            self.config.asr.device == "cpu"
            and self.config.asr.compute_type in {"float16", "int8_float16"}
        ):
            raise ValueError(tr("CPU 模式不建议使用 float16 精度，请选择 int8 或自动。"))

    def _set_combo(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
