from PySide6.QtCore import (QObject, QPoint, QTimer, Qt, QSize, Signal)
from PySide6.QtGui import QColor, QCursor, QDragLeaveEvent, QMouseEvent
from PySide6.QtWidgets import (QDialog, QGraphicsDropShadowEffect, QWidget)
from juniors_toolbox.gui.images import CommonCursor, get_common_cursor
from juniors_toolbox.gui.tools import get_screen_pixel_color

from juniors_toolbox.utils.types import BasicColors, RGBA8

class ColorPickerDialog(QDialog):
    colorChanged = Signal(RGBA8)
    colorPicked = Signal(RGBA8)
    colorDismissed = Signal(RGBA8)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curColor = RGBA8(BasicColors.BLACK)
        self.dismissColor = RGBA8(BasicColors.BLACK)
        self.mousePos = QPoint(0, 0)
        self.pickReady = False
        
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.checkColorChanged)
        self.updateTimer.start(10)

        self.setCursor(get_common_cursor(CommonCursor.COLOR_PICKER, QSize(40, 40)))
        self.reset()

    def reset(self):
        self.setAttribute(Qt.WA_NoBackground)
        self.setWindowState(Qt.WindowMaximized)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.01)
        self.setMouseTracking(True)

    def checkColorChanged(self):
        if not self.isVisible():
            return

        color = get_screen_pixel_color(QCursor().pos())
        if color != self.curColor:
            self.curColor = color
            self.colorChanged.emit(color)
    
    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        if event.buttons() & Qt.RightButton:
            self.colorDismissed.emit(self.dismissColor)
            self.close()
        elif event.buttons() & Qt.LeftButton:
            self.pickReady = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        if self.pickReady:
            self.colorPicked.emit(self.curColor)
            self.close()

    def setDismissColor(self, color: RGBA8):
        self.dismissColor = color