"""Streaming mono downmix and resampling to 16 kHz float32."""

from __future__ import annotations

import numpy as np

try:  # soxr gives a clean, high-quality streaming resampler
    import soxr
except ImportError:  # pragma: no cover - exercised only in minimal installs
    soxr = None


class StreamResampler:
    """Convert arbitrary-rate, multi-channel blocks to 16 kHz mono.

    ``process`` may be called from a realtime audio callback, so it avoids
    allocations where practical and never blocks.
    """

    def __init__(self, input_rate: int, output_rate: int = 16_000, channels: int = 1):
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("sample rates must be positive")
        self.input_rate = int(input_rate)
        self.output_rate = int(output_rate)
        self.channels = max(1, int(channels))
        self._stream = None
        if soxr is not None and self.input_rate != self.output_rate:
            self._stream = soxr.ResampleStream(
                self.input_rate,
                self.output_rate,
                1,
                dtype="float32",
                quality="HQ",
            )
        self._buf = np.zeros(0, dtype=np.float32)
        self._phase = 0.0
        self._step = self.input_rate / float(self.output_rate)

    def process(self, block: np.ndarray, gain_db: float = 0.0) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 2:
            if x.shape[1] > 1:
                x = x.mean(axis=1)
            else:
                x = x[:, 0]
        x = np.ascontiguousarray(x.reshape(-1))
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        if gain_db:
            x = x * np.float32(10.0 ** (gain_db / 20.0))
        np.clip(x, -1.0, 1.0, out=x)
        if self.input_rate == self.output_rate:
            return x.astype(np.float32, copy=False)
        if self._stream is not None:
            y = self._stream.resample_chunk(x, last=False)
            return np.clip(np.asarray(y, dtype=np.float32).reshape(-1), -1.0, 1.0)
        return self._linear(x)

    def _linear(self, x: np.ndarray) -> np.ndarray:
        """Fallback resampler with persistent phase (no soxr installed)."""
        self._buf = np.concatenate((self._buf, x)) if self._buf.size else x.copy()
        if self._buf.size < 2:
            return np.zeros(0, dtype=np.float32)
        span = self._buf.size - 1
        if self._phase > span:
            self._phase -= span
            self._buf = self._buf[-1:].copy()
            return np.zeros(0, dtype=np.float32)
        count = int(np.floor((span - self._phase) / self._step)) + 1
        positions = self._phase + np.arange(count, dtype=np.float64) * self._step
        out = np.interp(positions, np.arange(self._buf.size), self._buf).astype(np.float32)
        consumed = self._phase + count * self._step
        cut = int(np.floor(consumed))
        cut = min(cut, self._buf.size - 1)
        self._buf = self._buf[cut:].copy()
        self._phase = consumed - cut
        return out

    def flush(self) -> np.ndarray:
        if self._stream is not None:
            try:
                y = self._stream.resample_chunk(np.zeros(0, dtype=np.float32), last=True)
                return np.clip(np.asarray(y, dtype=np.float32).reshape(-1), -1.0, 1.0)
            except Exception:
                return np.zeros(0, dtype=np.float32)
        return np.zeros(0, dtype=np.float32)

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._phase = 0.0
        if self._stream is not None:
            self._stream.clear()
