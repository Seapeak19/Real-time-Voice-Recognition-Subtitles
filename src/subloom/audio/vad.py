"""Low-latency voice activity segmentation.

Whisper is not a streaming model, so SubLoom cuts the microphone/loopback
stream into speech-bounded utterances with WebRTC VAD.  While a person is
still speaking, lightweight partial hypotheses are emitted every ~650 ms;
when a short silence is detected the utterance is finalized and translated
with the higher-quality settings.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000


@dataclass(slots=True)
class VadEvent:
    kind: str  # "partial" | "final"
    audio: np.ndarray
    start: float
    end: float


class VadSegmenter:
    def __init__(
        self,
        *,
        aggressiveness: int = 2,
        silence_ms: int = 450,
        min_speech_ms: int = 350,
        max_segment_sec: float = 9.0,
        partial_interval_ms: int = 650,
        preroll_ms: int = 240,
        sample_rate: int = SAMPLE_RATE,
        vad=None,
    ) -> None:
        if sample_rate != SAMPLE_RATE:
            raise ValueError("VadSegmenter currently expects 16 kHz audio")
        self.sample_rate = sample_rate
        self.frame_samples = FRAME_SAMPLES
        self.frame_sec = FRAME_MS / 1000.0
        self.silence_frames = max(1, int(silence_ms / FRAME_MS))
        self.min_speech_frames = max(1, int(min_speech_ms / FRAME_MS))
        self.max_frames = max(1, int(max_segment_sec * 1000 / FRAME_MS))
        self.partial_frames = max(1, int(partial_interval_ms / FRAME_MS))
        self.preroll_frames = max(0, int(preroll_ms / FRAME_MS))
        if vad is None:
            import webrtcvad

            vad = webrtcvad.Vad(aggressiveness)
        self._vad = vad
        self._residual = np.zeros(0, dtype=np.float32)
        self._pre_roll: deque[np.ndarray] = deque(maxlen=max(1, self.preroll_frames))
        self._speech_run = 0
        self._speaking = False
        self._frames_seen = 0
        self._segment_start_frame = 0
        self._segment_frames: list[np.ndarray] = []
        self._voiced_frames = 0
        self._silence_frames = 0
        self._last_voiced_frame = 0
        self._last_partial_frame = 0

    @property
    def speaking(self) -> bool:
        return self._speaking

    def push(self, samples: np.ndarray) -> list[VadEvent]:
        x = np.asarray(samples, dtype=np.float32).reshape(-1)
        if x.size:
            self._residual = np.concatenate((self._residual, x)) if self._residual.size else x.copy()
        events: list[VadEvent] = []
        while self._residual.size >= self.frame_samples:
            frame = self._residual[: self.frame_samples].copy()
            self._residual = self._residual[self.frame_samples :]
            events.extend(self._process_frame(frame))
        return events

    def _is_speech(self, frame: np.ndarray) -> bool:
        pcm = np.clip(frame, -1.0, 1.0)
        pcm16 = (pcm * 32767.0).astype(np.int16)
        try:
            return bool(self._vad.is_speech(pcm16.tobytes(), self.sample_rate))
        except Exception:
            log.debug("VAD failed on frame", exc_info=True)
            return False

    def _process_frame(self, frame: np.ndarray) -> list[VadEvent]:
        self._frames_seen += 1
        speech = self._is_speech(frame)
        events: list[VadEvent] = []

        if not self._speaking:
            self._pre_roll.append(frame)
            if speech:
                self._speech_run += 1
            else:
                self._speech_run = 0
            if self._speech_run >= 3:
                self._speaking = True
                self._segment_frames = list(self._pre_roll)
                self._segment_start_frame = max(0, self._frames_seen - len(self._segment_frames))
                self._voiced_frames = sum(1 for f in self._segment_frames if self._is_speech(f))
                self._silence_frames = 0
                self._last_voiced_frame = self._frames_seen - 1
                self._last_partial_frame = self._frames_seen
                self._pre_roll.clear()
                self._speech_run = 0
            return events

        self._segment_frames.append(frame)
        if speech:
            self._voiced_frames += 1
            self._last_voiced_frame = self._frames_seen - 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        segment_len = len(self._segment_frames)
        if (
            self._voiced_frames >= self.min_speech_frames
            and self._silence_frames == 0
            and self._frames_seen - self._last_partial_frame >= self.partial_frames
            and segment_len < self.max_frames
        ):
            audio = self._trimmed_audio(keep_tail=1)
            if audio.size:
                events.append(self._partial_event(audio))
            self._last_partial_frame = self._frames_seen

        if self._silence_frames >= self.silence_frames or segment_len >= self.max_frames:
            event = self._finalize()
            if event is not None:
                events.append(event)
        return events

    def _trimmed_audio(self, keep_tail: int = 1) -> np.ndarray:
        if not self._segment_frames:
            return np.zeros(0, dtype=np.float32)
        cut = self._last_voiced_frame - self._segment_start_frame + keep_tail
        cut = max(1, min(cut, len(self._segment_frames)))
        return np.concatenate(self._segment_frames[:cut]).astype(np.float32, copy=False)

    def _partial_event(self, audio: np.ndarray) -> VadEvent:
        start = self._segment_start_frame * self.frame_sec
        end = start + audio.size / self.sample_rate
        return VadEvent("partial", audio, start, end)

    def _finalize(self) -> VadEvent | None:
        audio = self._trimmed_audio(keep_tail=1)
        start = self._segment_start_frame * self.frame_sec
        end = start + audio.size / self.sample_rate
        event = None
        if self._voiced_frames >= self.min_speech_frames and audio.size >= self.frame_samples:
            event = VadEvent("final", audio, start, end)
        self._reset_segment()
        return event

    def _reset_segment(self) -> None:
        self._speaking = False
        self._segment_frames = []
        self._voiced_frames = 0
        self._silence_frames = 0
        self._speech_run = 0
        self._pre_roll.clear()
        self._last_partial_frame = self._frames_seen

    def flush(self) -> VadEvent | None:
        if not self._speaking:
            return None
        return self._finalize()

    def reset(self) -> None:
        self._residual = np.zeros(0, dtype=np.float32)
        self._frames_seen = 0
        self._reset_segment()
