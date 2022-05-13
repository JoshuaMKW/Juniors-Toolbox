from enum import Enum
from genericpath import isfile
import time
from turtle import title

from typing import List, Optional, Union

from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer, Signal, SignalInstance, Property, QPoint, QPointF, Slot
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QMouseEvent, QEventPoint
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QPushButton, QDoubleSpinBox, QSpinBox, QApplication,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)
from enum import IntEnum


class SpinBoxLineEdit(QLineEdit):
    dragOffsetChanged = Signal(float)
    borderlessChanged = Signal(bool)

    def __init__(self, isFloat: bool, _min: int, _max: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._klass_ = float if isFloat else int
        self._min = float(_min)
        self._max = float(_max)
        self.__mouseLastPos: Optional[QPoint] = None
        self.__mouseLoopCounter = [0, 0]
        self._startValue = None

    @Slot(QMouseEvent)
    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MiddleButton:
            self.__mouseLastPos = event.pos()
            self.__mouseLoopCounter = [0, 0]
            self._startValue = self._klass_(self.text())
            self.selectAll()

    @Slot(QMouseEvent)
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)

        if self.__mouseLastPos is None:
            return

        self.setCursor(Qt.SizeHorCursor)

        ePos = event.pos()
        mPos = self.__mouseLastPos
        wPos = self.pos()

        from juniors_toolbox.gui.application import JuniorsToolbox
        window = JuniorsToolbox.get_instance_window()
        windowSize = window.size()
        titleHeight = QApplication.style().pixelMetric(QStyle.PM_TitleBarHeight)

        point = event.point(0)
        pointPos = self.mapTo(window, point.position())
        
        xLooped = 0
        if pointPos.x() < 0.0:
            self.__mouseLoopCounter[0] -= 1
            QCursor.setPos(
                (window.pos().x() + windowSize.width()) - 1,
                QCursor.pos().y()
            )
            xLooped = -1
        elif pointPos.x() > windowSize.width():
            self.__mouseLoopCounter[0] += 1
            QCursor.setPos(
                window.pos().x() + 1,
                QCursor.pos().y()
            )
            xLooped = 1
        if pointPos.y() < 0.0:
            self.__mouseLoopCounter[1] = min(max(self.__mouseLoopCounter[1] - 1, -2), 4)
            QCursor.setPos(
                QCursor.pos().x(),
                (window.pos().y() + windowSize.height() + titleHeight) - 1,
            )
        elif pointPos.y() > windowSize.height():
            self.__mouseLoopCounter[1] = min(max(self.__mouseLoopCounter[1] + 1, -2), 4)
            QCursor.setPos(
                QCursor.pos().x(),
                window.pos().y() + titleHeight + 6,
            )
        
        if self._klass_ == float:
            minDif = 0.0000000000000001
        else:
            minDif = 1

        yDiff = (wPos.y() - ((windowSize.height() - titleHeight) * self.__mouseLoopCounter[1])) - ePos.y()
        xDiff = (ePos.x() - mPos.x()) + windowSize.width() * xLooped
        multiplier = max(pow(1.0 + yDiff / windowSize.height(), 13), minDif / 50)
        valueOffset = self._klass_(xDiff) * multiplier
        if abs(valueOffset) >= minDif:
            self.dragOffsetChanged.emit(valueOffset)
            self.__mouseLastPos = ePos

        event.accept()

    @Slot(QMouseEvent)
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self.__mouseLastPos = None
            self.unsetCursor()

        super().mouseReleaseEvent(event)

class SpinBoxDragDouble(QDoubleSpinBox):
    valueChangedExplicit = Signal(QDoubleSpinBox, float)
    contextUpdated = Signal()

    def __init__(self, isFloat: bool = True, parent: Optional[QWidget] = None) -> None:
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

    def set_float(self, isFloat: bool) -> None:
        self.__isFloat = isFloat
        self.contextUpdated.emit()

    def __update_bounds(self) -> None:
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
        lineEdit._min = self.minimum()
        lineEdit._max = self.maximum()

    def __update_value(self, offset: float) -> None:
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

    def __catch_and_name_text(self, value: float) -> None:
        self.valueChangedExplicit.emit(self, value)

    def textFromValue(self, val: float) -> str:
        return str(val)


class SpinBoxDragInt(QSpinBox):
    valueChangedExplicit = Signal(QSpinBox, int)
    contextUpdated = Signal()

    class IntSize(IntEnum):
        BYTE = 1
        SHORT = 2
        WORD = 4
        LONG = 8

    def __init__(self, intSize: IntSize = IntSize.WORD, signed: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWrapping(True)

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

    def set_signed(self, signed: bool = True) -> None:
        self.__signed = signed
        self.contextUpdated.emit()

    def int_size(self) -> IntSize:
        return self.__intSize

    def set_int_size(self, size: IntSize) -> None:
        self.__intSize = size
        self.contextUpdated.emit()

    def __update_bounds(self) -> None:
        intSize = self.__intSize
        signed = self.__signed
        
        if signed:
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
            if intSize == SpinBoxDragInt.IntSize.BYTE:
                self.setMinimum(0)
                self.setMaximum(0x7F)
            elif intSize == SpinBoxDragInt.IntSize.SHORT:
                self.setMinimum(0)
                self.setMaximum(0x7FFF)
            elif intSize == SpinBoxDragInt.IntSize.WORD:
                self.setMinimum(0)
                self.setMaximum(0x7FFFFFFF)
            elif intSize == SpinBoxDragInt.IntSize.LONG:
                self.setMinimum(0)
                self.setMaximum(0x7FFFFFFFFFFFFFFF)


        lineEdit = self.__lineEdit
        lineEdit._min = self.minimum()
        lineEdit._max = self.maximum()

    def __update_value(self, offset: float) -> None:
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

    def __catch_and_name_text(self, value: int) -> None:
        self.valueChangedExplicit.emit(self, value)