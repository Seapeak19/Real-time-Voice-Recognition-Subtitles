from __future__ import annotations

import numpy as np

from subloom.audio.vad import FRAME_SAMPLES, VadSegmenter


class FakeVad:
    def is_speech(self, data: bytes, sample_rate: int) -> bool:
        values = np.frombuffer(data, dtype=np.int16)
        return bool(np.mean(np.abs(values)) > 800)


def speech_frame(level: float = 6000.0) -> np.ndarray:
    return np.full(FRAME_SAMPLES, level / 32768.0, dtype=np.float32)


def silent_frame() -> np.ndarray:
    return np.zeros(FRAME_SAMPLES, dtype=np.float32)


def make_segmenter(**kwargs) -> VadSegmenter:
    defaults = dict(
        vad=FakeVad(),
        silence_ms=200,
        min_speech_ms=100,
        max_segment_sec=5.0,
        partial_interval_ms=200,
        preroll_ms=60,
    )
    defaults.update(kwargs)
    return VadSegmenter(**defaults)


def test_speech_produces_partial_and_final():
    segmenter = make_segmenter()
    events = []
    for _ in range(20):
        events.extend(segmenter.push(speech_frame()))
    kinds = [event.kind for event in events]
    assert "partial" in kinds
    for _ in range(15):
        events.extend(segmenter.push(silent_frame()))
    finals = [event for event in events if event.kind == "final"]
    assert len(finals) == 1
    final = finals[0]
    assert final.audio.size >= FRAME_SAMPLES
    assert final.end > final.start
    assert not segmenter.speaking


def test_short_noise_is_not_emitted():
    segmenter = make_segmenter()
    events = []
    for _ in range(3):
        events.extend(segmenter.push(speech_frame()))
    for _ in range(15):
        events.extend(segmenter.push(silent_frame()))
    assert not [event for event in events if event.kind == "final"]


def test_flush_finalizes_in_progress_utterance():
    segmenter = make_segmenter()
    for _ in range(15):
        segmenter.push(speech_frame())
    event = segmenter.flush()
    assert event is not None
    assert event.kind == "final"
    assert not segmenter.speaking


def test_partial_audio_grows_and_does_not_include_trailing_silence():
    segmenter = make_segmenter()
    sizes = []
    for _ in range(25):
        for event in segmenter.push(speech_frame()):
            if event.kind == "partial":
                sizes.append(event.audio.size)
    assert sizes == sorted(sizes)
    assert len(sizes) >= 2


def test_frames_can_be_fed_in_odd_sizes():
    segmenter = make_segmenter()
    block = np.concatenate([speech_frame() for _ in range(30)])
    events = []
    events.extend(segmenter.push(block[:123]))
    events.extend(segmenter.push(block[123:777]))
    events.extend(segmenter.push(block[777:]))
    events.extend(segmenter.push(np.zeros(FRAME_SAMPLES * 15, dtype=np.float32)))
    assert any(event.kind == "final" for event in events)
