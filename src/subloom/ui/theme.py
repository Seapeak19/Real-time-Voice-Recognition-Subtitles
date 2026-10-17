"""Visual language for SubLoom."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette, QPolygonF
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle

from ..paths import resource_path

_CHEVRON = resource_path("assets", "chevron-down.png").as_posix()
_CHECK = resource_path("assets", "check.png").as_posix()

BG = "#0B0F14"
BG_SOFT = "#0F141C"
PANEL = "#121821"
PANEL_RAISED = "#17202B"
FIELD = "#0D121A"
BORDER = "#223041"
BORDER_SOFT = "#1A2532"
TEXT = "#F2F6F9"
TEXT_SOFT = "#C8D2DE"
MUTED = "#8493A6"
DIM = "#5A687A"
ACCENT = "#5FE3C0"
ACCENT_HOVER = "#7BF0D2"
ACCENT_DARK = "#06251E"
LIVE = "#FF8E72"
WARN = "#FFC06A"
ERROR = "#FF7B7B"

STYLE = f"""
* {{
    outline: none;
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}
QFrame#Header {{
    background: transparent;
}}
QLabel#AppTitle {{
    font-size: 23px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#AppTitleZh {{
    font-size: 13px;
    font-weight: 600;
    color: {ACCENT};
    background: rgba(95, 227, 192, 0.10);
    border: 1px solid rgba(95, 227, 192, 0.22);
    border-radius: 7px;
    padding: 2px 7px;
}}
QLabel#Tagline {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#SectionLabel {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Mono {{
    color: {MUTED};
    font-size: 11px;
}}
QFrame#SidePanel, QFrame#TranscriptPanel {{
    background: {PANEL};
    border: 1px solid {BORDER_SOFT};
    border-radius: 18px;
}}
QFrame#SubCard {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
}}
QFrame#OverlayToggleCard {{
    background: {BG_SOFT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
}}
QPushButton {{
    background: transparent;
    color: {TEXT_SOFT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border-color: #31445A;
}}
QPushButton:pressed {{
    background: #0D141D;
}}
QPushButton:disabled {{
    color: {DIM};
    border-color: {BORDER_SOFT};
    background: transparent;
}}
QPushButton#PrimaryButton {{
    background: {ACCENT};
    color: {ACCENT_DARK};
    border: none;
    border-radius: 11px;
    min-height: 46px;
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#PrimaryButton:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#PrimaryButton:pressed {{
    background: #4ACFAD;
}}
QPushButton#PrimaryButton[running="true"] {{
    background: rgba(255, 123, 123, 0.12);
    color: {ERROR};
    border: 1px solid rgba(255, 123, 123, 0.45);
}}
QPushButton#PrimaryButton[running="true"]:hover {{
    background: rgba(255, 123, 123, 0.20);
}}
QPushButton#SecondaryButton {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    color: {TEXT};
}}
QPushButton#GhostButton {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 6px 9px;
}}
QPushButton#GhostButton:hover {{
    background: {PANEL_RAISED};
    color: {TEXT};
}}
QPushButton#DangerGhostButton {{
    background: transparent;
    border: 1px solid transparent;
    color: {ERROR};
    padding: 6px 9px;
}}
QPushButton#DangerGhostButton:hover {{
    background: rgba(255, 123, 123, 0.10);
    border-color: rgba(255, 123, 123, 0.28);
}}
QPushButton#SegmentButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    color: {MUTED};
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#SegmentButton:hover {{
    color: {TEXT};
    background: rgba(255, 255, 255, 0.04);
}}
QPushButton#SegmentButton:checked {{
    background: {ACCENT};
    color: {ACCENT_DARK};
}}
QFrame#SegmentBar {{
    background: {FIELD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 9px;
}}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 10px;
    min-height: 22px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_DARK};
}}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #31445A;
}}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    background: transparent;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url("{_CHEVRON}");
    width: 12px;
    height: 8px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(95, 227, 192, 0.16);
    selection-color: {TEXT};
    color: {TEXT};
    outline: none;
}}
QCheckBox {{
    color: {TEXT_SOFT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid #34465A;
    background: {FIELD};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("{_CHECK}");
}}
QSlider::groove:horizontal {{
    height: 4px;
    border-radius: 2px;
    background: {FIELD};
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {TEXT};
    border: 2px solid {ACCENT};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2A3849;
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3A4C60;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    background: {PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 8px 14px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    background: {PANEL_RAISED};
    color: {ACCENT};
}}
QGroupBox {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    background: {BG_SOFT};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {TEXT_SOFT};
}}
QToolTip {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 6px;
}}
QProgressBar {{
    background: {FIELD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 5px;
    text-align: center;
    color: {TEXT_SOFT};
    min-height: 8px;
    max-height: 8px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QMessageBox, QProgressDialog {{
    background: {PANEL};
}}
QMenu {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    padding: 5px;
    border-radius: 8px;
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 5px;
    color: {TEXT_SOFT};
}}
QMenu::item:selected {{
    background: rgba(95, 227, 192, 0.12);
    color: {TEXT};
}}
"""


def pick_font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in (
        "Segoe UI Variable Text",
        "Segoe UI",
        "SF Pro Text",
        "PingFang SC",
        "Microsoft YaHei UI",
        "Noto Sans CJK SC",
        "Noto Sans",
    ):
        if candidate in families:
            return candidate
    return QApplication.font().family()


class SubLoomStyle(QProxyStyle):
    """Fusion with clean, theme-coloured dropdown arrows."""

    def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            rect = option.rect
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(MUTED))
            cx = rect.center().x()
            cy = rect.center().y()
            arrow = QPolygonF(
                [
                    QPointF(cx - 4.0, cy - 2.0),
                    QPointF(cx + 4.0, cy - 2.0),
                    QPointF(cx, cy + 3.0),
                ]
            )
            painter.drawPolygon(arrow)
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


def apply_theme(app: QApplication) -> None:
    app.setStyle(SubLoomStyle("Fusion"))
    family = pick_font_family()
    font = QFont(family, 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(FIELD))
    palette.setColor(QPalette.AlternateBase, QColor(PANEL_RAISED))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(PANEL))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor(ACCENT_DARK))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL_RAISED))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(DIM))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
