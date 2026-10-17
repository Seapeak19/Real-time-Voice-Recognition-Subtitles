"""The realtime capture → VAD → ASR → translation pipeline."""

from __future__ import annotations

import logging
import math
import queue
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .asr import LanguageTracker, WhisperASR
from .audio.capture import AudioSource, create_source
from .audio.vad import VadEvent, VadSegmenter
from .config import AppConfig
from .languages import from_whisper, normalize_code, whisper_code
from .models import CaptionSegment, ModelNotReadyError
from .translate import Readiness, TranslationService

log = logging.getLogger(__name__)


@dataclass
class PipelineCallbacks:
    on_segment: object
    on_status: object = lambda message: None
    on_error: object = lambda message: None
    on_finished: object = lambda: None
    on_language: object = lambda code, probability: None
    on_level: object = lambda db: None


class CaptionPipeline:
    def __init__(self, config: AppConfig, callbacks: PipelineCallbacks):
        self.config = config
        self.callbacks = callbacks
        self.asr = WhisperASR(config.asr)
        self.translator = TranslationService(config.translation)
        self.tracker = LanguageTracker(config.asr.language_mode)
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=80)
        self._stop_event = threading.Event()
        self._source_finished = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: AudioSource | None = None
        self._state_lock = threading.RLock()
        self._error_sent = False
        self._finished = False
        self._translation_enabled = False
        self._source_only = False
        self._session_token = ""
        self._sequence = 0
        self._current_id: str | None = None
        self._revision: dict[str, int] = {}
        self._last_partial_text: dict[str, str] = {}
        self._partial_translation_at: dict[str, float] = {}
        self._partial_translation_text: dict[str, str] = {}
        self._recent_sources: deque[str] = deque(maxlen=3)
        self._context_pairs: deque[tuple[str, str]] = deque(maxlen=3)
        self._final_executor: ThreadPoolExecutor | None = None
        self._partial_executor: ThreadPoolExecutor | None = None
        self._last_level_at = 0.0
        self._last_drop_status = 0.0
        self._dropped_seconds = 0.0
        self._started_at: float | None = None
        self._target_lang = config.translation.target_lang
        self._vad_segmenter = VadSegmenter(
            aggressiveness=config.audio.vad_aggressiveness,
            silence_ms=config.asr.silence_ms,
            min_speech_ms=config.asr.min_speech_ms,
            max_segment_sec=config.asr.max_segment_sec,
            partial_interval_ms=config.asr.partial_interval_ms,
        )

    # ------------------------------------------------------------------ state
    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def selected_provider(self) -> str:
        return self.translator.selected_provider()

    def readiness(self) -> Readiness:
        return self.translator.readiness()

    def status(self) -> tuple[bool, str]:
        return self.asr.status()

    # ------------------------------------------------------------------ start
    def start(self, *, file_path: str | Path | None = None, allow_source_only: bool = False) -> None:
        if self.is_running:
            raise RuntimeError("Pipeline is already running")
        readiness = self.translator.readiness()
        provider = readiness.provider
        if provider != "off" and not readiness.ready:
            if not allow_source_only:
                raise ModelNotReadyError(readiness.message)
            self._source_only = True
        else:
            self._source_only = provider == "off"
        self._translation_enabled = bool(readiness.ready and provider not in {"off", "none"})
        self._target_lang = self.config.translation.target_lang
        self.tracker.reset()
        self._vad_segmenter.reset()
        self._stop_event.clear()
        self._source_finished.clear()
        self._error_sent = False
        self._finished = False
        self._queue = queue.Queue(maxsize=80)
        self._session_token = uuid.uuid4().hex[:8]
        self._sequence = 0
        self._current_id = None
        self._revision.clear()
        self._last_partial_text.clear()
        self._partial_translation_at.clear()
        self._partial_translation_text.clear()
        self._recent_sources.clear()
        self._context_pairs.clear()
        self._dropped_seconds = 0.0
        self._started_at = None
        self._last_drop_status = 0.0
        self._final_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="subloom-final")
        self._partial_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="subloom-partial")
        self._thread = threading.Thread(
            target=self._run,
            args=(Path(file_path) if file_path else None,),
            name="subloom-pipeline",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------ audio
    def _on_audio(self, samples: np.ndarray) -> None:
        if self._stop_event.is_set():
            return
        now = time.monotonic()
        if now - self._last_level_at >= 0.05:
            self._last_level_at = now
            try:
                rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float32))))
                db = 20.0 * math.log10(max(rms, 1e-5))
                self.callbacks.on_level(db)
            except Exception:
                pass
        try:
            self._queue.put_nowait(samples)
        except queue.Full:
            dropped = 0
            try:
                old = self._queue.get_nowait()
                dropped += len(old)
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(samples)
            except queue.Full:
                dropped += len(samples)
            self._dropped_seconds += dropped / 16_000.0
            if time.monotonic() - self._last_drop_status > 4.0:
                self._last_drop_status = time.monotonic()
                self._status("识别速度暂时落后，已丢弃少量旧音频")

    def _on_source_error(self, message: str) -> None:
        self._fail(message)

    def _on_source_finished(self) -> None:
        self._source_finished.set()

    # ------------------------------------------------------------------ worker
    def _run(self, file_path: Path | None) -> None:
        source: AudioSource | None = None
        try:
            if self._stop_event.is_set():
                return
            if self._translation_enabled and self.selected_provider == "local":
                self._status("正在准备本地翻译模型…")
                self.translator.warm_local(self._status)
            self._status("正在准备识别模型…")
            self.asr.load(self._status)
            if self._stop_event.is_set():
                return
            self._status("正在启动音频…")
            source = create_source(
                self.config.audio.source,
                on_audio=self._on_audio,
                on_error=self._on_source_error,
                on_finished=self._on_source_finished,
                gain_db=self.config.audio.input_gain_db,
                system_device=self.config.audio.system_device,
                microphone_device=self.config.audio.microphone_device,
                file_path=file_path,
                realtime=self.config.audio.file_realtime,
            )
            self._source = source
            source.start()
            self._started_at = time.monotonic()
            self._status("正在聆听…")
            while not self._stop_event.is_set():
                if self._source_finished.is_set() and self._queue.empty():
                    break
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._process_audio(chunk)
            # Finalize the utterance in progress when the input ends/stops.
            if self._stop_event.is_set() or self._source_finished.is_set():
                self._flush_vad()
        except Exception as exc:
            log.exception("Pipeline failed")
            self._fail(str(exc))
        finally:
            if source is not None:
                try:
                    source.stop()
                except Exception:
                    log.debug("Could not stop source", exc_info=True)
            self._source = None
            self._shutdown_executors()
            self._finish()

    def _process_audio(self, chunk: np.ndarray) -> None:
        try:
            events = self._vad.push(chunk)
        except Exception as exc:
            log.exception("VAD failure")
            self._fail(f"音频分段失败：{exc}")
            return
        for event in events:
            try:
                if event.kind == "partial":
                    self._handle_partial(event)
                else:
                    self._handle_final(event)
            except Exception as exc:
                log.exception("Recognition failure")
                self._status(f"这一句识别失败：{exc}")

    @property
    def _vad(self) -> VadSegmenter:
        return self._vad_segmenter

    def _flush_vad(self) -> None:
        try:
            event = self._vad.flush()
        except Exception:
            log.debug("VAD flush failed", exc_info=True)
            return
        if event is not None:
            try:
                self._handle_final(event)
            except Exception as exc:
                log.exception("Final transcription failed")
                self._status(f"最后一句识别失败：{exc}")

    def _asr_language(self) -> str | None:
        locked = self.tracker.locked
        if not locked:
            return None
        return whisper_code(locked) or locked

    def _source_code(self, detected: str, probability: float, duration: float, final: bool) -> str:
        if self.tracker.manual_mode:
            manual = normalize_code(self.config.asr.language_mode)
            language = from_whisper(whisper_code(manual) or manual)
            code = language.code if language else (manual or "en")
            self.callbacks.on_language(code, probability)
            return code
        code = self.tracker.observe(detected, probability, duration, final=final)
        if not code:
            code = normalize_code(detected) or "en"
        self.callbacks.on_language(code, probability)
        return code

    def _new_segment_id(self) -> str:
        self._sequence += 1
        return f"{self._session_token}-{self._sequence:04d}"

    def _bump_revision(self, segment_id: str) -> int:
        with self._state_lock:
            revision = self._revision.get(segment_id, 0) + 1
            self._revision[segment_id] = revision
            return revision

    def _current_segment_id(self) -> str:
        if self._current_id is None:
            self._current_id = self._new_segment_id()
        return self._current_id

    def _handle_partial(self, event: VadEvent) -> None:
        segment_id = self._current_segment_id()
        result = self.asr.transcribe(
            event.audio,
            language=self._asr_language(),
            partial=True,
            context=self._recent_sources[-1] if self._recent_sources else "",
        )
        if not result.text:
            return
        source = self._source_code(result.language, result.language_probability, result.duration, False)
        revision = self._bump_revision(segment_id)
        self._last_partial_text[segment_id] = result.text
        expected = self._should_translate(source)
        segment = CaptionSegment(
            id=segment_id,
            source_text=result.text,
            source_lang=source,
            target_lang=self._target_lang,
            start=event.start,
            end=event.end,
            is_final=False,
            revision=revision,
            translation_pending=expected,
            translation_expected=expected,
        )
        if source == self._target_lang:
            segment.translated_text = result.text
            segment.translation_pending = False
            segment.translation_expected = False
        self._emit(segment)
        if expected:
            self._maybe_submit_partial(segment)

    def _handle_final(self, event: VadEvent) -> None:
        segment_id = self._current_segment_id()
        result = self.asr.transcribe(
            event.audio,
            language=self._asr_language(),
            partial=False,
            context=self._recent_sources[-1] if self._recent_sources else "",
        )
        text = result.text or self._last_partial_text.get(segment_id, "")
        if not text:
            self._current_id = None
            return
        source = self._source_code(result.language, result.language_probability, result.duration, True)
        revision = self._bump_revision(segment_id)
        expected = self._should_translate(source)
        segment = CaptionSegment(
            id=segment_id,
            source_text=text,
            source_lang=source,
            target_lang=self._target_lang,
            start=event.start,
            end=event.end,
            is_final=True,
            revision=revision,
            translation_pending=expected,
            translation_expected=expected,
        )
        if source == self._target_lang:
            segment.translated_text = text
            segment.translation_pending = False
            segment.translation_expected = False
        self._recent_sources.append(text)
        self._current_id = None
        self._last_partial_text.pop(segment_id, None)
        self._partial_translation_at.pop(segment_id, None)
        self._partial_translation_text.pop(segment_id, None)
        self._emit(segment)
        if expected:
            context = list(self._context_pairs)
            self._submit_final(segment, context)
        elif source == self._target_lang:
            with self._state_lock:
                self._context_pairs.append((text, text))

    def _should_translate(self, source: str) -> bool:
        return (
            self._translation_enabled
            and self.config.translation.provider != "off"
            and source != self._target_lang
        )

    def _maybe_submit_partial(self, segment: CaptionSegment) -> None:
        if not self.config.translation.translate_partials:
            return
        now = time.monotonic()
        previous_time = self._partial_translation_at.get(segment.id, 0.0)
        previous_text = self._partial_translation_text.get(segment.id, "")
        interval = 0.9 if self.selected_provider == "cloud" else 0.55
        if now - previous_time < interval:
            return
        if previous_text and _similar(previous_text, segment.source_text):
            return
        self._partial_translation_at[segment.id] = now
        self._partial_translation_text[segment.id] = segment.source_text
        executor = self._partial_executor
        if executor is None:
            return
        context = list(self._context_pairs)
        try:
            executor.submit(self._translate_job, replace(segment), context)
        except RuntimeError:
            pass

    def _submit_final(self, segment: CaptionSegment, context: list[tuple[str, str]]) -> None:
        executor = self._final_executor
        if executor is None:
            return
        try:
            executor.submit(self._translate_job, replace(segment), context)
        except RuntimeError:
            pass

    def _translate_job(self, segment: CaptionSegment, context: list[tuple[str, str]]) -> None:
        started = time.monotonic()
        try:
            translated, provider, fallback, warning = self.translator.translate(
                segment.source_text,
                segment.source_lang,
                segment.target_lang,
                context=context,
                partial=not segment.is_final,
            )
        except Exception as exc:
            log.warning("Translation failed for %s: %s", segment.id, exc)
            with self._state_lock:
                if self._revision.get(segment.id) != segment.revision:
                    return
            updated = replace(segment, translation_pending=False, warning=str(exc))
            self._emit(updated)
            return
        with self._state_lock:
            if self._revision.get(segment.id) != segment.revision:
                return
            updated = replace(
                segment,
                translated_text=translated,
                provider=provider,
                warning=warning,
                translation_pending=False,
            )
            if segment.is_final:
                self._context_pairs.append((segment.source_text, translated))
        self._emit(updated)
        if segment.is_final:
            log.debug(
                "Translated final %s in %.2fs (%s)",
                segment.id,
                time.monotonic() - started,
                provider,
            )

    # ------------------------------------------------------------------ output
    def _emit(self, segment: CaptionSegment) -> None:
        try:
            self.callbacks.on_segment(segment)
        except Exception:
            log.exception("Segment callback failed")

    def _status(self, message: str) -> None:
        try:
            self.callbacks.on_status(message)
        except Exception:
            pass

    def _fail(self, message: str) -> None:
        with self._state_lock:
            if self._error_sent:
                return
            self._error_sent = True
        self._stop_event.set()
        try:
            self.callbacks.on_error(message)
        except Exception:
            log.exception("Error callback failed")

    def _shutdown_executors(self) -> None:
        partial, self._partial_executor = self._partial_executor, None
        final, self._final_executor = self._final_executor, None
        if partial is not None:
            partial.shutdown(wait=False, cancel_futures=True)
        if final is not None:
            if self._translation_enabled:
                self._status("正在完成最后一句翻译…")
            final.shutdown(wait=True)

    def _finish(self) -> None:
        with self._state_lock:
            if self._finished:
                return
            self._finished = True
        self._stop_event.set()
        try:
            self.callbacks.on_finished()
        except Exception:
            log.exception("Finished callback failed")

    # ------------------------------------------------------------------ stop
    def stop(self, timeout: float = 8.0) -> None:
        self._stop_event.set()
        source = self._source
        if source is not None:
            try:
                source.stop()
            except Exception:
                log.debug("Source stop failed", exc_info=True)
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def close(self) -> None:
        self.stop(timeout=4.0)
        self.translator.close()
        self.asr.close()
        try:
            if hasattr(self, "_vad_segmenter"):
                self._vad_segmenter.reset()
        except Exception:
            pass


def _similar(a: str, b: str) -> bool:
    a = a.strip()
    b = b.strip()
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer.startswith(shorter) and len(shorter) / max(1, len(longer)) > 0.72
