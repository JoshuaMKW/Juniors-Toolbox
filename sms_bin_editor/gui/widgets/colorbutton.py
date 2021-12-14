from typing import List
from PySide2.QtCore import QSize, Qt, Signal
from PySide2.QtGui import QColor, QCursor, QImage, QMouseEvent, QPalette, QPixmap
from PySide2.QtWidgets import QColorDialog, QFrame, QLabel, QListWidget, QPushButton, QTreeWidget, QTreeWidgetItem
from numpy.lib.arraysetops import isin
from sms_bin_editor.gui.commoncursor import CommonCursor, get_common_cursor

from sms_bin_editor.gui.widgets.colorpicker import ColorPicker
from sms_bin_editor.gui.widgets.dynamictab import DynamicTabWidget
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.objects.types import BasicColors, ColorRGBA
from sms_bin_editor.scene import SMSScene
from sms_bin_editor.utils.filesystem import resource_path

class ColorButton(QLabel):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    colorChanged = Signal(object)
    pressed = Signal()

    def __init__(self, *args, color: ColorRGBA = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.press = False

        if color is None:
            self._color = None
            self._default = ColorRGBA(BasicColors.RED)
        else:
            self._color = color
            self._default = color

        self.pressed.connect(self.onColorPicker)

        self.setCursor(get_common_cursor(CommonCursor.COLOR_PICKER, QSize(40, 40)))

        # Set the initial/default state.
        self.setColor(self._default)

    def setColor(self, color: ColorRGBA):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(color)

        color = self._color if self._color else self._default
        textColor = color.chooseContrastBW()

        backgroundColorSheet = f"rgba({color.red},{color.green},{color.blue},{color.alpha})"
        textColorSheet = f"rgba({textColor.red},{textColor.green},{textColor.blue},{textColor.alpha})"
        self.setStyleSheet(f"background-color: {backgroundColorSheet}; color: {textColorSheet}")

    def color(self) -> ColorRGBA:
        return self._color

    def onColorPicker(self):
        """
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.
        """
        dlg = ColorPicker(False, True)
        if self._color:
            self.setColor(ColorRGBA.from_tuple(dlg.getColor(self._color.tuple())))
        else:
            self.setColor(ColorRGBA.from_tuple(dlg.getColor(self._default.tuple())))

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