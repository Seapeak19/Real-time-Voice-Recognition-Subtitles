# 第三方组件与模型许可

SubLoom 的源码使用 MIT 许可。以下组件和模型**不包含在 Git 仓库中**，由用户在运行时安装或下载，各自遵循其原始许可。

## 模型

| 模型 | 用途 | 许可 | 备注 |
| --- | --- | --- | --- |
| OpenAI Whisper / faster-whisper 转换权重 | 本地语音识别 | MIT | 通过 faster-whisper 下载 |
| NLLB-200 distilled 600M | 本地翻译兜底 | **CC BY-NC 4.0** | **仅限非商业用途**；模型单独下载 |

NLLB 的非商业限制来自 Meta 的模型许可，不是 SubLoom 代码的限制。商业使用请：

1. 只使用云端翻译；或
2. 替换 `src/subloom/translate/nllb.py` 为许可兼容的本地翻译后端。

## 主要软件依赖

| 组件 | 许可 |
| --- | --- |
| faster-whisper | MIT |
| CTranslate2 | MIT |
| PySide6 / Qt | LGPLv3（动态链接） |
| NumPy | BSD-3-Clause |
| httpx | BSD-3-Clause |
| PyAV / FFmpeg | BSD-3-Clause / LGPL 或 GPL（取决于 FFmpeg 构建） |
| sounddevice / PortAudio | MIT |
| SoundCard | BSD-3-Clause |
| WebRTC VAD | MIT |
| python-soxr / libsoxr | LGPL-2.1-or-later |
| SentencePiece | Apache-2.0 |
| Hugging Face Hub | Apache-2.0 |
| keyring | MIT |
| platformdirs | MIT |

打包分发时请同时保留各依赖的许可文本。PySide6 采用 LGPLv3，分发动态链接的 Qt 库时需要满足 LGPL 的相应要求。

## 云端服务

云端翻译由用户自行配置的服务商提供。SubLoom 不附带任何 API Key，也不对服务商的可用性、价格、数据处理方式或输出准确性作出承诺。请阅读你选择的服务商条款。
