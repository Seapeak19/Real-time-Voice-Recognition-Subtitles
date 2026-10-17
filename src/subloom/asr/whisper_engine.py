"""Local Whisper speech recognition through faster-whisper."""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import numpy as np

from ..config import ASRConfig
from ..models import ASRResult, ModelNotReadyError
from ..paths import models_dir
from .cuda_runtime import cuda_ready, install_hint

log = logging.getLogger(__name__)

AUTO_MODEL_CUDA = "large-v3-turbo"
AUTO_MODEL_CPU = "small"
MODEL_SIZES = {
    "tiny": "约 75 MB",
    "tiny.en": "约 75 MB",
    "base": "约 145 MB",
    "base.en": "约 145 MB",
    "small": "约 484 MB",
    "small.en": "约 484 MB",
    "medium": "约 1.5 GB",
    "medium.en": "约 1.5 GB",
    "large-v3": "约 3.1 GB",
    "large-v3-turbo": "约 1.6 GB",
    "distil-large-v3": "约 1.5 GB",
    "distil-large-v3.5": "约 1.5 GB",
}
WHISPER_MODELS = (
    "auto",
    "large-v3-turbo",
    "large-v3",
    "distil-large-v3.5",
    "distil-large-v3",
    "medium",
    "small",
    "base",
    "tiny",
)

_NOISE_RE = re.compile(r"^[\s\[\]\(\)（）【】♪♫.,，。!！?？…·\-—]*$")


def cuda_available() -> bool:
    return cuda_ready()[0]


def cuda_status() -> tuple[bool, str]:
    return cuda_ready()


def resolve_model(config: ASRConfig) -> str:
    if config.model and config.model != "auto":
        return config.model
    return AUTO_MODEL_CUDA if cuda_available() else AUTO_MODEL_CPU


def resolve_device(config: ASRConfig) -> str:
    ok, reason = cuda_ready()
    if config.device == "auto":
        return "cuda" if ok else "cpu"
    if config.device == "cuda" and not ok:
        raise ModelNotReadyError(
            "配置为使用 NVIDIA GPU，但 CUDA 后端当前不可用。\n"
            f"原因：{reason}\n\n{install_hint()}\n\n"
            "也可以在设置中把计算设备改为“自动”或 CPU。"
        )
    return config.device


def resolve_compute_type(config: ASRConfig, device: str) -> str:
    if config.compute_type and config.compute_type != "auto":
        return config.compute_type
    return "float16" if device == "cuda" else "int8"


def _safe_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", model).strip("-") or "model"


def model_target(model: str) -> Path:
    if Path(model).expanduser().is_dir():
        return Path(model).expanduser()
    return models_dir() / "whisper" / _safe_name(model)


def model_available(config: ASRConfig) -> bool:
    model = resolve_model(config)
    target = model_target(model)
    return _model_files_present(target)


def _model_files_present(target: Path) -> bool:
    return (target / "model.bin").is_file() and (target / "config.json").is_file()


def download_model(model: str, progress=None) -> Path:
    """Download a Whisper model into the app data directory.

    Returns the local model directory.  Repeated calls are cheap.
    """
    target = model_target(model)
    if _model_files_present(target):
        return target
    if Path(model).expanduser().is_dir():
        return Path(model).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(f"正在下载识别模型 {model}（{MODEL_SIZES.get(model, '首次下载')}）…")
    from faster_whisper.utils import download_model as fw_download

    log.info("Downloading Whisper model %s to %s", model, target)
    fw_download(model, output_dir=str(target))
    if not _model_files_present(target):
        # Some versions create a nested snapshots directory.
        matches = list(target.rglob("model.bin"))
        for match in matches:
            if (match.parent / "config.json").is_file():
                return match.parent
        raise ModelNotReadyError(f"模型下载完成但文件不完整：{target}")
    return target


def clean_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if _NOISE_RE.match(cleaned):
        return ""
    # Whisper occasionally wraps non-speech sounds in brackets.
    if re.fullmatch(r"[\[\(（【]\s*(music|applause|laughter|silence|音乐|掌声|笑声)\s*[\]\)）】]", cleaned, re.I):
        return ""
    return cleaned


