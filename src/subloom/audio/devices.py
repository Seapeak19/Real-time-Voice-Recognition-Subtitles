"""Best-effort enumeration of microphone and system-audio devices."""

from __future__ import annotations

import logging
import sys

from ..i18n import tr
from ..models import AudioDevice

log = logging.getLogger(__name__)


def list_microphones() -> list[AudioDevice]:
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else -1
        result: list[AudioDevice] = []
        for index, info in enumerate(devices):
            if int(info.get("max_input_channels", 0)) <= 0:
                continue
            name = str(info.get("name", tr("输入设备 {index}", index=index)))
            api = ""
            try:
                api = sd.query_hostapis(info["hostapi"])["name"]
            except Exception:
                pass
            label = f"{name}  [{api}]" if api else name
            result.append(AudioDevice(str(index), label, "microphone", index == default_in))
        return result
    except Exception as exc:
        log.warning("Could not enumerate microphones: %s", exc)
        return []


def list_system_devices() -> list[AudioDevice]:
    """List devices that can carry system playback audio.

    Windows uses WASAPI loopback through ``soundcard``.  macOS has no
    built-in loopback API exposed by PortAudio; users route output through a
    virtual device such as BlackHole, which then appears as an input here.
    """
    if sys.platform == "win32":
        try:
            import soundcard as sc

            result = [AudioDevice("", tr("默认扬声器"), "system", True)]
            seen = {""}
            for mic in sc.all_microphones(include_loopback=True):
                if not getattr(mic, "isloopback", False):
                    continue
                name = str(mic.name)
                if name in seen:
                    continue
                seen.add(name)
                result.append(AudioDevice(name, name, "system", False))
            return result
        except Exception as exc:
            log.warning("Could not enumerate loopback devices: %s", exc)
            return [AudioDevice("", tr("默认扬声器"), "system", True)]

    result = []
    for device in list_microphones():
        lower = device.name.lower()
        if any(token in lower for token in ("blackhole", "soundflower", "loopback", "monitor")):
            result.append(AudioDevice(device.id, device.name, "system", device.is_default))
    return result


def resolve_input_device(value: str | int | None) -> int | str | None:
    """Turn a stored device string into something sounddevice understands."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        import sounddevice as sd

        matches = [
            index
            for index, info in enumerate(sd.query_devices())
            if text.lower() in str(info.get("name", "")).lower()
            and int(info.get("max_input_channels", 0)) > 0
        ]
        if matches:
            return matches[0]
    except Exception:
        pass
    return text


def system_audio_hint() -> str:
    if sys.platform == "win32":
        return tr("使用 WASAPI 回环捕获扬声器输出，无需安装虚拟声卡。")
    if sys.platform == "darwin":
        return tr("macOS 需安装 BlackHole 并创建多输出设备；详见 docs/macos-audio.md。")
    return tr("Linux 需使用 PulseAudio/PipeWire 的 monitor 输入源。")
