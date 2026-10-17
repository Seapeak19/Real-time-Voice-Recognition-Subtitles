# macOS 系统声音配置

macOS 没有向普通应用开放“直接录制扬声器输出”的 PortAudio 接口。SubLoom 0.1 使用 **BlackHole** 虚拟声卡捕获系统声音；麦克风和文件模式不需要这一步。

## 1. 安装 BlackHole

推荐 2 声道版本：

```bash
brew install blackhole-2ch
```

没有 Homebrew 时，可从 [BlackHole 官网](https://existential.audio/blackhole/) 下载安装包并重启。

安装后，在“系统设置 → 隐私与安全性 → 麦克风”中允许 SubLoom 使用音频输入。

## 2. 创建多输出设备

如果直接把系统输出切到 BlackHole，你会听不到声音。需要同时输出到扬声器和 BlackHole：

1. 打开 **音频 MIDI 设置**（Audio MIDI Setup）。
2. 左下角 `+` → **创建多输出设备**（Create Multi-Output Device）。
3. 勾选你的扬声器/耳机，以及 **BlackHole 2ch**。
4. 把多输出设备设为系统输出（系统设置 → 声音 → 输出）。
5. 建议把主设备设为扬声器，这样音量键仍然有效。

## 3. 在 SubLoom 中选择

1. 音频来源选择 **系统声音**。
2. 刷新设备列表。
3. 选择 **BlackHole 2ch**。

此时 SubLoom 能听到系统播放的声音，同时你仍然能从扬声器听到。

## 4. 验证

播放一段有人说话的视频，开始字幕后观察输入电平：

- 电平有变化、出现字幕 → 成功。
- 电平一直为 -60dB → 检查系统输出是否是多输出设备，以及 BlackHole 是否被勾选。
- 有字幕但延迟很大 → 尝试更小的识别模型或关闭其他占用 GPU/CPU 的应用。

## 常见问题

**Q: 为什么不能像 Windows 一样直接选“默认扬声器”？**

A: macOS 的 Core Audio 不提供跨进程回环录制；Windows 的 WASAPI loopback 是系统 API。原生方案需要 ScreenCaptureKit（macOS 13+），已列入路线图。

**Q: 能否只用 BlackHole，不要扬声器？**

A: 可以，但你会听不到原声。会议场景通常需要多输出设备。

**Q: 蓝牙耳机可以用吗？**

A: 可以，但蓝牙本身有 100–300ms 延迟；多输出设备可能进一步增加延迟。字幕延迟会受影响。

**Q: 安装 BlackHole 后需要重启吗？**

A: 通常不需要，但音频 MIDI 设置和部分应用需要重新打开。若 SubLoom 设备列表没有出现，点“刷新”。

**Q: 这会被识别为屏幕录制吗？**

A: BlackHole 是音频驱动，不需要屏幕录制权限；SubLoom 只申请麦克风权限。未来接入 ScreenCaptureKit 时会申请屏幕录制权限。