class WhisperASR:
    def __init__(self, config: ASRConfig):
        self.config = config
        self._model = None
        self._loaded_key: tuple[str, str, str] | None = None
        self._lock = threading.RLock()
        self._force_cpu = False
        self.last_text = ""

    @property
    def model_name(self) -> str:
        return resolve_model(self.config)

    @property
    def device(self) -> str:
        if self._force_cpu:
            return "cpu"
        return resolve_device(self.config)

    @property
    def compute_type(self) -> str:
        if self._force_cpu:
            return "int8"
        return resolve_compute_type(self.config, self.device)

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def status(self) -> tuple[bool, str]:
        model = self.model_name
        if model_available(self.config):
            return True, f"{model} · 已下载"
        return False, f"{model} · 首次使用将自动下载（{MODEL_SIZES.get(model, '约 1–3 GB')}）"

    def _load_locked(self, progress=None) -> None:
        key = (self.model_name, self.device, self.compute_type)
        if self._model is not None and self._loaded_key == key:
            return
        self.close()
        model_path = download_model(self.model_name, progress)
        if progress:
            progress(f"正在加载 {self.model_name}（{self.device} / {self.compute_type}）…")
        from faster_whisper import WhisperModel

        try:
            model = WhisperModel(
                str(model_path),
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,
                num_workers=1,
            )
        except RuntimeError as exc:
            if self.device == "cuda" and _is_cuda_library_error(exc):
                self._force_cpu = True
                log.warning("CUDA model load failed, falling back to CPU: %s", exc)
                if progress:
                    progress("GPU 运行库加载失败，已自动切换 CPU。")
                self._load_locked(progress)
                return
            raise
        self._model = model
        self._loaded_key = key
        log.info("Whisper loaded: %s on %s (%s)", model_path, self.device, self.compute_type)

    def load(self, progress=None) -> None:
        with self._lock:
            self._load_locked(progress)

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._loaded_key = None

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None = None,
        partial: bool = False,
        context: str = "",
    ) -> ASRResult:
        if audio.size < 160:  # < 10 ms
            return ASRResult("", language or "", 0.0, audio.size / 16_000)
        with self._lock:
            if self._model is None:
                self._load_locked()
            assert self._model is not None
            try:
                return self._transcribe_once(
                    audio, language=language, partial=partial, context=context
                )
            except RuntimeError as exc:
                if self.device == "cuda" and _is_cuda_library_error(exc):
                    self._force_cpu = True
                    log.warning("CUDA inference failed, falling back to CPU: %s", exc)
                    self.close()
                    self._load_locked()
                    assert self._model is not None
                    return self._transcribe_once(
                        audio, language=language, partial=partial, context=context
                    )
                raise

    def _transcribe_once(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        partial: bool,
        context: str,
    ) -> ASRResult:
        assert self._model is not None
        prompt = context[-240:] if (not partial and self.config.use_context_prompt) else ""
        segments, info = self._model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=self.config.partial_beam_size if partial else self.config.beam_size,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            without_timestamps=True,
            vad_filter=False,
            no_speech_threshold=0.75,
            log_prob_threshold=-1.2,
            compression_ratio_threshold=2.4,
            word_timestamps=False,
        )
        texts: list[str] = []
        avg_logprob = 0.0
        no_speech_prob = 0.0
        count = 0
        for segment in segments:
            text = clean_text(segment.text)
            if text:
                texts.append(text)
                avg_logprob += float(getattr(segment, "avg_logprob", 0.0) or 0.0)
                no_speech_prob = max(
                    no_speech_prob, float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
                )
                count += 1
        text = clean_text(" ".join(texts))
        if count:
            avg_logprob /= count
        language_code = getattr(info, "language", "") or (language or "")
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
        duration = float(getattr(info, "duration", 0.0) or audio.size / 16_000)
        if text:
            self.last_text = text
        return ASRResult(text, language_code, probability, duration, avg_logprob, no_speech_prob)


def _is_cuda_library_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("cublas", "cudnn", "cuda", "no kernel image"))
