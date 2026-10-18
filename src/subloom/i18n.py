"""Tiny two-language UI localization layer.

The app is Chinese-first, so Chinese source strings double as translation keys.
This keeps call sites readable and makes missing translations fall back safely.
"""

from __future__ import annotations

from .languages import get_language, language_name

UI_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("zh", "简体中文"),
    ("en", "English"),
)

_current = "zh"


def set_language(code: str | None) -> str:
    global _current
    _current = code if code in {"zh", "en"} else "zh"
    return _current


def current_language() -> str:
    return _current


def is_english() -> bool:
    return _current == "en"


def ui_language_name(code: str | None = None) -> str:
    code = code or _current
    return dict(UI_LANGUAGES).get(code, "简体中文")


def display_language(code: str | None) -> str:
    """Language name for subtitles/cards, in the current UI language."""
    return language_name(code, "en" if _current == "en" else "zh")


def language_choice_label(code: str, *, full: bool = False) -> str:
    lang = get_language(code)
    if lang is None:
        return code
    if _current == "en":
        return lang.name_en
    return lang.name_zh


def tr(text: str, **kwargs) -> str:
    template = EN.get(text, text) if _current == "en" else text
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return template
    return template


EN: dict[str, str] = {
    # ---------------------------------------------------------------- app/chrome
    "实时语音 · 自动识别 · 即时翻译": "Real-time speech · auto-detect · instant translation",
    "让每一句话，都有字幕": "Every word, captioned",
    "就绪": "Ready",
    "聆听中": "Listening",
    "启动中": "Starting",
    "停止中": "Stopping",
    "已停止": "Stopped",
    "准备中": "Preparing",
    "发生错误": "Error",
    "已导出": "Exported",
    "设置": "Settings",
    "快速开始": "Quick start",
    "音频来源": "Audio source",
    "系统声音": "System audio",
    "麦克风": "Microphone",
    "文件": "File",
    "刷新": "Refresh",
    "翻译": "Translation",
    "目标语言": "Target language",
    "翻译方式": "Translation",
    "自动选择": "Auto",
    "云端 API": "Cloud API",
    "本地模型": "Local model",
    "仅显示原文": "Source only",
    "开始字幕": "Start subtitles",
    "停止字幕": "Stop subtitles",
    "正在停止…": "Stopping…",
    "输入电平": "Input level",
    "悬浮字幕": "Floating subtitles",
    "置顶显示，可拖动": "Always on top · draggable",
    "本地识别": "Local ASR",
    "实时字幕": "Live subtitles",
    "等待音频": "Waiting for audio",
    "导出": "Export",
    "清空": "Clear",
    "0 句": "0 lines",
    "{count} 句": "{count} lines",
    "正在准备…": "Preparing…",
    "已识别一句，继续聆听…": "Sentence captured · listening…",
    "已识别三句，继续聆听…": "3 sentences captured · listening…",
    "未检测到系统音频设备": "No system audio device found",
    "未检测到麦克风": "No microphone found",
    "默认": "Default",
    "默认扬声器": "Default speaker",
    "使用 WASAPI 回环捕获扬声器输出，无需安装虚拟声卡。": "Captures speaker output via WASAPI loopback; no virtual cable required.",
    "macOS 需安装 BlackHole 并创建多输出设备；详见 docs/macos-audio.md。": "On macOS, install BlackHole and create a Multi-Output Device; see docs/macos-audio.md.",
    "Linux 需使用 PulseAudio/PipeWire 的 monitor 输入源。": "On Linux, use a PulseAudio/PipeWire monitor source.",
    "适合现场讲话、会议发言和课堂。": "Best for live speech, meetings and classrooms.",
    "选择音频或视频文件…": "Choose an audio or video file…",
    "按原速播放并生成字幕；支持 WAV / MP3 / M4A / MP4 / MKV 等。": "Plays at real speed and generates subtitles; supports WAV, MP3, M4A, MP4, MKV and more.",
    "浏览": "Browse",
    "选择要生成字幕的媒体文件": "Choose a media file for subtitles",
    "媒体文件 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mkv *.mov *.webm);;所有文件 (*.*)": (
        "Media (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mkv *.mov *.webm);;All files (*.*)"
    ),
    "云端翻译": "Cloud translation",
    "本地翻译": "Local translation",
    "自定义字幕": "Custom subtitles",
    "仅原文": "Source only",
    "未配置翻译": "Translation not configured",
    "未配置": "Not configured",
    "翻译服务尚未就绪": "Translation service not ready",
    "现在还没有可用的翻译服务。": "No translation service is available yet.",
    "配置翻译": "Configure translation",
    "取消": "Cancel",
    "显示原文": "Show source",
    "初始化失败": "Initialization failed",
    "启动失败": "Could not start",
    "无法开始": "Cannot start",
    "请先停止": "Stop first",
    "请先停止当前字幕，再修改设置。": "Stop the current subtitles before changing settings.",
    "字幕仍在运行，确定要退出吗？": "Subtitles are still running. Quit anyway?",
    "退出 SubLoom": "Quit SubLoom",
    "清空字幕": "Clear subtitles",
    "确定清空当前字幕吗？已导出的文件不会受影响。": "Clear the current subtitles? Exported files are not affected.",
    "还没有已完成识别和翻译的句子。": "No completed sentences to export yet.",
    "导出译文 SRT": "Export translated SRT",
    "导出双语 SRT": "Export bilingual SRT",
    "导出纯文本": "Export plain text",
    "导出字幕": "Export subtitles",
    "SRT 字幕 (*.srt)": "SRT subtitles (*.srt)",
    "文本文件 (*.txt)": "Text file (*.txt)",
    "已导出：{name}": "Exported: {name}",
    "字幕已停止": "Subtitles stopped",
    "字幕窗已就绪，开始后显示字幕": "Overlay ready · start subtitles to show it",
    "首次使用：建议先在「设置 → 翻译」中配置服务": "First run: configure a translation service in Settings → Translation.",
    "系统音频": "System audio",
    "未检测到系统音频设备。\n\n": "No system audio device found.\n\n",
    "没有检测到麦克风。请连接设备后点击“刷新”。": "No microphone found. Connect one and click Refresh.",
    "请先选择要生成字幕的音视频文件。": "Choose an audio/video file first.",
    "正在翻译…": "Translating…",
    "翻译中…": "Translating…",
    "正在翻译新一句…": "Translating next line…",
    "正在更新译文…": "Updating translation…",
    "正在聆听…": "Listening…",
    "翻译失败 · 显示原文": "Translation failed · showing source",
    "原文": "Source",
    " · 原文": " · source",

    # ------------------------------------------------------------------ settings
    "调整识别、翻译与字幕显示。修改会在下次开始字幕时生效。": "Tune recognition, translation and subtitle display. Changes apply next time you start.",
    "调整识别、翻译与字幕显示；滑杆右侧数值可直接输入。修改会在下次开始字幕时生效。": (
        "Tune recognition, translation and subtitle display. The value at the right of each slider is editable. Changes apply next time you start."
    ),
    "识别": "Recognition",
    "字幕": "Subtitles",
    "SubLoom 设置向导": "SubLoom Setup",
    "欢迎使用 SubLoom 织幕": "Welcome to SubLoom",
    "三步完成设置：选择声音、配置翻译、确认识别设备。之后都可以在设置中修改。": (
        "Three quick steps: choose audio, configure translation, confirm recognition. Everything can be changed later in Settings."
    ),
    "实时识别语音，并把翻译字幕显示在置顶悬浮窗中。": (
        "Recognize speech live and show translated subtitles in an always-on-top overlay."
    ),
    "音频默认不上传，语音识别在本机完成。": "Audio stays on-device by default; speech recognition runs locally.",
    "翻译可使用云端 API，也可以下载本地模型离线运行。": (
        "Translation can use a cloud API or an optional offline local model."
    ),
    "悬浮字幕可以拖动、调字体/颜色，并停留足够时间供阅读。": (
        "The overlay is draggable, supports custom fonts/colors, and holds each line long enough to read."
    ),
    "上一步": "Back",
    "下一步": "Next",
    "完成": "Finish",
    "选择音频来源": "Choose audio source",
    "先选系统声音或麦克风；也可以稍后在主界面切换到媒体文件。": (
        "Choose system audio or a microphone; you can switch to a media file later."
    ),
    "系统声音（推荐）": "System audio (recommended)",
    "媒体文件（稍后选择）": "Media file (choose later)",
    "在主界面选择媒体文件": "Choose a media file in the main window",
    "向导只保存文件模式；具体文件在主界面选择。": (
        "The wizard only saves file mode; choose the actual file in the main window."
    ),
    "设备": "Device",
    "刷新设备": "Refresh devices",
    "适合现场讲话、会议发言和课堂；请在系统设置中确认麦克风权限。": (
        "Best for live speech, meetings and classrooms; check microphone permission in system settings."
    ),
    "Windows 上系统声音通过 WASAPI 回环捕获，无需安装虚拟声卡。": (
        "On Windows, system audio is captured through WASAPI loopback; no virtual cable is required."
    ),
    "推荐使用云端 API；没有 API 时可下载本地模型完全离线运行。": (
        "A cloud API is recommended; without one you can download the local model for fully offline use."
    ),
    "自动（有云端 Key 时优先云端）": "Auto (cloud when a key is set)",
    "本地模型约 650MB，需要单独下载；不下载也可以先使用云端。": (
        "The local model is about 650 MB and must be downloaded separately; cloud works without it."
    ),
    "Key 只保存在系统钥匙串；翻译时只发送识别后的文本。": (
        "The key is stored in the system keychain; only recognized text is sent for translation."
    ),
    "识别与性能": "Recognition & performance",
    "第一次开始字幕时会自动下载识别模型。": "The recognition model downloads automatically the first time you start.",
    "自动（GPU 用 large-v3-turbo）": "Auto (large-v3-turbo on GPU)",
    "保持“自动选择”即可；模型会保存到用户数据目录，不会进入 Git 仓库。": (
        "Keep Auto selected; models are stored in the user data directory and never enter the Git repository."
    ),
    "准备完成": "Ready",
    "确认下面的设置，之后可以随时在设置中修改。": (
        "Review these settings; you can change them later at any time."
    ),
    "点击“完成”后，选择音频来源并点击主界面的“开始字幕”。": (
        'After clicking Finish, choose an audio source and click "Start subtitles" in the main window.'
    ),
    "音频来源：{source}\n目标语言：{target}\n翻译方式：{provider}\n计算设备：{device}": (
        "Audio: {source}\nTarget language: {target}\nTranslation: {provider}\nCompute device: {device}"
    ),
    "请填写云端 API 地址和模型名。": "Enter the cloud API URL and model name.",
    "保存失败": "Save failed",
    "无法保存 API Key": "Could not save API key",
    "无法写入系统钥匙串：{error}": "Could not write to the system keychain: {error}",
    "设置向导已完成，可以开始字幕了": "Setup complete. You can start subtitles now.",
    "已跳过设置向导，可随时在设置中调整音频和翻译": (
        "Setup was skipped; you can adjust audio and translation in Settings at any time."
    ),
    "重新运行设置向导": "Run setup again",
    "自定义": "Custom",
    "术语与固定译文": "Glossary & fixed translations",
    "整句匹配时直接使用右侧译文；术语会作为云端翻译偏好，并在结果中替换同名原文。修改会在下次开始字幕时生效。": (
        "A full-sentence match uses the translated value directly. Terms are sent as cloud translation preferences and replaced in the output. Changes apply next time you start."
    ),
    "原文（整句或术语）": "Source (sentence or term)",
    "自定义译文": "Custom translation",
    "添加一行": "Add row",
    "删除选中": "Delete selected",
    "界面": "Interface",
    "关于": "About",
    "保存": "Save",
    "识别模型": "Recognition model",
    "自动（推荐：GPU 用 large-v3-turbo）": "Auto (large-v3-turbo on GPU)",
    "Large v3 Turbo · 快且准（约 1.6 GB）": "Large v3 Turbo · fast and accurate (~1.6 GB)",
    "Large v3 · 最高准确率（约 3.1 GB）": "Large v3 · highest accuracy (~3.1 GB)",
    "Distil Large v3.5 · 英文优先（约 1.5 GB）": "Distil Large v3.5 · English-first (~1.5 GB)",
    "Distil Large v3 · 英文优先（约 1.5 GB）": "Distil Large v3 · English-first (~1.5 GB)",
    "Medium · 均衡（约 1.5 GB）": "Medium · balanced (~1.5 GB)",
    "Small · 轻量（约 484 MB）": "Small · lightweight (~484 MB)",
    "Base · 更快（约 145 MB）": "Base · faster (~145 MB)",
    "Tiny · 仅测试（约 75 MB）": "Tiny · testing only (~75 MB)",
    "预下载": "Pre-download",
    "计算设备": "Compute device",
    "NVIDIA GPU (CUDA)": "NVIDIA GPU (CUDA)",
    "CPU": "CPU",
    "计算精度": "Compute type",
    "自动": "Auto",
    "float16 · GPU 推荐": "float16 · recommended for GPU",
    "int8 · CPU 推荐": "int8 · recommended for CPU",
    "float32 · 兼容性最好": "float32 · most compatible",
    "GPU": "GPU",
    "源语言": "Source language",
    "自动检测（推荐）": "Auto-detect (recommended)",
    "保持自动检测即可；锁定源语言可以避免短句误判。": "Auto-detect is usually best; locking the source language can prevent short-utterance mistakes.",
    "断句静音": "Pause to finalize",
    "越短越实时，但句子可能被切碎。": "Shorter is more real-time, but can split sentences.",
    "最长句长": "Max line length",
    "连续讲话时强制断句，避免字幕过长。": "Forces a break during continuous speech to keep subtitles short.",
    "局部刷新": "Partial refresh",
    "说话过程中更新字幕的频率。": "How often partial subtitles update while speaking.",
    "用上一句作为识别上下文（提升专有名词准确率）": "Use the previous line as ASR context (better for names)",
    "识别完全在本机完成，音频不会上传。首次使用会下载模型；下载后保存在用户数据目录，不进入 Git 仓库。": (
        "Recognition runs entirely on this device; audio is never uploaded. Models download on first use into the user data directory and never enter the Git repository."
    ),
    "本地翻译（离线兜底）": "Local translation (offline fallback)",
    "本地翻译模型尚未下载。": "Local translation model is not downloaded.",
    "本地模型已下载，可用于离线翻译和云端失败兜底。": "Local model is ready for offline translation and cloud fallback.",
    "本地模型未下载。": "Local model is not downloaded.",
    "下载本地模型": "Download local model",
    "重新检查": "Check again",
    "本地 NLLB 模型": "Local NLLB model",
    "仅识别，不翻译": "Recognize only",
    "说话过程中也翻译（更实时，云端会增加调用次数）": "Translate partials too (more real-time; more cloud calls)",
    "API 地址": "API URL",
    "模型": "Model",
    "API Key": "API Key",
    "显示": "Show",
    "清除": "Clear",
    "请求": "Request",
    "超时": "Timeout",
    "重试": "Retries",
    "测试云端翻译": "Test cloud translation",
    "需要云端 API Key；失败时若本地模型存在会自动兜底。": "Requires a cloud API key; falls back to the local model on failure.",
    "完全离线。若模型未下载，开始时会提示。": "Fully offline. You will be prompted if the model is missing.",
    "只显示识别原文，不调用翻译。": "Shows recognized source only; no translation calls.",
    "将优先使用云端；云端失败或未配置时使用本地模型。": "Prefers cloud; falls back to local when unavailable.",
    "已保存：{mask}（留空不修改）": "Saved: {mask} (leave blank to keep)",
    "sk-…（保存到系统钥匙串）": "sk-… (stored in the system keychain)",
    "保存后将清除已存 Key": "Saved key will be removed",
    "API Key 已保存到系统钥匙串。": "API key saved to the system keychain.",
    "无法写入系统钥匙串：{error}\n可改用 SUBLOOM_API_KEY 环境变量。": (
        "Could not write to the system keychain: {error}\nYou can use the SUBLOOM_API_KEY environment variable instead."
    ),
    "无法清除系统钥匙串：{error}": "Could not clear the system keychain: {error}",
    "缺少 Key": "Missing key",
    "请先填写云端翻译 API Key。": "Enter a cloud translation API key first.",
    "正在测试…": "Testing…",
    "正在请求云端翻译…": "Requesting cloud translation…",
    "正在测试云端翻译…": "Testing cloud translation…",
    "成功：{text}": "Success: {text}",
    "失败：{error}": "Failed: {error}",
    "下载失败": "Download failed",
    "本地翻译模型已就绪。": "Local translation model is ready.",
    "正在下载本地翻译模型…": "Downloading local translation model…",
    "启动字幕时显示悬浮字幕窗": "Show the floating subtitle window when starting",
    "同时显示原文": "Show source text too",
    "鼠标穿透（字幕窗不挡操作；启用后需从主界面修改设置）": "Click-through (overlay won't block clicks; change settings from the main window)",
    "正文字号": "Subtitle font size",
    "字幕文件": "Subtitle file",
    "载入外部字幕…": "Load external subtitles…",
    "载入外部字幕": "Load external subtitles",
    "按当前时间重新对齐": "Re-align to now",
    "停止外部字幕": "Stop external subtitles",
    "字幕时间偏移": "Subtitle time offset",
    "正数表示字幕延后出现（秒），负数表示提前。": (
        "Positive values delay subtitles (seconds); negative values show them earlier."
    ),
    "外部字幕": "External subtitles",
    "外部字幕：{name}": "External subtitles: {name}",
    "外部字幕已重新对齐": "External subtitles re-aligned",
    "外部字幕已停止": "External subtitles stopped",
    "外部字幕播放结束": "External subtitles finished",
    "无法载入字幕": "Could not load subtitles",
    "这个文件里没有可用的字幕时间轴。": "This file has no usable subtitle timeline.",
    "字幕文件 (*.srt *.vtt *.ass *.ssa);;所有文件 (*.*)": (
        "Subtitle files (*.srt *.vtt *.ass *.ssa);;All files (*.*)"
    ),
    "字体": "Font",
    "文字颜色": "Text color",
    "背景颜色": "Background color",
    "对齐方式": "Alignment",
    "左对齐": "Left",
    "居中": "Center",
    "右对齐": "Right",
    "文字阴影（提高复杂背景上的可读性）": "Text shadow (better readability on busy backgrounds)",
    "阴影颜色": "Shadow color",
    "恢复字幕默认样式": "Reset subtitle style",
    "点击选择颜色": "Click to choose a color",
    "字幕预览：每一句话，都值得被看见。": "Subtitle preview: every sentence deserves to be seen.",
    "背景不透明度": "Background opacity",
    "字幕窗宽度": "Overlay width",
    "最短停留": "Minimum hold",
    "可直接输入数字，按回车或失焦生效": (
        "Type a number directly; press Enter or click away to apply."
    ),
    "保证一句译文至少显示这么久，避免还没看完就被下一句替换。": (
        "Keep each translation visible at least this long so the next line cannot replace it before you finish reading."
    ),
    "恢复默认位置": "Reset position",
    "位置": "Position",
    "提示：可以直接拖动悬浮字幕窗；右键可快速调整字号或隐藏。": "Tip: drag the overlay directly; right-click to adjust size or hide it.",
    "跨平台实时语音翻译字幕。识别在本机完成，翻译可选择云端或本地模型；音频默认不离开设备。": (
        "Cross-platform real-time speech translation captions. Recognition stays on-device; translation can use cloud or local models; audio never leaves the device."
    ),
    "版本 {version}\n代码许可：MIT\n识别模型：faster-whisper（MIT）\n本地翻译模型：NLLB-200（CC BY-NC 4.0，模型单独下载）\n云端翻译：由你配置的服务商提供，费用与隐私政策以其条款为准。": (
        "Version {version}\nCode license: MIT\nASR model: faster-whisper (MIT)\nLocal translation model: NLLB-200 (CC BY-NC 4.0, downloaded separately)\nCloud translation: provided by your chosen vendor; fees and privacy terms are theirs."
    ),
    "项目主页 / 问题反馈": "Project home / issues",
    "界面语言": "Interface language",
    "选择 SubLoom 的显示语言。": "Choose the display language for SubLoom.",
    "切换后需要重启 SubLoom 才会生效。": "Restart SubLoom for the change to take effect.",
    "界面语言已保存": "Interface language saved",
    "重启 SubLoom 后，新的界面语言会生效。": "The new interface language will apply after restarting SubLoom.",
    "● {model} 已下载，启动时直接加载。": "● {model} is downloaded and will load at startup.",
    "○ 尚未下载，首次开始时会自动下载（也可点“预下载”）。": "○ Not downloaded yet; it will download on first start (or use Pre-download).",
    "● CUDA 可用，识别将使用 NVIDIA GPU 加速。": "● CUDA available; recognition will use the NVIDIA GPU.",
    "⚠ 检测到 NVIDIA GPU，但 CUDA 运行库不可用，将回退 CPU。": "⚠ NVIDIA GPU detected, but the CUDA runtime is unavailable; falling back to CPU.",
    "○ 未检测到可用的 NVIDIA GPU，将使用 CPU。": "○ No usable NVIDIA GPU detected; using CPU.",
    "NLLB-200 distilled 600M · {size}。模型许可为 {license}，请根据你的使用场景确认是否可用。模型不随仓库分发。": (
        "NLLB-200 distilled 600M · {size}. Model license: {license}; confirm it fits your use case. Models are not bundled with the repository."
    ),
    "CPU 模式不建议使用 float16 精度，请选择 int8 或自动。": "CPU mode does not support float16; choose int8 or Auto.",

    # ------------------------------------------------------------------- overlay
    "SubLoom 字幕": "SubLoom subtitles",
    "字幕设置…": "Subtitle settings…",
    "增大字号": "Larger text",
    "减小字号": "Smaller text",
    "隐藏字幕窗": "Hide overlay",

    # ---------------------------------------------------------------- empty/card
    "声音会在这里变成字幕": "Speech becomes subtitles here",
    "选择系统声音、麦克风或一个媒体文件，点击「开始字幕」。\n识别在本机完成，翻译可走云端或本地模型。": (
        "Choose system audio, a microphone or a media file, then click Start subtitles.\nRecognition runs on-device; translation can use cloud or local models."
    ),

    # ------------------------------------------------------------------ pipeline
    "正在准备识别模型…": "Preparing recognition model…",
    "正在启动音频…": "Starting audio…",
    "正在准备本地翻译模型…": "Preparing local translation model…",
    "正在完成最后一句翻译…": "Finishing the last translation…",
    "识别速度暂时落后，已丢弃少量旧音频": "Recognition is behind; dropped a little old audio",
    "音频分段失败：{error}": "Audio segmentation failed: {error}",
    "这一句识别失败：{error}": "Could not recognize this sentence: {error}",
    "最后一句识别失败：{error}": "Could not recognize the last sentence: {error}",
    "正在加载 {model}（{device} / {compute}）…": "Loading {model} ({device} / {compute})…",
    "正在下载识别模型 {model}（{size}）…": "Downloading recognition model {model} ({size})…",
    "正在加载本地翻译模型（{device} / {compute}）…": "Loading local translation model ({device} / {compute})…",
    "正在下载本地翻译模型（{size}）…": "Downloading local translation model ({size})…",
    "GPU 运行库加载失败，已自动切换 CPU。": "CUDA runtime failed to load; switched to CPU.",
    "GPU 运行库不可用，已自动切换 CPU。": "CUDA runtime unavailable; switched to CPU.",

    # ---------------------------------------------------------- translation svc
    "仅显示原文，不翻译": "Source only; translation disabled",
    "未配置云端 API Key": "Cloud API key not configured",
    "云端翻译 · {model}": "Cloud translation · {model}",
    "本地翻译模型未下载（{size}，{license}）": "Local translation model not downloaded ({size}, {license})",
    "本地翻译 · NLLB-200 600M": "Local translation · NLLB-200 600M",
    "未配置翻译：请填写云端 API Key，或下载本地模型": "Translation not configured: enter a cloud API key or download the local model",
    "没有可用的翻译服务。\n请配置云端 API Key，或在设置中下载本地翻译模型。": (
        "No translation service is available.\nConfigure a cloud API key or download the local translation model in Settings."
    ),
    "云端失败，已切换本地翻译：{error}": "Cloud failed; switched to local translation: {error}",
    "云端 API 地址或模型未填写": "Cloud API URL or model is empty",
    "未配置云端翻译 API Key。": "Cloud translation API key is not configured.",
    "云端翻译返回了空结果。": "Cloud translation returned no result.",
    "云端翻译返回了空文本。": "Cloud translation returned empty text.",
    "云端翻译暂时不可用（{error}）": "Cloud translation is temporarily unavailable ({error})",
    "云端翻译失败（HTTP {status}）：{detail}": "Cloud translation failed (HTTP {status}): {detail}",
    "云端翻译超时：{error}": "Cloud translation timed out: {error}",
    "无法连接云端翻译服务：{error}": "Could not reach the cloud translation service: {error}",
    "云端翻译失败：{error}": "Cloud translation failed: {error}",
    "本地 NLLB 不支持该语言：{source} → {target}": "Local NLLB does not support this language pair: {source} → {target}",
    "本地翻译模型尚未下载。\n请在设置中下载 NLLB 模型，或配置云端翻译 API。": (
        "The local translation model is not downloaded.\nDownload NLLB in Settings or configure a cloud API."
    ),
    "模型下载完成，但文件不完整，请重试。": "Download finished but files are incomplete; please retry.",
    "本地翻译模型下载失败：{error}": "Local translation model download failed: {error}",
    "本地翻译没有返回结果。": "Local translation returned no result.",
    "本地翻译返回了空文本。": "Local translation returned empty text.",
    "本地翻译失败：{error}": "Local translation failed: {error}",
    "本地翻译解码失败：{error}": "Local translation decode failed: {error}",

    # ------------------------------------------------------------------- labels
    "FINAL": "FINAL",
    "LIVE": "LIVE",
    "约 650 MB": "~650 MB",
    "CC BY-NC 4.0（仅限非商业用途）": "CC BY-NC 4.0 (non-commercial only)",
    "无法加载本地翻译模型：{error}": "Could not load the local translation model: {error}",
    "NLLB-200 600M · 已下载（{size}）": "NLLB-200 600M · downloaded ({size})",
    "NLLB-200 600M · 未下载（{size}，{license}）": "NLLB-200 600M · not downloaded ({size}, {license})",
    " 当前未配置云端 Key。": " No cloud key configured.",
    " 当前未下载本地模型。": " Local model not downloaded.",
    " 秒": " s",
    " 次": " attempts",
    "秒": "s",
    "SubLoom 设置": "SubLoom Settings",
    "实时语音翻译字幕": "real-time speech translation subtitles",
    "本地识别 · {model}": "Local ASR · {model}",
    "本地识别 · {model} · {device}": "Local ASR · {model} · {device}",
    "NVIDIA CUDA 加速已启用": "NVIDIA CUDA acceleration enabled",
    "CPU · CUDA 缺失": "CPU · CUDA missing",
    "未使用 GPU 加速": "GPU acceleration not in use",
    "{language} · {probability}%": "{language} · {probability}%",
    "{model} · 已下载": "{model} · downloaded",
    "{model} · 首次使用将自动下载（{size}）": "{model} · downloads automatically on first use ({size})",
    "模型下载完成但文件不完整：{path}": "Model download finished but files are incomplete: {path}",
    "配置为使用 NVIDIA GPU，但 CUDA 后端当前不可用。\n原因：{reason}\n\n{hint}\n\n也可以在设置中把计算设备改为“自动”或 CPU。": (
        "Configured to use the NVIDIA GPU, but the CUDA backend is unavailable.\n"
        "Reason: {reason}\n\n{hint}\n\n"
        "You can also set the compute device to Auto or CPU in Settings."
    ),
    "输入设备 {index}": "Input device {index}",
    "没有检测到系统音频设备。\n\n": "No system audio device found.\n\n",
    "任务未完成": "Task did not finish",
    "正在下载 {model}…": "Downloading {model}…",
    "导出失败": "Export failed",
    "设置无效": "Invalid settings",
    "翻译失败": "Translation failed",
    "● 本地模型已下载，可用于离线翻译和云端失败兜底。": "● Local model is ready for offline translation and cloud fallback.",
    "○ 本地模型未下载。": "○ Local model is not downloaded.",
    "● 成功：{text}": "● Success: {text}",
    "✕ 失败：{error}": "✕ Failed: {error}",
    "{message}\n\n你可以先配置云端 API 或下载本地模型，也可以先只显示识别原文。": (
        "{message}\n\nConfigure a cloud API or download the local model, or start with source-only subtitles."
    ),
    "1. 选择音频来源：系统声音、麦克风或一个媒体文件。\n\n2. 选择目标语言和翻译方式。推荐先配置云端 API；没有 API 时可下载本地 NLLB 模型。\n\n3. 点击「开始字幕」。识别在本机完成，悬浮字幕窗会置顶显示翻译。\n\n4. 结束后点击「导出」保存 SRT 或纯文本。\n\n提示：首次使用需要下载识别模型；模型保存在用户数据目录，不会进入 Git 仓库。": (
        "1. Choose system audio, a microphone or a media file.\n\n"
        "2. Pick a target language and translation mode. A cloud API is recommended; without one you can download the local NLLB model.\n\n"
        "3. Click Start subtitles. Recognition stays on-device and the overlay stays on top.\n\n"
        "4. When finished, click Export to save SRT or plain text.\n\n"
        "Tip: the recognition model downloads on first use into the user data directory and never enters the Git repository."
    ),
}


# A few strings are composed in the UI; keep their pieces here so English looks
# natural instead of mixing Chinese fragments.
EN.update(
    {
        "当前未配置云端 Key。": " No cloud key configured.",
        " 当前未下载本地模型。": " Local model not downloaded.",
        "将优先使用云端；云端失败或未配置时使用本地模型。": "Prefers cloud; falls back to local when unavailable.",
        "需要云端 API Key；失败时若本地模型存在会自动兜底。": "Requires a cloud API key; falls back to local when available.",
        "完全离线。若模型未下载，开始时会提示。": "Fully offline. You will be prompted if the model is missing.",
        "只显示识别原文，不调用翻译。": "Shows recognized source only; no translation calls.",
    }
)
