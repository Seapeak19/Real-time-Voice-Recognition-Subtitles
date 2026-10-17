from __future__ import annotations

import numpy as np

from subloom.audio.resample import StreamResampler


def test_resample_48k_stereo_to_16k_mono():
    rate = 48_000
    t = np.arange(rate // 2, dtype=np.float32) / rate
    stereo = np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)], axis=1)
    resampler = StreamResampler(rate, 16_000)
    out = resampler.process(stereo)
    out = np.concatenate([out, resampler.flush()])
    assert out.ndim == 1
    assert abs(out.size - 8000) <= 8
    assert np.max(np.abs(out)) <= 1.0


def test_identity_rate_and_gain():
    rate = 16_000
    x = np.full(rate // 2, 0.5, dtype=np.float32)
    resampler = StreamResampler(rate, rate)
    out = resampler.process(x, gain_db=6.0)
    assert out.size == x.size
    assert np.max(out) <= 1.0
