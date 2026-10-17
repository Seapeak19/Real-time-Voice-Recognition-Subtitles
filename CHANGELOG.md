# Changelog

## 0.1.0 — 2026-10-17

首个可运行版本。

### 新增

- Windows 系统声音回环、麦克风、本地音视频文件三种输入。
- faster-whisper 本地识别，自动语言检测与语言锁定。
- `large-v3-turbo` / `small` 等模型选择，GPU 自动检测与 CPU 回退。
- OpenAI Chat Completions 兼容的云端翻译，支持上下文。
- 本地 NLLB-200 distilled 600M 翻译，云端失败自动兜底。
- 50 种目标语言。
- 置顶透明悬浮字幕窗：拖动、字号、透明度、鼠标穿透、右键菜单。
- 主界面实时字幕卡片、语种/引擎状态、输入电平。
- 译文 SRT、双语 SRT、纯文本导出。
- API Key 存入系统钥匙串，支持 `SUBLOOM_API_KEY`。
- 模型与代码分离，模型首次使用时下载到用户数据目录。
- PyInstaller 配方、Windows/macOS CI、Release 工作流。
- 中文 README、架构文档、macOS 音频配置、故障排查。

### 已知限制

- macOS 系统声音依赖 BlackHole，尚未使用 ScreenCaptureKit。
- 没有云端流式 ASR。
- 本地 NLLB 模型为 CC BY-NC 4.0，仅限非商业用途。
- 无说话人分离、OBS 源、术语表。
- 安装包未签名。
