"""Print CUDA / GPU diagnostics for SubLoom."""

from __future__ import annotations

import sys

from subloom.asr.cuda_runtime import cuda_device_count, cuda_ready, install_hint
from subloom.paths import models_dir


def main() -> int:
    print(f"Python: {sys.version.split()[0]} ({sys.platform})")
    print(f"Models: {models_dir()}")
    try:
        import ctranslate2

        print(f"CTranslate2: {ctranslate2.__version__}")
    except Exception as exc:
        print(f"CTranslate2: unavailable ({exc})")
    ready, reason = cuda_ready()
    count = cuda_device_count()
    print(f"CUDA devices: {count}")
    print(f"CUDA usable: {ready}")
    if not ready:
        print(f"Reason: {reason}")
        print(install_hint())
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
