"""Generate the README screenshot from a deterministic sample transcript."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from subloom.config import AppConfig
from subloom.models import CaptionSegment
from subloom.ui.main_window import MainWindow
from subloom.ui.theme import apply_theme

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    config = AppConfig()
    config.translation.provider = "cloud"
    config.translation.target_lang = "zh"
    config.overlay.enabled = False
    config.first_run = False
    window = MainWindow(config)
    window.resize(1280, 840)
    window.show()

    samples = [
        CaptionSegment(
            id="demo-1",
            source_text="Good evening everyone, thanks for joining the product review.",
            translated_text="大家晚上好，感谢参加这次产品评审。",
            source_lang="en",
            target_lang="zh",
            start=0.4,
            end=4.6,
            is_final=True,
            revision=3,
            provider="cloud",
        ),
        CaptionSegment(
            id="demo-2",
            source_text="Today we are shipping real-time subtitles in twelve languages.",
            translated_text="今天我们将上线支持十二种语言的实时字幕。",
            source_lang="en",
            target_lang="zh",
            start=5.1,
            end=9.3,
            is_final=True,
            revision=3,
            provider="cloud",
        ),
        CaptionSegment(
            id="demo-3",
            source_text="The latency is now under one second on a laptop GPU.",
            translated_text="现在，在笔记本 GPU 上延迟已经低于一秒。",
            source_lang="en",
            target_lang="zh",
            start=9.9,
            end=13.4,
            is_final=True,
            revision=3,
            provider="cloud",
        ),
        CaptionSegment(
            id="demo-4",
            source_text="Let's open the floor for questions about the offline mode.",
            translated_text="",
            source_lang="en",
            target_lang="zh",
            start=14.1,
            end=17.8,
            is_final=False,
            revision=1,
            translation_pending=True,
            translation_expected=True,
        ),
    ]

    def populate() -> None:
        for segment in samples:
            window._on_segment(segment)
        window._status_pill.set_state("listening", "聆听中")
        window._status_text.setText("已识别三句，继续聆听…")
        window._detected_label.setText("英语 · 98%")
        window._provider_label.setText("云端翻译")
        window._level_meter.set_level(-14)
        window._elapsed_label.setText("00:18")
        window._stats_label.setText("3 句")

    def capture() -> None:
        out = ROOT / "docs" / "screenshot.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        pixmap = window.grab()
        pixmap.save(str(out), "PNG")
        print(f"wrote {out} ({pixmap.width()}x{pixmap.height()})")
        window.close()
        app.quit()

    QTimer.singleShot(500, populate)
    QTimer.singleShot(1400, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
