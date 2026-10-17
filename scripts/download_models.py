"""Download models into the per-user data directory.

Examples:
    python scripts/download_models.py --whisper large-v3-turbo
    python scripts/download_models.py --nllb
    python scripts/download_models.py --all
"""

from __future__ import annotations

import argparse

from subloom.asr.whisper_engine import MODEL_SIZES, download_model, resolve_model
from subloom.config import ASRConfig
from subloom.paths import ensure_dirs, models_dir
from subloom.translate.nllb import (
    NLLB_LICENSE,
    NLLB_SIZE_HINT,
    download_local_model,
    local_model_available,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download SubLoom models")
    parser.add_argument(
        "--whisper",
        metavar="MODEL",
        help="Whisper model name (tiny/base/small/medium/large-v3/large-v3-turbo) or 'auto'",
    )
    parser.add_argument("--nllb", action="store_true", help="Download the local NLLB translation model")
    parser.add_argument("--all", action="store_true", help="Download the auto Whisper model and NLLB")
    args = parser.parse_args()
    ensure_dirs()
    print(f"Model directory: {models_dir()}")

    if not (args.whisper or args.nllb or args.all):
        parser.print_help()
        return 0

    if args.all:
        args.whisper = "auto"
        args.nllb = True

    if args.whisper:
        model = resolve_model(ASRConfig(model=args.whisper))
        print(f"Whisper model: {model} ({MODEL_SIZES.get(model, 'size unknown')})")
        path = download_model(model, progress=lambda message: print(message, flush=True))
        print(f"Whisper ready: {path}")

    if args.nllb:
        if local_model_available():
            print("NLLB is already downloaded.")
        else:
            print(f"NLLB: {NLLB_SIZE_HINT}; license {NLLB_LICENSE}")
            path = download_local_model(progress=lambda message: print(message, flush=True))
            print(f"NLLB ready: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
