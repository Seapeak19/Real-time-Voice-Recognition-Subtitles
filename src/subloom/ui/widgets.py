"""Reusable Qt widgets for the SubLoom interface."""

from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..languages import language_name
from ..models import CaptionSegment
from ..subtitles import format_timestamp
from . import theme


class LogoMark(QWidget):
    def __init__(self, size: int = 42, parent=None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, self._size - 1, self._size - 1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor(theme.ACCENT_2))
        gradient.setColorAt(0.52, QColor(theme.ACCENT_3))
        gradient.setColorAt(1, QColor(theme.ACCENT))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, self._size * 0.28, self._size * 0.28)
        pen = QPen(QColor(theme.ACCENT_DARK))
        pen.setWidthF(max(2.0, self._size * 0.075))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        left = self._size * 0.25
        right = self._size * 0.75
        y1 = self._size * 0.40
        y2 = self._size * 0.58
        painter.drawLine(QPointF(left, y1), QPointF(right, y1))
        painter.drawLine(QPointF(left + self._size * 0.12, y2), QPointF(right - self._size * 0.12, y2))
        painter.end()


class StatusPill(QFrame):
    def __init__(self, text: str = "就绪", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 4, 11, 4)
        layout.setSpacing(6)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {theme.ACCENT}; font-size: 8px;")
        self._label = QLabel(text)
        self._label.setStyleSheet(f"color: {theme.TEXT_SOFT}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        self._set_bg(theme.ACCENT)
        self._timer = QTimer(self)
        self._timer.setInterval(650)
        self._timer.timeout.connect(self._blink)
        self._blink_on = True
        self._state = "ready"

    def _set_bg(self, color: str, alpha_bg: int = 18, alpha_border: int = 46) -> None:
        qcolor = QColor(color)
        self.setStyleSheet(
            f"QFrame#StatusPill {{ background: rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()},"
            f" {alpha_bg / 255:.3f});"
            f" border: 1px solid rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()},"
            f" {alpha_border / 255:.3f}); border-radius: 11px; }}"
        )
        self._dot.setStyleSheet(f"color: {color}; font-size: 8px;")

    def set_state(self, state: str, text: str | None = None) -> None:
        self._state = state
        colors = {
            "ready": theme.ACCENT,
            "listening": theme.LIVE,
            "loading": theme.WARN,
            "error": theme.ERROR,
        }
        color = colors.get(state, theme.ACCENT)
        self._set_bg(color)
        if text:
            self._label.setText(text)
        if state == "listening":
            self._timer.start()
        else:
            self._timer.stop()
            self._dot.setText("●")
            self._blink_on = True

    def _blink(self) -> None:
        self._blink_on = not self._blink_on
        self._dot.setText("●" if self._blink_on else "○")


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 2, self.width() - 2, self.height() - 4)
        off = QColor("#2A2340")
        on = QColor(theme.ACCENT)
        color = QColor(
            int(off.red() + (on.red() - off.red()) * self._offset),
            int(off.green() + (on.green() - off.green()) * self._offset),
            int(off.blue() + (on.blue() - off.blue()) * self._offset),
        )
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        radius = 9.0
        x = 4 + (self.width() - 8 - radius * 2) * self._offset
        painter.setBrush(QColor("#F7FAFC"))
        painter.drawEllipse(QRectF(x, self.height() / 2 - radius, radius * 2, radius * 2))
        painter.end()


