"""Always-on-top translator subtitle overlay."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import replace

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from ..config import OverlayConfig
from ..i18n import display_language, tr
from ..models import CaptionSegment
from . import theme

log = logging.getLogger(__name__)


class SubtitleOverlay(QWidget):
    settings_requested = Signal()
    hide_requested = Signal()
    position_changed = Signal(int, int)
    font_size_changed = Signal(int)

    def __init__(self, config: OverlayConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._segment: CaptionSegment | None = None
        self._last_translation_text = ""
        self._last_translation_id = ""
        self._current_final: CaptionSegment | None = None
        self._current_final_shown_at = 0.0
        self._final_queue: deque[CaptionSegment] = deque(maxlen=2)
        self._seen_final_ids: set[str] = set()
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_expired)
        self._drag_origin: QPoint | None = None
        self._window_origin: QPoint | None = None
        self._fitted_height = 0
        self.setWindowTitle(tr("SubLoom 字幕"))
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.setCursor(Qt.OpenHandCursor)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(28, 18, 28, 22)
        self._root.setSpacing(5)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._live = QLabel("●  LIVE")
        self._live.setStyleSheet(
            f"color: {theme.LIVE}; font-size: 9px; font-weight: 700; letter-spacing: 2px;"
        )
        self._lang = QLabel("")
        self._lang.setStyleSheet(
            f"color: {theme.MUTED}; font-size: 9px; font-weight: 600; letter-spacing: 1px;"
        )
        header.addWidget(self._live)
        header.addStretch(1)
        header.addWidget(self._lang)
        self._root.addLayout(header)

        self._translation = QLabel("")
        self._translation.setAlignment(Qt.AlignCenter)
        self._translation.setWordWrap(True)
        self._translation.setTextInteractionFlags(Qt.NoTextInteraction)
        self._root.addWidget(self._translation)

        self._source = QLabel("")
        self._source.setAlignment(Qt.AlignCenter)
        self._source.setWordWrap(True)
        self._source.setStyleSheet(f"color: {theme.MUTED}; font-size: 13px;")
        self._root.addWidget(self._source)

        self._hint = QLabel(tr("正在聆听…"))
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        self._root.addWidget(self._hint)

        self.apply_config(config)
        self.resize(config.width, 130)
        self._restore_position()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        alpha = int(max(0.2, min(1.0, self.config.opacity)) * 242)
        painter.setBrush(QColor(7, 6, 12, alpha))
        painter.setPen(QPen(QColor(155, 108, 255, 48), 1))
        painter.drawRoundedRect(rect, 19, 19)
        # A neon gradient edge gives the overlay a modern, broadcast feel.
        gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        gradient.setColorAt(0, QColor(theme.ACCENT))
        gradient.setColorAt(0.5, QColor(theme.ACCENT_2))
        gradient.setColorAt(1, QColor(theme.ACCENT_3))
        painter.setPen(QPen(QBrush(gradient), 1.6))
        painter.drawLine(
            int(rect.left() + 26),
            int(rect.top()),
            int(rect.right() - 26),
            int(rect.top()),
        )
        painter.end()

    # ------------------------------------------------------------------ text
    def set_segment(self, segment: CaptionSegment) -> None:
        """Show finalized lines only, with a minimum reading time.

        Partial results still churn quickly, especially on fast speech. Showing
        them here makes a stable translation disappear before it can be read.
        The main window can keep showing partials; the overlay is for reading.
        """
        translated = segment.translated_text.strip()
        failed = bool(segment.warning)

        if not segment.is_final:
            if self._current_final is not None:
                return
            if segment.translation_expected or segment.translation_pending:
                self._render_segment(
                    replace(
                        segment,
                        translated_text="",
                        translation_pending=True,
                        translation_expected=True,
                    )
                )
            else:
                self._render_segment(segment)
            return

        if not translated and not failed:
            if self._current_final is None:
                self._render_segment(
                    replace(segment, translation_pending=True, translation_expected=True)
                )
            return

        if self._current_final is not None and self._current_final.id == segment.id:
            # A cached preview followed by the context-refined final: update in
            # place and keep the reading clock, so the hold does not restart.
            old_length = len(self._current_final.translated_text.strip())
            self._current_final = segment
            self._render_segment(segment)
            if len(segment.translated_text.strip()) > old_length:
                self._current_final_shown_at = time.monotonic()
                self._hold_timer.start(int(self._hold_seconds(segment) * 1000))
            return

        for index, queued in enumerate(self._final_queue):
            if queued.id == segment.id:
                self._final_queue[index] = segment
                return

        # A very late refinement of a line that has already been replaced must
        # not bring that old line back after the next sentence is on screen.
        if segment.id in self._seen_final_ids:
            return
        self._seen_final_ids.add(segment.id)
        self._final_queue.append(segment)
        self._maybe_show_next_final()

    def _hold_seconds(self, segment: CaptionSegment) -> float:
        text = segment.translated_text.strip() or segment.source_text.strip()
        chars = len("".join(text.split()))
        return min(4.5, max(self.config.hold_ms / 1000.0, chars / 9.0))

    def _maybe_show_next_final(self) -> None:
        if self._current_final is not None:
            elapsed = time.monotonic() - self._current_final_shown_at
            remaining = self._hold_seconds(self._current_final) - elapsed
            if remaining > 0:
                self._hold_timer.start(max(1, int(remaining * 1000)))
                return
        if not self._final_queue:
            self._hold_timer.stop()
            return
        segment = self._final_queue.popleft()
        self._current_final = segment
        self._current_final_shown_at = time.monotonic()
        self._render_segment(segment)
        self._hold_timer.start(int(self._hold_seconds(segment) * 1000))

    def _on_hold_expired(self) -> None:
        self._maybe_show_next_final()

    def _render_segment(self, segment: CaptionSegment) -> None:
        self._segment = segment
        translated = segment.translated_text.strip()
        source = segment.source_text.strip()
        expected = bool(segment.translation_expected or segment.translation_pending)
        failed = bool(segment.warning)
        same_segment = bool(
            self._last_translation_id and self._last_translation_id == segment.id
        )
        show_original = False
        hint = ""
        kind = "translation"

        if translated:
            main = translated
            self._last_translation_text = translated
            self._last_translation_id = segment.id
            show_original = bool(
                self.config.show_source and source and translated != source
            )
            hint = tr("正在聆听…") if not segment.is_final else ""
        elif expected and not failed:
            # Never present source text as if it were the translated subtitle.
            # While waiting, keep the previous translation visible instead.
            if self._last_translation_text:
                main = self._last_translation_text
                hint = tr("正在更新译文…") if same_segment else tr("正在翻译新一句…")
            else:
                main = tr("正在翻译…")
                hint = ""
                kind = "placeholder"
        elif failed:
            main = source or tr("翻译失败")
            hint = tr("翻译失败 · 显示原文")
            kind = "error"
        else:
            main = source
            hint = tr("仅原文") if segment.target_lang and segment.target_lang != segment.source_lang else ""
            kind = "source"

        if not main:
            self._translation.setText("")
            self._source.setText("")
            self._source.setVisible(False)
            self._hint.setText(tr("正在聆听…"))
            self._hint.show()
            self._refit()
            return

        self._translation.setText(main)
        colors = {
            "translation": theme.TEXT,
            "placeholder": theme.MUTED,
            "source": theme.TEXT_SOFT,
            "error": theme.WARN,
        }
        self._translation.setStyleSheet(
            f"color: {colors[kind]}; font-size: {self.config.font_size}px; font-weight: 600;"
        )
        self._source.setText(source if show_original else "")
        self._source.setVisible(show_original)
        self._hint.setText(hint)
        self._hint.setStyleSheet(
            f"color: {theme.WARN if kind == 'error' else theme.DIM}; font-size: 11px;"
        )
        self._hint.setVisible(bool(hint))
        self._live.setText("●  LIVE" if not segment.is_final else "●  FINAL")
        self._live.setStyleSheet(
            f"color: {theme.LIVE if not segment.is_final else theme.MUTED};"
            " font-size: 9px; font-weight: 700; letter-spacing: 2px;"
        )
        src = display_language(segment.source_lang)
        tgt = display_language(segment.target_lang)
        if expected or translated:
            self._lang.setText(f"{src}  →  {tgt}" if tgt and tgt != src else src)
        elif tgt and tgt != src:
            self._lang.setText(f"{src}  ·  {tr('原文')}")
        else:
            self._lang.setText(src)
        self._refit()

    def set_session_hint(self, text: str | None = None) -> None:
        text = text or tr("正在聆听…")
        if self._segment is None or not self._segment.source_text:
            self._translation.setText("")
            self._source.setText("")
            self._source.setVisible(False)
            self._hint.setText(text)
            self._hint.show()
            self._live.setText("●  LIVE")
            self._refit()

    def clear(self) -> None:
        self._hold_timer.stop()
        self._current_final = None
        self._current_final_shown_at = 0.0
        self._final_queue.clear()
        self._seen_final_ids.clear()
        self._segment = None
        self._last_translation_text = ""
        self._last_translation_id = ""
        self._translation.setText("")
        self._source.setText("")
        self._source.setVisible(False)
        self._hint.setText(tr("正在聆听…"))
        self._hint.show()
        self._refit()

    # ------------------------------------------------------------------ layout
    def _refit(self) -> None:
        width = int(self.config.width)
        if self.width() != width:
            self.setFixedWidth(width)
        QTimer.singleShot(0, self._do_refit)

    def _do_refit(self) -> None:
        if not self.isVisible():
            return
        self.layout().activate()
        height = max(104, self.sizeHint().height())
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            height = min(height, int(screen.availableGeometry().height() * 0.45))
        if height != self._fitted_height:
            self._fitted_height = height
            self.setFixedHeight(height)
            if self.config.y is None:
                self._place_default()
            else:
                self._clamp_to_screen()

    def apply_config(self, config: OverlayConfig) -> None:
        self.config = config
        size = max(14, min(64, int(config.font_size)))
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setWeight(QFont.DemiBold)
        self._translation.setFont(font)
        self._translation.setStyleSheet(f"color: {theme.TEXT}; font-size: {size}px; font-weight: 600;")
        source_font = QFont(self.font())
        source_font.setPixelSize(max(10, int(size * 0.52)))
        self._source.setFont(source_font)
        self._source.setStyleSheet(
            f"color: {theme.MUTED}; font-size: {max(10, int(size * 0.52))}px;"
        )
        self._set_click_through(config.click_through)
        self.setFixedWidth(int(config.width))
        self._refit()
        self.update()

    def _set_click_through(self, enabled: bool) -> None:
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        if self.isVisible():
            self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
            self.show()
        else:
            self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
        self.setCursor(Qt.ArrowCursor if enabled else Qt.OpenHandCursor)

    # ------------------------------------------------------------------ position
    def _restore_position(self) -> None:
        if self.config.x is not None and self.config.y is not None:
            self.move(int(self.config.x), int(self.config.y))
            self._clamp_to_screen()
        else:
            self._place_default()

    def _clamp_to_screen(self) -> None:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        width = min(self.width(), geo.width())
        x = min(max(self.x(), geo.left()), max(geo.left(), geo.right() - width + 1))
        height = min(self.height(), geo.height())
        y = min(max(self.y(), geo.top()), max(geo.top(), geo.bottom() - height + 1))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def _place_default(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        width = max(420, min(int(self.config.width), geo.width() - 40))
        self.setFixedWidth(width)
        self._fitted_height = max(104, self.sizeHint().height())
        x = geo.x() + (geo.width() - width) // 2
        y = geo.y() + geo.bottom() - self._fitted_height - 72
        self.move(x, y)

    def show_overlay(self) -> None:
        self.show()
        self.raise_()
        self._restore_position()
        self._refit()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and not self.config.click_through:
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None and self._window_origin is not None:
            delta = event.globalPosition().toPoint() - self._drag_origin
            self.move(self._window_origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None:
            self._drag_origin = None
            self._window_origin = None
            self.setCursor(Qt.OpenHandCursor)
            self._clamp_to_screen()
            self.position_changed.emit(self.x(), self.y())
        super().mouseReleaseEvent(event)

    def _show_menu(self, position) -> None:
        if self.config.click_through:
            return
        menu = QMenu(self)
        menu.addAction(tr("字幕设置…"), self.settings_requested.emit)
        menu.addSeparator()
        menu.addAction(tr("增大字号"), lambda: self.font_size_changed.emit(self.config.font_size + 2))
        menu.addAction(tr("减小字号"), lambda: self.font_size_changed.emit(self.config.font_size - 2))
        menu.addSeparator()
        menu.addAction(tr("隐藏字幕窗"), self.hide_requested.emit)
        menu.exec(self.mapToGlobal(position))
