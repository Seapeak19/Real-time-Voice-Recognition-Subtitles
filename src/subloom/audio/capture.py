"""Audio sources that emit 16 kHz mono float32 blocks."""

from __future__ import annotations

import logging
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

import numpy as np

from ..models import AudioError
from .devices import resolve_input_device, system_audio_hint
from .resample import StreamResampler

log = logging.getLogger(__name__)

AudioCallback = Callable[[np.ndarray], None]
ErrorCallback = Callable[[str], None]
FinishedCallback = Callable[[], None]
SAMPLE_RATE = 16_000


class AudioSource(ABC):
    kind = "audio"

    def __init__(
        self,
        on_audio: AudioCallback,
        on_error: ErrorCallback | None = None,
        on_finished: FinishedCallback | None = None,
        gain_db: float = 0.0,
    ) -> None:
        self.on_audio = on_audio
        self.on_error = on_error or (lambda message: None)
        self.on_finished = on_finished or (lambda: None)
        self.gain_db = float(gain_db)
        self._running = False
        self._error_reported = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def describe(self) -> str:
        return self.kind

    def _emit(self, samples: np.ndarray) -> None:
        if not self._running or samples.size == 0:
            return
        try:
            self.on_audio(samples)
        except Exception:
            log.exception("Audio callback failed")

    def _fail(self, message: str) -> None:
        with self._lock:
            if self._error_reported:
                return
            self._error_reported = True
            self._running = False
        log.error("Audio source error: %s", message)
        try:
            self.on_error(message)
        except Exception:
            log.exception("Error callback failed")

    def _finish(self) -> None:
        try:
            self.on_finished()
        except Exception:
            log.exception("Finished callback failed")


