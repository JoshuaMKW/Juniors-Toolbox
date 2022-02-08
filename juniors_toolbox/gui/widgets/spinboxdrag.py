from enum import Enum
from genericpath import isfile
import time

from typing import List, Optional, Union

from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer, Signal, SignalInstance
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QMouseEvent
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QPushButton, QDoubleSpinBox, QSpinBox, QApplication,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)
from aenum import IntEnum


class SpinBoxLineEdit(QLineEdit):
    dragOffsetChanged: SignalInstance = Signal(float)

    def __init__(self, isFloat: bool, min: int, max: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._klass_ = float if isFloat else int
        self.min = min
        self.max = max
        self.__mouseLastPos = None
        self.__mouseLoopCounter = 0
        self._startValue = None

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        if event.button() == Qt.MiddleButton:
            self.__mouseLastPos = event.pos()
            self.__mouseLoopCounter = 0
            self._startValue = self._klass_(self.text())
            self.selectAll()

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)

        if self.__mouseLastPos is None:
            return

        ePos = event.pos()
        mPos = self.__mouseLastPos
        wPos = self.pos()

        from juniors_toolbox.gui.application import JuniorsToolbox
        windowSize = JuniorsToolbox.get_instance_size()

        self.setCursor(Qt.SizeHorCursor)
        #print(event.points())
        
        if self._klass_ == float:
            minDif = 0.0000000000000001
        else:
            minDif = 1

        yDiff = wPos.y() - ePos.y()
        multiplier = max(pow(1.0 + yDiff / windowSize.height(), 19), minDif / 50)
        valueOffset = self._klass_(ePos.x() - mPos.x()) * multiplier
        print(yDiff, multiplier, valueOffset)
        if abs(valueOffset) >= minDif:
            self.dragOffsetChanged.emit(valueOffset)
            self.__mouseLastPos = ePos

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self.__mouseLastPos = None
            self.unsetCursor()

        super().mouseReleaseEvent(event)


class SpinBoxDragDouble(QDoubleSpinBox):
    valueChangedExplicit: SignalInstance = Signal(QDoubleSpinBox, float)
    contextUpdated: SignalInstance = Signal()

    def __init__(self, isFloat: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWrapping(True)
        
        lineEdit = SpinBoxLineEdit(True, 0, 0)
        lineEdit.dragOffsetChanged.connect(self.__update_value)
        lineEdit.setMouseTracking(False)
        lineEdit.setDragEnabled(True)
        self.__lineEdit = lineEdit
        self.setLineEdit(lineEdit)

        self.__isFloat = isFloat
        self.__update_bounds()

        self.valueChanged.connect(self.__catch_and_name_text)
        self.contextUpdated.connect(self.__update_bounds)

    def is_float(self) -> bool:
        return self.__isFloat

    def set_float(self, isFloat: bool):
        self.__isFloat = isFloat
        self.contextUpdated.emit()

    def __update_bounds(self):
        isFloat = self.__isFloat
        
        if isFloat:
            self.setDecimals(12)
            self.setRange(
                -3.402823466e+38,
                3.402823466e+38
            )
        else:
            self.setDecimals(16)
            self.setRange(
                -1.7976931348623158e+308,
                1.7976931348623158e+308
            )

        lineEdit = self.__lineEdit
        lineEdit.min = self.minimum()
        lineEdit.max = self.maximum()

    def __update_value(self, offset: float):
        _min = self.minimum()
        _max = self.maximum()
        value = self.value() + offset
        if self.wrapping():
            if value > _max:
                value = _min + (value - _max)
            elif value < _min:
                value = _max + (value - _min)
        else:
            value = min(max(value, _min), _max)
        self.setValue(value)

    def __catch_and_name_text(self, value: float):
        self.valueChangedExplicit.emit(self, value)


class SpinBoxDragInt(QSpinBox):
    valueChangedExplicit: SignalInstance = Signal(QSpinBox, int)
    contextUpdated: SignalInstance = Signal()

    class IntSize(IntEnum):
        BYTE = 1
        SHORT = 2
        WORD = 4
        LONG = 8

    def __init__(self, intSize: IntSize = IntSize.WORD, signed: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)

        lineEdit = SpinBoxLineEdit(False, 0, 0)
        lineEdit.dragOffsetChanged.connect(self.__update_value)
        self.__lineEdit = lineEdit
        self.setLineEdit(lineEdit)

        self.__signed = signed
        self.__intSize = intSize
        self.__update_bounds()

        self.valueChanged.connect(self.__catch_and_name_text)
        self.contextUpdated.connect(self.__update_bounds)

    def is_signed(self) -> bool:
        return self.__signed

    def set_signed(self, signed: bool):
        self.__signed = signed
        self.contextUpdated.emit()

    def int_size(self) -> IntSize:
        return self.__intSize

    def set_int_size(self, size: IntSize):
        self.__intSize = size
        self.contextUpdated.emit()

    def __update_bounds(self):
        intSize = self.__intSize
        signed = self.__signed
        
        if signed or True:
            if intSize == SpinBoxDragInt.IntSize.BYTE:
                self.setMinimum(-0x80)
                self.setMaximum(0x7F)
            elif intSize == SpinBoxDragInt.IntSize.SHORT:
                self.setMinimum(-0x8000)
                self.setMaximum(0x7FFF)
            elif intSize == SpinBoxDragInt.IntSize.WORD:
                self.setMinimum(-0x80000000)
                self.setMaximum(0x7FFFFFFF)
            elif intSize == SpinBoxDragInt.IntSize.LONG:
                self.setMinimum(-0x8000000000000000)
                self.setMaximum(0x7FFFFFFFFFFFFFFF)
        else:
            self.setMinimum(0)
            if intSize == SpinBoxDragInt.IntSize.BYTE:
                self.setMaximum(0xFF)
            elif intSize == SpinBoxDragInt.IntSize.SHORT:
                self.setMaximum(0xFFFF)
            elif intSize == SpinBoxDragInt.IntSize.WORD:
                self.setMaximum(0xFFFFFFFF)
            elif intSize == SpinBoxDragInt.IntSize.LONG:
                self.setMaximum(0xFFFFFFFFFFFFFFFF)

        lineEdit = self.__lineEdit
        lineEdit.min = self.minimum()
        lineEdit.max = self.maximum()

    def __update_value(self, offset: float):
        offset = int(offset)
        _min = self.minimum()
        _max = self.maximum()
        value = self.value() + offset
        if self.wrapping():
            if value > _max:
                value = _min + (value - _max)
            elif value < _min:
                value = _max + (value - _min)
        else:
            value = min(max(value, _min), _max)
        self.setValue(value)

    def __catch_and_name_text(self, value: int):
        self.valueChangedExplicit.emit(self, value)