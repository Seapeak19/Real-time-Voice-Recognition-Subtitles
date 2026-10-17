from __future__ import annotations

from subloom.asr.whisper_engine import _is_cuda_library_error


def test_cuda_library_errors_are_recognized():
    assert _is_cuda_library_error(RuntimeError("Library cublas64_12.dll is not found"))
    assert _is_cuda_library_error(RuntimeError("cudnn64_9.dll cannot be loaded"))
    assert not _is_cuda_library_error(RuntimeError("model file is corrupt"))