class SegmentedControl(QWidget):
    changed = Signal(str)

    def __init__(self, options: Sequence[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._current = ""
        bar = QFrame(self)
        bar.setObjectName("SegmentBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(bar)
        inner = QHBoxLayout(bar)
        inner.setContentsMargins(3, 3, 3, 3)
        inner.setSpacing(2)
        for value, label in options:
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, v=value: self.set_value(v))
            inner.addWidget(button, 1)
            self._buttons[value] = button
        if options:
            self.set_value(options[0][0], emit=False)

    @property
    def value(self) -> str:
        return self._current

    def set_value(self, value: str, emit: bool = True) -> None:
        if value not in self._buttons:
            return
        changed = value != self._current
        self._current = value
        for key, button in self._buttons.items():
            button.setChecked(key == value)
        if emit and changed:
            self.changed.emit(value)


class LevelMeter(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._level = -60.0
        self._display = -60.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_level(self, db: float) -> None:
        self._level = max(-60.0, min(0.0, float(db)))

    def _tick(self) -> None:
        target = self._level
        self._display += (target - self._display) * (0.55 if target > self._display else 0.18)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        count = 22
        gap = 3
        width = (self.width() - gap * (count - 1)) / count
        active = int(round((self._display + 60.0) / 60.0 * count))
        for index in range(count):
            x = index * (width + gap)
            rect = QRectF(x, 5, width, self.height() - 10)
            if index < active:
                if index >= count - 4:
                    color = QColor(theme.ACCENT_3)
                elif index >= count - 9:
                    color = QColor(theme.WARN)
                else:
                    color = QColor(theme.ACCENT)
            else:
                color = QColor("#2A2340")
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 2, 2)
        painter.end()


class IconTextButton(QPushButton):
    def __init__(self, glyph: str, text: str, parent=None) -> None:
        super().__init__(f"{glyph}  {text}", parent)
        self.setObjectName("GhostButton")
        self.setCursor(Qt.PointingHandCursor)


class CaptionCard(QFrame):
    def __init__(self, segment: CaptionSegment, show_source: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SubCard")
        self.setProperty("partial", not segment.is_final)
        self._segment = segment
        self._show_source = show_source
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 13)
        layout.setSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._time = QLabel()
        self._time.setObjectName("Mono")
        self._language = QLabel()
        self._language.setStyleSheet(
            f"color: {theme.MUTED}; font-size: 10px; font-weight: 600;"
            f" background: {theme.BG}; border-radius: 5px; padding: 2px 6px;"
        )
        self._state = QLabel()
        self._state.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 9px; font-weight: 700; letter-spacing: 1px;"
        )
        top.addWidget(self._time)
        top.addWidget(self._language)
        top.addStretch(1)
        top.addWidget(self._state)
        layout.addLayout(top)

        self._source = QLabel()
        self._source.setWordWrap(True)
        self._source.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        layout.addWidget(self._source)

        self._translation = QLabel()
        self._translation.setWordWrap(True)
        self._translation.setTextInteractionFlags(Qt.TextSelectableByMouse)
        font = self._translation.font()
        font.setPixelSize(21)
        font.setWeight(QFont.DemiBold)
        self._translation.setFont(font)
        self._translation.setStyleSheet(f"color: {theme.TEXT}; font-size: 21px; font-weight: 600;")
        layout.addWidget(self._translation)

        self._pending = QLabel("翻译中…")
        self._pending.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        layout.addWidget(self._pending)

        self._warning = QLabel()
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet(f"color: {theme.WARN}; font-size: 10px;")
        layout.addWidget(self._warning)
        self.update_segment(segment, show_source)

    def update_segment(self, segment: CaptionSegment, show_source: bool) -> None:
        self._segment = segment
        self._show_source = show_source
        self._time.setText(format_timestamp(segment.start)[3:8])
        self._language.setText(language_name(segment.source_lang))
        self._state.setText("LIVE" if not segment.is_final else "FINAL")
        self._state.setStyleSheet(
            f"color: {theme.LIVE if not segment.is_final else theme.DIM};"
            " font-size: 9px; font-weight: 700; letter-spacing: 1px;"
        )
        translated = segment.translated_text.strip()
        source = segment.source_text.strip()
        expected = bool(segment.translation_expected or segment.translation_pending)
        failed = bool(segment.warning)
        if translated:
            main = translated
            kind = "translation"
            pending = bool(segment.translation_pending)
        elif expected and not failed:
            main = "正在翻译…"
            kind = "placeholder"
            pending = False
        elif failed:
            main = source
            kind = "error"
            pending = False
        else:
            main = source
            kind = "source"
            pending = False
        self._translation.setText(main)
        colors = {
            "translation": theme.TEXT,
            "placeholder": theme.MUTED,
            "source": theme.TEXT_SOFT,
            "error": theme.WARN,
        }
        self._translation.setStyleSheet(
            f"color: {colors[kind]}; font-size: 21px; font-weight: 600;"
        )
        self._source.setText(source)
        show_original = bool(
            show_source and translated and source and translated != source
        )
        self._source.setVisible(show_original)
        self._pending.setVisible(pending)
        self._warning.setVisible(failed)
        if failed:
            text = segment.warning if len(segment.warning) <= 140 else segment.warning[:137] + "…"
            self._warning.setText("⚠ " + text)
        language = language_name(segment.source_lang)
        if (
            not translated
            and not expected
            and segment.target_lang
            and segment.target_lang != segment.source_lang
        ):
            language += " · 原文"
        self._language.setText(language)
        self.setProperty("partial", not segment.is_final)
        self.style().unpolish(self)
        self.style().polish(self)


class EmptyState(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.addStretch(1)
        self._mark = WaveMark(76)
        layout.addWidget(self._mark, 0, Qt.AlignHCenter)
        title = QLabel("声音会在这里变成字幕")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 20px; font-weight: 700;")
        subtitle = QLabel(
            "选择系统声音、麦克风或一个媒体文件，点击「开始字幕」。\n"
            "识别在本机完成，翻译可走云端或本地模型。"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px; line-height: 1.6;")
        layout.addSpacing(14)
        layout.addWidget(title)
        layout.addSpacing(4)
        layout.addWidget(subtitle)
        layout.addStretch(1)


class WaveMark(QWidget):
    def __init__(self, size: int = 72, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._phase += 0.16
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(155, 108, 255, 30))
        painter.drawEllipse(center, self.width() / 2 - 2, self.height() / 2 - 2)
        bars = 7
        spacing = 7
        start = center.x() - (bars - 1) * spacing / 2
        for i in range(bars):
            amp = 5 + (math.sin(self._phase + i * 0.8) + 1) * 7
            x = start + i * spacing
            color = theme.ACCENT if i % 2 == 0 else theme.ACCENT_2
            painter.setPen(QPen(QColor(color), 2.4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x, center.y() - amp / 2), QPointF(x, center.y() + amp / 2))
        painter.end()


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._full = text

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        super().setText(text)

    def paintEvent(self, event) -> None:  # noqa: N802
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full, Qt.ElideRight, self.width())
        if elided != self.text():
            super().setText(elided)
        super().paintEvent(event)
