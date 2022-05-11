from abc import ABC, abstractmethod
from typing import List, Optional
from PySide6.QtCore import QSize, Qt, Signal, SignalInstance, Slot
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QMouseEvent, QPaintEvent, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QColorDialog, QFrame, QLabel, QListWidget, QPushButton, QTreeWidget, QTreeWidgetItem, QWidget
from numpy.lib.arraysetops import isin
from juniors_toolbox.gui.images import CommonCursor, get_common_cursor
from juniors_toolbox.gui.widgets import ABCMetaWidget, ABCWidget

from juniors_toolbox.gui.widgets.colorpicker import ColorPicker
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.utils.types import RGB8, BasicColors, RGBA8, DigitalColor
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.filesystem import resource_path


class A_ColorButton(QLabel, ABCWidget):
    """
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-picker, while
    right-clicking resets the color to the default.
    """
    colorChanged = Signal(str, DigitalColor)
    pressed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.setCursor(get_common_cursor(
            CommonCursor.COLOR_PICKER, QSize(40, 40)))
        self.setAlignment(Qt.AlignCenter)

        self._color: DigitalColor = None
        self._default: DigitalColor = None

        self._press = False
        self.pressed.connect(self.show_color_picker)

    def get_color(self) -> DigitalColor:
        if self._color is not None:
            return self._color
        else:
            return self._default

    @abstractmethod
    def set_color(self, color: DigitalColor): ...

    @abstractmethod
    def set_default(self, color: DigitalColor): ...

    @abstractmethod
    @Slot()
    def show_color_picker(self):
        """
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.
        """
        ...

    @Slot(QPaintEvent)
    def paintEvent(self, event: QPaintEvent):
        fillpattern = QPixmap(
            str(resource_path("gui/backgrounds/transparent.png")))
        fillpattern = fillpattern.scaled(
            32, 32, Qt.AspectRatioMode.KeepAspectRatio)
        """
        pen = QPen()
        pen.setBrush(QBrush(fillpattern))
        pen.setStyle(Qt.NoPen)
        """
        color = self.get_color()
        painter = QPainter()
        painter.begin(self)
        if color.alpha is not None:
            painter.setOpacity(1 - (self.get_color().alpha / 255))
        painter.drawTiledPixmap(self.rect(), fillpattern)
        painter.end()
        super().paintEvent(event)

    @Slot(QMouseEvent)
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.RightButton:
            self.set_color(self._default)

        if e.button() == Qt.LeftButton:
            self._press = True

        return super().mousePressEvent(e)

    @Slot(QMouseEvent)
    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._press:
            self._press = False
            self.pressed.emit()

        return super().mouseReleaseEvent(e)


class ColorButtonRGBA8(A_ColorButton):
    def get_color(self) -> RGBA8:
        return super().get_color()

    def set_color(self, color: RGBA8):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(self.objectName(), color)

        color = self._color if self._color else self._default
        textColor = color.chooseContrastBW()

        backgroundColorSheet = f"rgba({color.red},{color.green},{color.blue},{color.alpha})"
        textColorSheet = f"rgba({textColor.red},{textColor.green},{textColor.blue},{textColor.alpha})"
        self.setStyleSheet(
            f"background-color: {backgroundColorSheet}; color: {textColorSheet}")

        self.setText(color.hex())

    @Slot()
    def show_color_picker(self):
        """
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.
        """
        picker = ColorPicker(False, True)
        if self._color:
            self.set_color(RGBA8.from_tuple(
                picker.getColor(self._color.tuple())))
        else:
            self.set_color(RGBA8.from_tuple(
                picker.getColor(self._default.tuple())))


class ColorButtonRGB8(A_ColorButton):
    def get_color(self) -> RGB8:
        return super().get_color()

    def set_color(self, color: RGB8):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(self.objectName(), color)

        color = self._color if self._color else self._default
        textColor = color.chooseContrastBW()

        backgroundColorSheet = f"rgb({color.red},{color.green},{color.blue})"
        textColorSheet = f"rgb({textColor.red},{textColor.green},{textColor.blue})"
        self.setStyleSheet(
            f"background-color: {backgroundColorSheet}; color: {textColorSheet}")

        self.setText(color.hex())

    @Slot()
    def show_color_picker(self):
        """
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.
        """
        picker = ColorPicker(False, False)
        if self._color:
            self.set_color(RGB8.from_tuple(
                picker.getColor(self._color.tuple())))
        else:
            self.set_color(RGB8.from_tuple(
                picker.getColor(self._default.tuple())))