class _InputStreamSource(AudioSource):
    """Shared PortAudio input implementation (microphone or virtual device)."""

    kind = "microphone"

    def __init__(
        self,
        on_audio: AudioCallback,
        device: str | int | None = None,
        on_error: ErrorCallback | None = None,
        on_finished: FinishedCallback | None = None,
        gain_db: float = 0.0,
    ) -> None:
        super().__init__(on_audio, on_error, on_finished, gain_db)
        self.device = device
        self._stream = None
        self._resampler: StreamResampler | None = None
        self._device_label = "默认输入"

    def _resolve(self):
        import sounddevice as sd

        device = resolve_input_device(self.device)
        try:
            info = sd.query_devices(device, "input")
        except Exception as exc:
            raise AudioError(f"无法打开输入设备：{exc}") from exc
        channels = int(info.get("max_input_channels", 1))
        if channels <= 0:
            raise AudioError("所选设备没有输入通道。")
        rate = int(round(float(info.get("default_samplerate") or 48_000)))
        if rate <= 0:
            rate = 48_000
        self._device_label = str(info.get("name") or device or "默认输入")
        return device, rate

    def start(self) -> None:
        import sounddevice as sd

        device, rate = self._resolve()
        self._resampler = StreamResampler(rate, SAMPLE_RATE)
        self._running = True

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                log.debug("PortAudio status: %s", status)
            if not self._running or self._resampler is None:
                return
            try:
                self._emit(self._resampler.process(indata, self.gain_db))
            except Exception:
                log.exception("Microphone processing failed")

        def error_callback(exc: Exception):
            self._fail(f"麦克风读取失败：{exc}")

        try:
            self._stream = sd.InputStream(
                samplerate=rate,
                device=device,
                channels=1,
                dtype="float32",
                blocksize=0,
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            self._running = False
            self._stream = None
            raise AudioError(f"无法开始录音：{exc}") from exc
        log.info("Audio input started: %s @ %s Hz", self._device_label, rate)

    def stop(self) -> None:
        self._running = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.debug("Error closing input stream", exc_info=True)

    def describe(self) -> str:
        return self._device_label


class MicrophoneSource(_InputStreamSource):
    kind = "microphone"


class _WasapiLoopbackSource(AudioSource):
    kind = "system"

    def __init__(
        self,
        on_audio: AudioCallback,
        device_name: str = "",
        on_error: ErrorCallback | None = None,
        on_finished: FinishedCallback | None = None,
        gain_db: float = 0.0,
    ) -> None:
        super().__init__(on_audio, on_error, on_finished, gain_db)
        self.device_name = device_name
        self._thread: threading.Thread | None = None
        self._recorder = None
        self._label = "系统声音"

    def start(self) -> None:
        try:
            import soundcard as sc
        except Exception as exc:
            raise AudioError(f"系统声音捕获组件不可用：{exc}") from exc

        try:
            loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
            if self.device_name:
                match = next((m for m in loopbacks if m.name == self.device_name), None)
                if match is None:
                    match = next((m for m in loopbacks if self.device_name in m.name), None)
                if match is None:
                    raise AudioError("找不到所选系统声音设备，请刷新设备列表。")
                mic = match
            else:
                speaker = sc.default_speaker()
                if speaker is None:
                    raise AudioError("没有检测到默认扬声器。")
                mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            self._label = f"{mic.name}"
        except AudioError:
            raise
        except Exception as exc:
            raise AudioError(f"无法定位系统声音设备：{exc}") from exc

        rate = 48_000
        recorder = None
        last_error: Exception | None = None
        for candidate in (48_000, 44_100, 32_000):
            try:
                recorder = mic.recorder(samplerate=candidate, channels=2, blocksize=1920)
                recorder.__enter__()
                rate = candidate
                break
            except Exception as exc:
                last_error = exc
                recorder = None
        if recorder is None:
            raise AudioError(f"无法捕获系统声音：{last_error}")
        self._recorder = recorder
        self._running = True
        resampler = StreamResampler(rate, SAMPLE_RATE)
        block = max(320, int(rate * 0.02))

        def loop() -> None:
            try:
                while self._running:
                    data = recorder.record(numframes=block)
                    self._emit(resampler.process(np.asarray(data), self.gain_db))
            except Exception as exc:
                if self._running:
                    self._fail(f"系统声音捕获中断：{exc}")
            finally:
                try:
                    recorder.__exit__(None, None, None)
                except Exception:
                    pass

        self._thread = threading.Thread(target=loop, name="subloom-loopback", daemon=True)
        self._thread.start()
        log.info("System audio loopback started: %s @ %s Hz", self._label, rate)

    def stop(self) -> None:
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._recorder = None

    def describe(self) -> str:
        return self._label


class SystemAudioSource(AudioSource):
    """Cross-platform system-audio facade.

    Windows uses WASAPI loopback.  On macOS/Linux the user selects a virtual
    loopback input (BlackHole, Soundflower, or a PulseAudio monitor).
    """

    kind = "system"

    def __init__(
        self,
        on_audio: AudioCallback,
        device_name: str = "",
        on_error: ErrorCallback | None = None,
        on_finished: FinishedCallback | None = None,
        gain_db: float = 0.0,
    ) -> None:
        super().__init__(on_audio, on_error, on_finished, gain_db)
        self.device_name = device_name
        self._impl: AudioSource | None = None

    def start(self) -> None:
        self._running = True
        if sys.platform == "win32":
            self._impl = _WasapiLoopbackSource(
                self.on_audio, self.device_name, self.on_error, self.on_finished, self.gain_db
            )
        else:
            if not self.device_name:
                self._running = False
                raise AudioError(
                    "未选择系统音频设备。\n\n" + system_audio_hint()
                )
            self._impl = MicrophoneSource(
                self.on_audio,
                device=self.device_name,
                on_error=self.on_error,
                on_finished=self.on_finished,
                gain_db=self.gain_db,
            )
        try:
            self._impl.start()
        except Exception:
            self._running = False
            raise

    def stop(self) -> None:
        self._running = False
        if self._impl is not None:
            self._impl.stop()
            self._impl = None

    def describe(self) -> str:
        return self._impl.describe() if self._impl else "系统声音"


class FileAudioSource(AudioSource):
    kind = "file"

    def __init__(
        self,
        path: str | Path,
        on_audio: AudioCallback,
        on_error: ErrorCallback | None = None,
        on_finished: FinishedCallback | None = None,
        gain_db: float = 0.0,
        realtime: bool = True,
    ) -> None:
        super().__init__(on_audio, on_error, on_finished, gain_db)
        self.path = Path(path)
        self.realtime = realtime
        self._thread: threading.Thread | None = None
        self.duration = 0.0

    def start(self) -> None:
        if not self.path.is_file():
            raise AudioError(f"文件不存在：{self.path}")
        try:
            import av  # noqa: F401
        except Exception as exc:
            raise AudioError(f"缺少音视频解码组件：{exc}") from exc
        self._running = True
        self._thread = threading.Thread(target=self._run, name="subloom-file", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import av

        container = None
        try:
            container = av.open(str(self.path))
            streams = [s for s in container.streams if s.type == "audio"]
            if not streams:
                raise AudioError("该文件不包含音频轨道。")
            stream = streams[0]
            if container.duration:
                self.duration = float(container.duration / av.time_base)
            resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
            started = time.monotonic()
            total = 0
            pending = np.zeros(0, dtype=np.float32)
            target_chunk = SAMPLE_RATE // 5  # 200 ms

            def emit_pending(force: bool = False) -> None:
                nonlocal pending, total
                while pending.size >= target_chunk or (force and pending.size):
                    take = min(pending.size, target_chunk) if not force else pending.size
                    chunk = pending[:take].copy()
                    pending = pending[take:]
                    total += chunk.size
                    self._emit(chunk)
                    if self.realtime:
                        target = started + total / SAMPLE_RATE
                        delay = target - time.monotonic()
                        if delay > 0:
                            time.sleep(min(delay, 0.5))

            for frame in container.decode(stream):
                if not self._running:
                    break
                converted = resampler.resample(frame)
                if converted is None:
                    continue
                if not isinstance(converted, (list, tuple)):
                    converted = [converted]
                for out_frame in converted:
                    arr = np.asarray(out_frame.to_ndarray(), dtype=np.float32).reshape(-1)
                    if arr.size:
                        pending = np.concatenate((pending, arr))
                        emit_pending()
            if self._running:
                flushed = resampler.resample(None)
                if flushed:
                    if not isinstance(flushed, (list, tuple)):
                        flushed = [flushed]
                    for out_frame in flushed:
                        arr = np.asarray(out_frame.to_ndarray(), dtype=np.float32).reshape(-1)
                        pending = np.concatenate((pending, arr))
                emit_pending(force=True)
        except AudioError as exc:
            if self._running:
                self._fail(str(exc))
        except Exception as exc:
            if self._running:
                self._fail(f"文件解码失败：{exc}")
        finally:
            try:
                if container is not None:
                    container.close()
            except Exception:
                pass
            was_running = self._running
            self._running = False
            if was_running:
                self._finish()

    def stop(self) -> None:
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def describe(self) -> str:
        return self.path.name


def create_source(
    kind: str,
    *,
    on_audio: AudioCallback,
    on_error: ErrorCallback | None = None,
    on_finished: FinishedCallback | None = None,
    gain_db: float = 0.0,
    system_device: str = "",
    microphone_device: str = "",
    file_path: str | Path | None = None,
    realtime: bool = True,
) -> AudioSource:
    if kind == "microphone":
        return MicrophoneSource(
            on_audio,
            device=microphone_device or None,
            on_error=on_error,
            on_finished=on_finished,
            gain_db=gain_db,
        )
    if kind == "file":
        if not file_path:
            raise AudioError("请选择要识别的音视频文件。")
        return FileAudioSource(
            file_path,
            on_audio,
            on_error=on_error,
            on_finished=on_finished,
            gain_db=gain_db,
            realtime=realtime,
        )
    if kind == "system":
        return SystemAudioSource(
            on_audio,
            device_name=system_device,
            on_error=on_error,
            on_finished=on_finished,
            gain_db=gain_db,
        )
    raise AudioError(f"未知音频来源：{kind}")
