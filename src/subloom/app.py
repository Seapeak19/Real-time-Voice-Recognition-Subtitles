"""Application entrypoint."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, APP_NAME_ZH, __version__
from .config import AppConfig, load_config
from .i18n import set_language
from .logging_utils import configure_logging
from .paths import ensure_dirs
from .ui.main_window import MainWindow, make_app_icon
from .ui.theme import apply_theme

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subloom",
        description=f"{APP_NAME} ({APP_NAME_ZH}) — 实时语音翻译字幕",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="构建窗口后自动退出（用于 CI 检查 UI 是否可创建）",
    )
    parser.add_argument("--self-check", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--require-cuda", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--config",
        type=Path,
        help="使用指定配置文件（同时改变该实例的配置目录）",
    )
    return parser


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        try:
            QMessageBox.critical(
                None,
                "SubLoom 发生错误",
                f"{exc_value}\n\n详细信息已写入日志文件。",
            )
        except Exception:
            traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SubLoom.Captions")
    except Exception:
        pass


def _self_check(require_cuda: bool = False) -> int:
    """Import native-heavy pieces so a packaged build can be smoke tested."""
    import numpy as np

    from .asr.cuda_runtime import cuda_ready
    from .audio.vad import VadSegmenter
    from .paths import resource_path

    for name in ("faster_whisper", "ctranslate2", "av", "sentencepiece", "soxr", "keyring"):
        __import__(name)
    if sys.platform == "win32":
        __import__("soundcard")
    segmenter = VadSegmenter()
    segmenter.push(np.zeros(16_000, dtype=np.float32))
    assert resource_path("assets", "icon.png").is_file()
    cuda_ok, cuda_reason = cuda_ready()
    log.info("CUDA usable=%s reason=%s", cuda_ok, cuda_reason)
    if require_cuda and not cuda_ok:
        log.error("CUDA is required but unavailable: %s", cuda_reason)
        return 2
    log.info("self-check ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config:
        os.environ["SUBLOOM_CONFIG_DIR"] = str(args.config.expanduser().resolve().parent)
    configure_logging(args.debug)
    ensure_dirs()
    _set_windows_app_id()

    if args.self_check:
        return _self_check(args.require_cuda)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(f"{APP_NAME} · {APP_NAME_ZH}")
    app.setOrganizationName("SubLoom")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_app_icon())
    apply_theme(app)
    _install_excepthook()

    try:
        config = load_config(args.config)
    except Exception:
        log.exception("Could not load config")
        config = AppConfig()
    set_language(config.ui.language)
    window = MainWindow(config)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(900, app.quit)
    log.info("SubLoom %s started", __version__)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
