from typing import List
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QMouseEvent, QPaintEvent, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QColorDialog, QFrame, QLabel, QListWidget, QPushButton, QTreeWidget, QTreeWidgetItem
from numpy.lib.arraysetops import isin
from juniors_toolbox.gui.images import CommonCursor, get_common_cursor

from juniors_toolbox.gui.widgets.colorpicker import ColorPicker
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.utils.types import BasicColors, RGBA8
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.filesystem import resource_path

class ColorButton(QLabel):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    colorChanged = Signal(str, object)
    pressed = Signal()

    def __init__(self, *args, color: RGBA8 = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.press = False

        if color is None:
            self._color = None
            self._default = RGBA8(BasicColors.RED)
        else:
            self._color = color
            self._default = color

        self.pressed.connect(self.onColorPicker)

        self.setCursor(get_common_cursor(CommonCursor.COLOR_PICKER, QSize(40, 40)))

        # Set the initial/default state.
        self.setColor(self._default)

    def setColor(self, color: RGBA8):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(self.objectName(), color)

        color = self._color if self._color else self._default
        textColor = color.chooseContrastBW()

        backgroundColorSheet = f"rgba({color.red},{color.green},{color.blue},{color.alpha})"
        textColorSheet = f"rgba({textColor.red},{textColor.green},{textColor.blue},{textColor.alpha})"
        self.setStyleSheet(f"background-color: {backgroundColorSheet}; color: {textColorSheet}")

        self.setText(color.hex())

    def color(self) -> RGBA8:
        return self._color

    def onColorPicker(self):
        """
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.
        """
        dlg = ColorPicker(False, True)
        if self._color:
            self.setColor(RGBA8.from_tuple(dlg.getColor(self._color.tuple())))
        else:
            self.setColor(RGBA8.from_tuple(dlg.getColor(self._default.tuple())))

    def paintEvent(self, event: QPaintEvent):
        fillpattern = QPixmap(str(resource_path("gui/backgrounds/transparent.png")))
        fillpattern = fillpattern.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio)
        """
        pen = QPen()
        pen.setBrush(QBrush(fillpattern))
        pen.setStyle(Qt.NoPen)
        """
        painter = QPainter()
        painter.begin(self)
        painter.setOpacity(1 - (self.color().alpha / 255))
        painter.drawTiledPixmap(self.rect(), fillpattern)
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.RightButton:
            self.setColor(self._default)

        if e.button() == Qt.LeftButton:
            self.press = True

        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self.press:
            self.press = False
            self.pressed.emit()

        return super().mouseReleaseEvent(e)