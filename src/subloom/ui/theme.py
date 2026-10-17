"""Visual language for SubLoom — Neon Pop edition."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette, QPolygonF
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle

from ..paths import resource_path

_CHEVRON = resource_path("assets", "chevron-down.png").as_posix()
_CHECK = resource_path("assets", "check.png").as_posix()

# A near-black stage with acid lime, electric violet and hot pink accents.
BG = "#07070B"
BG_SOFT = "#0D0B14"
PANEL = "#11101A"
PANEL_RAISED = "#191625"
FIELD = "#0B0A12"
BORDER = "#2E2644"
BORDER_SOFT = "#211B31"
TEXT = "#FAF8FF"
TEXT_SOFT = "#D7D2E8"
MUTED = "#9A93B5"
DIM = "#635D78"
ACCENT = "#D8FF3E"
ACCENT_HOVER = "#E9FF7A"
ACCENT_DARK = "#0D1200"
ACCENT_2 = "#9B6CFF"
ACCENT_2_SOFT = "#C4ADFF"
ACCENT_3 = "#FF4F9A"
LIVE = "#FF4F9A"
WARN = "#FFB84D"
ERROR = "#FF6B7A"

STYLE = f"""
* {{
    outline: none;
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {BG}, stop:0.55 #0B0812, stop:1 #0D0A15);
}}
QFrame#Header {{
    background: transparent;
}}
QFrame#NeonDivider {{
    min-height: 2px;
    max-height: 2px;
    border: none;
    border-radius: 1px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:0.46 {ACCENT_2}, stop:1 {ACCENT_3});
}}
QLabel#AppTitle {{
    font-family: "Bahnschrift SemiBold", "Segoe UI Variable Display", "Segoe UI";
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {TEXT};
}}
QLabel#AppTitleZh {{
    font-size: 13px;
    font-weight: 600;
    color: {ACCENT_2_SOFT};
    background: rgba(155, 108, 255, 0.16);
    border: 1px solid rgba(155, 108, 255, 0.38);
    border-radius: 8px;
    padding: 2px 8px;
}}
QLabel#Tagline {{
    color: {MUTED};
    font-size: 12px;
    letter-spacing: 0.3px;
}}
QLabel#SectionLabel {{
    color: {ACCENT_2_SOFT};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Mono {{
    color: {MUTED};
    font-size: 11px;
}}
QFrame#SidePanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #14111F, stop:1 #0E0C16);
    border: 1px solid {BORDER_SOFT};
    border-radius: 20px;
}}
QFrame#TranscriptPanel {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #100E18, stop:1 #0B0A11);
    border: 1px solid {BORDER_SOFT};
    border-radius: 20px;
}}
QFrame#SubCard {{
    background: #161320;
    border-top: 1px solid {BORDER_SOFT};
    border-right: 1px solid {BORDER_SOFT};
    border-bottom: 1px solid {BORDER_SOFT};
    border-left: 3px solid {ACCENT_2};
    border-radius: 13px;
}}
QFrame#SubCard[partial="true"] {{
    background: #171522;
    border-left: 3px solid {ACCENT};
}}
QFrame#OverlayToggleCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(155, 108, 255, 0.12), stop:1 rgba(255, 79, 154, 0.06));
    border: 1px solid rgba(155, 108, 255, 0.30);
    border-radius: 13px;
}}
QPushButton {{
    background: transparent;
    color: {TEXT_SOFT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: rgba(155, 108, 255, 0.12);
    color: {TEXT};
    border-color: #4A3A6B;
}}
QPushButton:pressed {{
    background: #0B0912;
}}
QPushButton:disabled {{
    color: {DIM};
    border-color: {BORDER_SOFT};
    background: transparent;
}}
QPushButton#PrimaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {ACCENT}, stop:1 #A6FF6A);
    color: {ACCENT_DARK};
    border: none;
    border-radius: 12px;
    min-height: 46px;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QPushButton#PrimaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {ACCENT_HOVER}, stop:1 #C4FF8A);
}}
QPushButton#PrimaryButton:pressed {{
    background: #B6E832;
}}
QPushButton#PrimaryButton[running="true"] {{
    background: rgba(255, 79, 154, 0.14);
    color: {LIVE};
    border: 1px solid rgba(255, 79, 154, 0.52);
}}
QPushButton#PrimaryButton[running="true"]:hover {{
    background: rgba(255, 79, 154, 0.23);
}}
QPushButton#SecondaryButton {{
    background: rgba(155, 108, 255, 0.10);
    border: 1px solid rgba(155, 108, 255, 0.34);
    color: {TEXT};
}}
QPushButton#SecondaryButton:hover {{
    background: rgba(155, 108, 255, 0.20);
    border-color: {ACCENT_2};
}}
QPushButton#GhostButton {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 6px 9px;
}}
QPushButton#GhostButton:hover {{
    background: rgba(216, 255, 62, 0.08);
    color: {ACCENT};
}}
QPushButton#DangerGhostButton {{
    background: transparent;
    border: 1px solid transparent;
    color: {ERROR};
    padding: 6px 9px;
}}
QPushButton#DangerGhostButton:hover {{
    background: rgba(255, 107, 122, 0.10);
    border-color: rgba(255, 107, 122, 0.28);
}}
QPushButton#SegmentButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {MUTED};
    padding: 7px 8px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#SegmentButton:hover {{
    color: {TEXT};
    background: rgba(155, 108, 255, 0.10);
}}
QPushButton#SegmentButton:checked {{
    background: {ACCENT};
    color: {ACCENT_DARK};
}}
QFrame#SegmentBar {{
    background: {FIELD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
}}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 10px;
    min-height: 22px;
    color: {TEXT};
    selection-background-color: {ACCENT_2};
    selection-color: {TEXT};
}}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #4A3A6B;
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
    border-radius: 9px;
    padding: 4px;
    selection-background-color: rgba(155, 108, 255, 0.24);
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
    border: 1px solid #4A3A6B;
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_2});
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
    background: #3A2E55;
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
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
    background: rgba(155, 108, 255, 0.10);
}}
QTabBar::tab:selected {{
    background: rgba(216, 255, 62, 0.09);
    color: {ACCENT};
}}
QGroupBox {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    background: {BG_SOFT};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT_2_SOFT};
}}
QToolTip {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 7px;
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border-radius: 4px;
}}
QMessageBox, QProgressDialog {{
    background: {PANEL};
}}
QMenu {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    padding: 5px;
    border-radius: 9px;
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 5px;
    color: {TEXT_SOFT};
}}
QMenu::item:selected {{
    background: rgba(155, 108, 255, 0.22);
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


def pick_cjk_font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "PingFang SC",
        "Hiragino Sans GB",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
    ):
        if candidate in families:
            return candidate
    return ""


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
    cjk_family = pick_cjk_font_family()
    font = QFont(family, 10)
    if cjk_family and cjk_family != family:
        # Qt otherwise falls back to a serif CJK font (SimSun) on Windows,
        # which makes the whole UI look much older than intended.
        font.setFamilies([family, cjk_family])
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
    palette.setColor(QPalette.Highlight, QColor(ACCENT_2))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL_RAISED))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(DIM))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
