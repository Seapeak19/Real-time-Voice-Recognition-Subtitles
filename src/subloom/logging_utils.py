"""Logging setup."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from .paths import logs_dir


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(handler, "_subloom", False) for handler in root.handlers):
        return
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    console._subloom = True  # type: ignore[attr-defined]
    root.addHandler(console)
    try:
        logs_dir().mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir() / "subloom.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler._subloom = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)
    except OSError:
        pass
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
