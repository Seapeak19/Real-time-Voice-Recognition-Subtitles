# 故障排查

日志位置：

- Windows：`%LOCALAPPDATA%\SubLoom\logs\subloom.log`
- macOS：`~/Library/Application Support/SubLoom/logs/subloom.log`

启动时加 `--debug` 可以输出更详细的日志。

## 识别 / 模型

### `cublas64_12.dll is not found` 或 `cudnn64_9.dll is not found`

CTranslate2 的 PyPI wheel 不包含 CUDA 运行库。安装 GPU 额外依赖：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gpu]"
```

然后完全重启 SubLoom。确认状态：

```powershell
python scripts/check_gpu.py
```

设置 → 识别 → GPU 应显示“CUDA 可用”。如果仍不可用，把“计算设备”改为“自动”或“CPU”，至少可以先跑起来。

### 首次开始一直停在“正在准备识别模型…”

正在下载模型（约 1.6GB 或 484MB），取决于网络。可以看日志，或提前运行：

```bash
python scripts/download_models.py --whisper large-v3-turbo
```

下载失败后重试即可；已下载的分片会复用。

### 识别很慢 / 字幕持续落后

- 设置 → 识别：确认设备是 GPU，精度是 `float16`。
- CPU 上不要用 `large-v3`；换 `small` 或 `base`。
- 关闭其他占用显存的程序。
- 日志里出现“识别速度暂时落后，已丢弃少量旧音频”说明队列溢出；换更小模型或提高 `partial_interval_ms`。

### 没有字幕，但电平在动

- VAD 可能把声音当成噪声。设置 → 识别 → 断句静音调低，或把源语言从“自动”改成实际语言。
- 麦克风增益太低：提高系统输入音量，或在配置文件里调 `audio.input_gain_db`。
- Whisper 对音乐/掌声可能输出空文本，这是预期行为。

### 中英文混合时语言标签乱跳

自动检测在混合语言场景下天然不稳定。设置 → 识别 → 源语言锁定为主要的语言。

## 翻译

### `401` / `invalid api key`

- 检查 API 地址是否包含正确的 `/v1` 路径。
- 检查模型名是否是服务商支持的名称。
- 在设置里点“测试云端翻译”，不要只靠猜。
- 环境变量 `SUBLOOM_API_KEY` 的优先级高于钥匙串；如果设了旧值，会覆盖设置。

### 云端超时，字幕只有原文

- 增大设置里的请求超时（默认 10 秒）。
- 检查网络/代理；某些服务商在特定地区不可直连。
- 下载本地 NLLB 模型后，云端失败会自动兜底。
- 只显示原文说明“翻译方式”是“仅原文”，或当前没有可用翻译服务。

### 本地模型下载后仍提示未下载

确认模型目录里有 `model.bin` 和 `sentencepiece.bpe.model`。默认目录：

- Windows：`%LOCALAPPDATA%\SubLoom\models\translation\nllb-200-distilled-600M-ct2-int8`
- macOS：`~/Library/Application Support/SubLoom/models/translation/nllb-200-distilled-600M-ct2-int8`

路径含中文时，SubLoom 已改用序列化 proto 加载 SentencePiece，不应再因路径失败。

### 本地翻译质量差

NLLB 600M 是“能离线跑”的折中，不是 GPT 级翻译。专有名词、口语、长句都可能出错。优先使用云端；商业场景请确认 NLLB 的 CC BY-NC 许可。

## 音频

### Windows 只有“默认扬声器”，没有具体设备

点“刷新”。如果仍然没有，确认有正在使用的播放设备；某些虚拟声卡（SteelSeries Sonar、Voicemeeter）需要选择对应的回环设备，而不是默认扬声器。

### 捕获到的是麦克风而不是系统声音

在“系统声音”页选择具体的扬声器回环设备。SteelSeries Sonar 等软件会把不同通道暴露成多个回环设备，逐个试。

### macOS 没有系统声音

见 [macos-audio.md](macos-audio.md)。这是 0.1 的已知限制。

### 文件模式没有声音/无法解码

- 确认文件有音频轨道。
- 支持 WAV/MP3/M4A/AAC/FLAC/OGG/OPUS/MP4/MKV/MOV/WebM；文件解码使用 PyAV，不依赖 ffmpeg 命令。
- 文件模式默认按原速播放；长文件需要等待与时长相当的时间。

## 界面 / 系统

### 悬浮字幕窗不见了

主界面左侧“悬浮字幕”开关是否关闭；或右键菜单里点了“隐藏”。重新打开开关即可。若窗口跑到屏幕外，设置 → 字幕 → 恢复默认位置。

### 鼠标穿透后无法操作悬浮窗

这是设计行为。从主界面关闭“悬浮字幕”开关，或重新打开设置修改。

### 钥匙串写入失败

某些精简版 Windows/无桌面密钥环的 Linux 环境会失败。使用环境变量：

```powershell
$env:SUBLOOM_API_KEY = "sk-..."
subloom
```

### 应用启动报 Qt / 平台插件错误

确认通过虚拟环境启动，且 PySide6 安装完整：

```bash
python -m pip install --force-reinstall "PySide6-Essentials>=6.7,<7"
```

### 卸载后模型还在

模型在用户数据目录，卸载程序不会删除。手动删除 `SubLoom` 数据目录即可。

## 提交问题

请附上：

- 操作系统、Python 版本、是否 NVIDIA GPU
- `python scripts/check_gpu.py` 输出
- 日志最后 50 行（注意可能包含字幕片段）
- 复现步骤

不要粘贴完整的 API Key。
