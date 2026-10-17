# 架构说明

## 总览

SubLoom 是一个单进程 PySide6 桌面应用。音频捕获、VAD、识别在后台线程；翻译在独立线程池中执行；UI 通过 Qt signal 接收事件。这样做的好处是：模型加载和网络请求不会阻塞窗口，且悬浮字幕可以独立于主窗口刷新。

```text
AudioSource (Windows WASAPI loopback / PortAudio input / PyAV file)
    │  float32 mono 16k, ~20–200 ms blocks
    ▼
queue.Queue (bounded)
    ▼
VadSegmenter (WebRTC VAD, 20 ms frames)
    │ VadEvent(partial)              │ VadEvent(final)
    ▼                                ▼
WhisperASR.transcribe()          WhisperASR.transcribe()
beam=1, no context               beam=3, context prompt
    │                                │
    └──────────────┬─────────────────┘
                   ▼
            LanguageTracker
                   ▼
         CaptionSegment (revision)
             │            │
             ▼            ▼
      UI / overlay   TranslationService
                     ├─ cloud (OpenAI-compatible)
                     └─ local NLLB fallback
```

## 关键设计

### 1. 分段而不是“逐帧识别”

Whisper 不是流式模型。直接对每 0.5 秒音频调用一次会丢失上下文、增加幻觉，而且成本很高。SubLoom 用 WebRTC VAD 检测语音边界：

- 连续 3 个 20ms 帧为语音 → 开始一段。
- 说话过程中每约 650ms 用当前缓冲区做一次 `partial` 识别（`beam_size=1`）。
- 静音约 450ms → 用完整句子做 `final` 识别（`beam_size=3`）。
- 最长 9 秒强制断句，防止字幕过长、延迟无限增长。

`preroll` 保留约 240ms 语音前缓冲，避免吞掉第一个音节。

### 2. 语言锁定

Whisper 对 1–2 秒的短音频可能给出不同的语言判断。`LanguageTracker` 维护加权投票：

- 手动指定源语言时始终使用手动值。
- 自动模式需要两个一致的 `final` 结果，或约 3 秒的一致语音，才锁定语言。
- 锁定后把语言传给 Whisper，既提高速度，也避免同一场会议里语言标签闪烁。

### 3. 字幕修订号

每个句子有稳定的 `id` 和递增的 `revision`：

- 新的 `partial` 结果增加 revision，旧翻译返回时会被丢弃。
- 翻译完成写回同一个 revision。
- `final` 是新 revision，替换此前的局部字幕。
- UI 的 `TranscriptStore.upsert()` 负责合并，避免旧翻译覆盖新文本。

### 4. 翻译回退

`TranslationService` 的选择顺序：

1. 配置为 `off` → 不翻译。
2. 配置为 `cloud` → 云端；失败且本地模型已下载 → 本地，并标记 `fallback_used`。
3. 配置为 `local` → 本地。
4. `auto` → 有 Key 选云端，否则本地；都没有则启动前提示配置。

云端翻译使用最近 3 条定稿字幕作为上下文（只作为参考），提高代词和术语一致性。NLLB 是句级模型，不使用上下文。

### 5. 线程与背压

- 音频回调只做重采样和入队，绝不阻塞。
- 音频队列有上限（80 个 block）。识别落后时丢弃最旧音频，并在 UI 提示；不会让内存无限增长。
- 局部翻译和定稿翻译使用两个单线程执行器：
  - 定稿任务串行，保证顺序和上下文。
  - 局部任务串行且有节流；如果 ASR 已经产生更新的 revision，旧任务的返回结果会被丢弃。
- 停止时先停音频源，flush VAD，再等待最后一句定稿翻译（最多由网络超时决定）。

### 6. 模型管理

- 识别模型：`faster-whisper` + CTranslate2，`large-v3-turbo`（GPU）/ `small`（CPU）。
- 翻译模型：NLLB-200 distilled 600M INT8，CTranslate2。
- 路径：`platformdirs.user_data_dir("SubLoom")/models`，可用环境变量覆盖。
- 首次使用自动下载；下载失败会显示错误，不会把半截模型标记为可用。
- 模型永远不进入 Git 仓库或应用安装包。

### 7. CUDA 运行库

`ctranslate2` 的 PyPI wheel 不带 cuBLAS/cuDNN。Windows 上：

- 可选安装 `nvidia-cublas-cu12`、`nvidia-cudnn-cu12`。
- `cuda_runtime.py` 在导入 CTranslate2 前把 `site-packages/nvidia/*/bin` 加入 DLL 搜索路径，并显式 `WinDLL` 预加载。
- 预加载是必须的：只调用 `os.add_dll_directory()` 时，CTranslate2 懒加载 `cublas64_12.dll` 仍可能失败。
- 不可用时自动回退 CPU，并在设置界面显示原因。

## 数据与隐私

- 音频只在内存中处理；不写临时文件（文件模式也只读源文件）。
- 云端翻译发送：识别文本、源/目标语言、最近 3 条上下文。
- 不发送音频、设备名、用户名。
- API Key 优先读 `SUBLOOM_API_KEY`，否则读系统钥匙串。
- 日志可能包含错误信息和片段文本；默认写入用户数据目录，最多 3 个 2MB 文件。

## 已知架构限制

- 没有云端流式 ASR；本地 ASR 是唯一识别后端。
- 没有说话人分离；多人重叠时 VAD 可能合并。
- VAD 对音乐、掌声等非语音的抑制有限；Whisper 可能会产生幻觉字幕。
- 悬浮窗使用 Qt 置顶窗口，无法覆盖独占全屏游戏。
- macOS 系统声音依赖虚拟声卡，尚未接入 ScreenCaptureKit。
- 单进程、单会话；同时开两个实例会争用音频设备和模型显存。
