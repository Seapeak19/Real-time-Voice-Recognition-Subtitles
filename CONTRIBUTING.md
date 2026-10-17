# 贡献指南

感谢你愿意改进 SubLoom。

## 开发环境

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Windows 上如果需要 GPU：

```powershell
python -m pip install -e ".[dev,gpu]"
python scripts/check_gpu.py
```

## 提交前检查

```bash
python -m pytest -q
python -m ruff check src tests scripts
python -m subloom --smoke-test
```

测试不应下载模型，也不应需要 API Key。需要真实模型的实验请放在 `scripts/` 或手动验证，不要加进默认 CI。

## 代码约定

- Python 3.10+，类型标注尽量完整。
- 面向用户的错误使用 `SubLoomError` 子类，并在 UI 中给出可操作的下一步。
- 音频回调、翻译线程不得直接操作 Qt 控件；通过 `PipelineCallbacks` / signal 回到 UI 线程。
- 不要把模型、录音、API Key、日志或构建产物提交到仓库。
- 新增翻译后端时实现 `translate/base.py` 的接口，并在 `TranslationService` 中接入回退与就绪检查。
- 新增语言时修改 `languages.py`，确认 Whisper code 和 NLLB code 都正确。

## 模型与测试音频

- 模型目录由 `SUBLOOM_MODEL_DIR` 指定；本地测试建议放在仓库外的临时目录。
- `samples/` 已在 `.gitignore` 中，不要提交受版权保护的音视频。
- 可以用系统 TTS 生成测试语音，或使用明确允许再分发的短片段。

## Pull Request

请说明：

- 改动解决了什么问题
- 在哪些平台/设备上测试过
- 是否影响延迟、模型体积或许可
- 用户可见行为的变化

小而聚焦的 PR 更容易 review。涉及 UI 的改动请附截图；涉及音频的改动请说明测试设备和输入来源。

## 报告问题

请附上操作系统、Python 版本、GPU 信息、日志最后 50 行和复现步骤。不要粘贴完整 API Key。安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。
