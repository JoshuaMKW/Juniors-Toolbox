from abc import ABC, abstractmethod
from ctypes.wintypes import BYTE, SHORT
from optparse import Option
import time
from typing import Any, Iterable, List, Optional, Sequence, Type

from PySide6.QtGui import QPainter, QPaintEvent, QStandardItemModel, QPalette
from PySide6.QtCore import Qt, Signal, SignalInstance, Slot, QModelIndex
from PySide6.QtWidgets import QWidget, QGridLayout, QFormLayout, QComboBox, QLabel, QFrame, QLineEdit, QStyleOptionComboBox, QGroupBox

from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton, ColorButtonRGB8, ColorButtonRGBA8
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragHex, SpinBoxDragInt
from juniors_toolbox.gui.widgets import ABCWidget
from juniors_toolbox.objects.value import QualifiedName, ValueType
from juniors_toolbox.utils.gx import color
from juniors_toolbox.utils.types import RGB8, RGBA8, BasicColors, Quaternion, Transform, Vec3f
from juniors_toolbox.utils import clamp


class A_ValueProperty(QWidget, ABCWidget):
    """
    Represents an abstract widget that interfaces a property
    """
    valueChanged = Signal(QWidget, object)
    IndentionWidth = 10

    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional["A_ValueProperty"] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._value: Any = value
        self._resetValue: Any = value
        self._readOnly = readOnly
        self._parent: Optional["A_ValueProperty"] = None

        self.setObjectName(name)
        self.construct()
        self.set_parent_property(parent)

        self.valueChanged.connect(self.set_inputs)

    def get_qualified_name(self) -> QualifiedName:
        """
        Get the full formatted name of this `Member`, as is scoped from its parents
        """
        scopes = [self.get_name()]
        parent = self.get_parent_property()
        while parent is not None:
            if not parent.is_array():
                scopes.append(parent.get_name())
            parent = parent.get_parent_property()
        return QualifiedName(*scopes[::-1])

    def get_name(self) -> str:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name

    def get_value(self) -> Any:
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = value
        self.valueChanged.emit(self, value)

    def set_reset_value(self, value: Any) -> None:
        self._resetValue = value

    def get_nested_depth(self) -> int:
        i = 0
        parent = self.get_parent_property()
        while parent:
            i += 1
            parent = parent.get_parent_property()
        return i

    def is_read_only(self) -> bool:
        return self._readOnly

    def is_container(self) -> bool:
        return False

    def is_array(self) -> bool:
        return False

    def reset(self) -> None:
        self.set_value(self._resetValue)

    def get_parent_property(self) -> Optional["A_ValueProperty"]:
        return self._parent

    def set_parent_property(self, prop: Optional["A_ValueProperty"]):
        self._parent = prop
        if prop is not None:
            prop.add_property(self)
        self._update_input_depth()

    def get_properties(self, *, deep: bool = True) -> Iterable["A_ValueProperty"]:
        return []

    def get_property(self, name: QualifiedName) -> Optional["A_ValueProperty"]:
        """
        name is treated as relative to this struct
        """
        return None

    def add_property(self, prop: "A_ValueProperty"):
        """
        Add a sub property to this property
        """
        pass

    @abstractmethod
    def construct(self) -> None: ...

    @abstractmethod
    def set_minimum_value(self, value: Any) -> None: ...

    @abstractmethod
    def set_maximum_value(self, value: Any) -> None: ...

    @abstractmethod
    def _update_input_depth(self) -> None: ...

    @abstractmethod
    @Slot(QWidget, object)
    def set_inputs(self) -> None: ...


class BoolProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, value, parent)
        self._resetValue = False

    def construct(self) -> None:
        lineEdit = QComboBox()
        lineEdit.addItem("False")
        lineEdit.addItem("True")
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setCurrentIndex(int(self._value))
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.currentIndexChanged.connect(
            lambda value: self.set_value(bool(value)))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self) -> None:
        self._input.blockSignals(True)
        self._input.setCurrentIndex(int(self.get_value()))
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> bool:
        return bool(super().get_value())

    def set_value(self, value: Any) -> None:
        if not isinstance(value, bool):
            raise ValueError("Value is not an bool type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class ByteProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, signed: bool = True, hexadecimal: bool = False, parent: Optional[QWidget] = None) -> None:
        self._signed = signed
        self._hex = hexadecimal
        super().__init__(name, readOnly, value, parent)
        self._resetValue = 0

    def construct(self) -> None:
        if self._hex:
            lineEdit = SpinBoxDragHex(
                intSize=SpinBoxDragInt.IntSize.BYTE,
                signed=False
            )
        else:
            lineEdit = SpinBoxDragInt(
                intSize=SpinBoxDragInt.IntSize.BYTE,
                signed=self._signed
            )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(self._value if self._value is not None else 0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        self._input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        self._input.setMaximum(value)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -128, 127) if self._signed else clamp(value, 0, 255)
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class ShortProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, signed: bool = True, hexadecimal: bool = False, parent: Optional[QWidget] = None):
        self._signed = signed
        self._hex = hexadecimal
        super().__init__(name, readOnly, value, parent)
        self._resetValue = 0

    def construct(self):
        if self._hex:
            lineEdit = SpinBoxDragHex(
                intSize=SpinBoxDragInt.IntSize.SHORT,
                signed=False
            )
        else:
            lineEdit = SpinBoxDragInt(
                intSize=SpinBoxDragInt.IntSize.SHORT,
                signed=self._signed
            )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(self._value if self._value is not None else 0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        self._input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        self._input.setMaximum(value)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -32768, 32767) if self._signed else clamp(value, 0, 65535)
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class IntProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, signed: bool = True, hexadecimal: bool = False, parent: Optional[QWidget] = None):
        self._signed = signed
        self._hex = hexadecimal
        super().__init__(name, readOnly, value, parent)
        self._resetValue = 0

    def construct(self):
        if self._hex:
            lineEdit = SpinBoxDragHex(
                intSize=SpinBoxDragInt.IntSize.WORD,
                signed=False
            )
        else:
            lineEdit = SpinBoxDragInt(
                intSize=SpinBoxDragInt.IntSize.WORD,
                signed=self._signed
            )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(self._value if self._value is not None else 0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        self._input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        self._input.setMaximum(value)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -0x80000000, 0x7FFFFFFF) if self._signed else clamp(value, 0, 0xFFFFFFFF)
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class FloatProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=True, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(self._value if self._value is not None else 0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        self._input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        self._input.setMaximum(value)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class DoubleProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=False, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(self._value if self._value is not None else 0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        self._input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        self._input.setMaximum(value)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class StringProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = QLineEdit(self.get_name())
        lineEdit.setText(self._value)
        lineEdit.setCursorPosition(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.textChanged.connect(self.set_value)
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setText(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class CommentProperty(A_ValueProperty):
    def __init__(self, name: str, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, True, value, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = QLabel(self.get_name())
        lineEdit.setText(self._value)
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setText(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class EnumProperty(A_ValueProperty):
    class _EnumFlagList(QComboBox):
        enumPressed = Signal()

        def __init__(self):
            super().__init__()
            self.view().pressed.connect(self.handleItemPressed)
            self.setModel(QStandardItemModel(self))
            self.setEditable(True)
            l = self.lineEdit()
            l.setReadOnly(True)
            l.textChanged.connect(self.setText)
            self._displayText = ""

        def handleItemPressed(self, index: QModelIndex):
            model: QStandardItemModel = self.model()
            item = model.itemFromIndex(index)
            if item.checkState() == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)
            self.__update_text()
            self.enumPressed.emit()

        def setText(self, text: str) -> None:
            l = self.lineEdit()
            l.blockSignals(True)
            l.setText(self._displayText)
            l.blockSignals(False)

        def get_value(self) -> int:
            model: QStandardItemModel = self.model()
            value = 0
            for i in range(model.rowCount()):
                item = model.item(i, 0)
                if item.checkState() == Qt.Checked:
                    value |= item.data(Qt.UserRole)
            return value

        def set_value(self, value: int):
            model: QStandardItemModel = self.model()
            for i in range(model.rowCount()):
                item = model.item(i, 0)
                if (value & item.data(Qt.UserRole)) != 0:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            self.__update_text()

        def addItems(self, texts: Sequence[str]) -> None:
            model: QStandardItemModel = self.model()
            row = model.rowCount()
            super().addItems(texts)
            for r in range(row, model.rowCount()):
                item = model.item(r, 0)
                item.setCheckable(True)
                item.setCheckState(Qt.Unchecked)

        def addItem(self, text: str, userData: Any = None) -> None:
            model: QStandardItemModel = self.model()
            row = model.rowCount()
            super().addItem(text, userData)
            item = model.item(row, 0)
            item.setCheckable(True)
            item.setCheckState(Qt.Unchecked)

        def __update_text(self):
            model: QStandardItemModel = self.model()
            texts: list[str] = []
            for i in range(model.rowCount()):
                item = model.item(i, 0)
                if item.checkState() == Qt.Checked:
                    texts.append(item.text())
            self._displayText = "|".join(texts)
            self.setText(self._displayText)

    class _EnumList(QComboBox):
        def get_value(self) -> int:
            return self.itemData(self.currentIndex(), Qt.UserRole)

        def set_value(self, value: int):
            model: QStandardItemModel = self.model()
            for i in range(model.rowCount()):
                item = model.item(i, 0)
                if value == item.data(Qt.UserRole):
                    self.setCurrentIndex(i)
                    break

    def __init__(self, name: str, readOnly: bool, value: Any, enumInfo: Optional[dict[str, Any]] = None, parent: Optional["A_ValueProperty"] = None) -> None:
        if enumInfo is None:
            enumInfo = {}
        self._enumInfo = enumInfo
        super().__init__(name, readOnly, value, parent)

    def construct(self) -> None:
        if self._enumInfo["Multi"] is True:
            self._checkList = EnumProperty._EnumFlagList()
            self._checkList.enumPressed.connect(
                lambda: self.__update_value_from_flags())
        else:
            self._checkList = EnumProperty._EnumList()
            self._checkList.currentIndexChanged.connect(
                lambda: self.__update_value_from_flags())

        self._checkList.blockSignals(True)
        for name, value in self._enumInfo["Flags"].items():
            self._checkList.addItem(name, value)
        self._checkList.blockSignals(False)

        entry = QGridLayout()
        entry.setContentsMargins(0, 4, 0, 4)
        entry.addWidget(self._checkList)

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._checkList.blockSignals(True)
        self._checkList.set_value(self.get_value())
        self._checkList.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int) -> None:
        super().set_value(value)

    def __update_value_from_flags(self):
        self.set_value(self._checkList.get_value())


class Vector3Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = Vec3f.zero

    def construct(self):
        propertyName = self.get_name()

        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 4, 0, 4)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)

        inputX = SpinBoxDragDouble(isFloat=True)
        inputY = SpinBoxDragDouble(isFloat=True)
        inputZ = SpinBoxDragDouble(isFloat=True)
        self._xyzInputs: List[SpinBoxDragDouble] = [inputX, inputY, inputZ]
        for i in range(3):
            axis = "XYZ"[i]
            spinBox = self._xyzInputs[i]
            spinBox.setObjectName(f"{propertyName}.{axis}")
            spinBox.setMinimumWidth(80)
            spinBox.setValue(self._value[i] if self._value is not None else 0)
            entry = QFormLayout()
            entry.addRow(axis, spinBox)
            entry.setRowWrapPolicy(QFormLayout.WrapLongRows)
            entry.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            containerLayout.addLayout(entry, 0, i, 1, 1)
            containerLayout.setColumnStretch(i, 0)
        inputX.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 0))
        inputY.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 1))
        inputZ.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 2))

        containerLayout.setEnabled(not self.is_read_only())

        self.setLayout(containerLayout)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.blockSignals(True)
        for i, _input in enumerate(self._xyzInputs):
            _input.setValue(self.get_value()[i])
        self.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        for input in self._xyzInputs:
            input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        for input in self._xyzInputs:
            input.setMaximum(value)

    def get_value(self) -> Vec3f:
        return super().get_value()

    def set_value(self, value: Vec3f):
        if not isinstance(value, Vec3f):
            raise ValueError("Value is not a Vec3f type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        for inputBox in self._xyzInputs:
            inputBox.setMinimumWidth(
                max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))

    def __update_axis(self, value: float, axis: int = 0):
        self.get_value()[axis] = value
        self.valueChanged.emit(self, self.get_value())


class RGBA8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = RGBA8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        colorbutton = ColorButtonRGBA8()
        colorbutton.set_color(self._value)
        colorbutton.setFrameStyle(QFrame.Box)
        colorbutton.setMinimumHeight(20)
        colorbutton.setObjectName(self.get_name())
        colorbutton.colorChanged.connect(
            lambda _, value: self.set_value(value))
        self._input = colorbutton
        layout.addWidget(colorbutton)
        self.setLayout(layout)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.set_color(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> RGBA8:
        return super().get_value()

    def set_value(self, value: RGBA8):
        if not isinstance(value, RGBA8):
            raise ValueError("Value is not a RGBA8 type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))


class RGB8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = RGB8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 4, 0, 4)
        colorbutton = ColorButtonRGB8()
        colorbutton.set_color(self._value)
        colorbutton.setFrameStyle(QFrame.Box)
        colorbutton.setMinimumHeight(20)
        colorbutton.setObjectName(self.get_name())
        colorbutton.colorChanged.connect(
            lambda _, value: self.set_value(value))
        self._input = colorbutton
        layout.addWidget(colorbutton)
        self.setLayout(layout)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.set_color(self.get_value())
        self._input.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> RGB8:
        return super().get_value()

    def set_value(self, value: RGB8):
        if not isinstance(value, RGB8):
            raise ValueError("Value is not a RGB8 type")
        super().set_value(value)


class RGB32Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        raise NotImplementedError(
            "RGB32 has not been implemented as a property yet")


class StructProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, value, parent)

    def construct(self) -> None:
        self._frameLayout = FrameLayout(title=self.get_name())
        self._frameLayout._main_v_layout.setContentsMargins(0, 4, 0, 4)
        self._frameLayout._content_layout.setContentsMargins(
            self.IndentionWidth, 0, 0, 0)

        self._formLayout = QFormLayout()
        self._formLayout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._formLayout.setFieldGrowthPolicy(
            QFormLayout.AllNonFixedFieldsGrow)
        self._formLayout.setContentsMargins(0, 4, 0, 4)
        self._frameLayout.addLayout(self._formLayout)

        self._properties: dict[str, A_ValueProperty] = {}

        self._mainLayout = QGridLayout()
        self._mainLayout.setContentsMargins(0, 0, 0, 4)
        self._mainLayout.addWidget(self._frameLayout)
        self.setLayout(self._mainLayout)

    def is_container(self) -> bool:
        return True

    def get_properties(self, *, deep: bool = True) -> Iterable[A_ValueProperty]:
        for prop in self._properties.values():
            yield prop
            if deep:
                yield from prop.get_properties()

    def get_property(self, name: QualifiedName) -> Optional[A_ValueProperty]:
        qualname = str(name)
        if qualname in self._properties:
            return self._properties[qualname]

        def _search(prop: "StructProperty") -> Optional[A_ValueProperty]:
            for p in prop._properties.values():
                if p.get_qualified_name() == name:
                    return p
                if p.get_qualified_name().scopes(name) and p.is_container():
                    return _search(p)
            return None

        return _search(self)

    def add_property(self, prop: A_ValueProperty):
        if not isinstance(prop, A_ValueProperty):
            raise TypeError("StructProperty can only contain properties")
        if prop.is_container():
            self._frameLayout.addWidget(prop)
            self._formLayout = QFormLayout()
            self._formLayout.setRowWrapPolicy(QFormLayout.WrapLongRows)
            self._formLayout.setFieldGrowthPolicy(
                QFormLayout.AllNonFixedFieldsGrow)
            self._formLayout.setContentsMargins(0, 4, 0, 4)
            self._frameLayout.addLayout(self._formLayout)
        else:
            self._formLayout.addRow(prop.get_name(), prop)
        self._properties[prop.get_name()] = prop
        prop._parent = self

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def set_value(self, value: Any) -> None:
        super().set_value(value)

    def get_value(self) -> Any:
        return super().get_value()

    def _update_input_depth(self) -> None:
        for prop in self.get_properties(deep=False):
            prop._update_input_depth()


class ArrayProperty(A_ValueProperty):
    IndentionWidth = 0
    sizeChanged = Signal(A_ValueProperty, int)

    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, sizeRef: Optional[A_ValueProperty] = None, parent: Optional["A_ValueProperty"] = None) -> None:
        super().__init__(name, readOnly, value, parent)
        self._sizeRef: Optional[A_ValueProperty] = None
        self._propCount = 0
        self.blockSignals(True)
        self.set_array_size(sizeRef)
        self.blockSignals(False)

    def construct(self) -> None:
        self._frame = QGroupBox()
        self._frame.setContentsMargins(0, 0, 0, 0)
        font = self._frame.font()
        font.setPointSize(6)
        self._frame.setFont(font)

        self._innerLayout = QGridLayout()
        self._innerLayout.setContentsMargins(2, 4, 2, 2)
        self._innerLayout.setSpacing(0)

        self._frame.setLayout(self._innerLayout)

        self._frameLayoutWidget: Optional[QWidget] = None

        self._properties: dict[str, A_ValueProperty] = {}

        self._mainLayout = QGridLayout()
        self._mainLayout.setContentsMargins(0, 0, 0, 0)
        self._mainLayout.setSpacing(0)
        self._mainLayout.addWidget(self._frame)
        self.setLayout(self._mainLayout)

        self.sizeChanged.connect(self.__adjust_properties)

    def is_container(self) -> bool:
        return True

    def is_array(self) -> bool:
        return True

    def get_properties(self, *, deep: bool = True) -> Iterable[A_ValueProperty]:
        for prop in self._properties.values():
            yield prop
            if deep:
                yield from prop.get_properties()

    def get_property(self, name: QualifiedName) -> Optional[A_ValueProperty]:
        qualname = str(name)
        if qualname in self._properties:
            return self._properties[qualname]

        def _search(prop: "StructProperty") -> Optional[A_ValueProperty]:
            for p in prop._properties.values():
                if p.get_qualified_name() == name:
                    return p
                if p.get_qualified_name().scopes(name) and p.is_container():
                    return _search(p)
            return None

        return _search(self)

    def set_array_size(self, sizeRef: Optional[ByteProperty | ShortProperty | IntProperty]):
        if self._sizeRef is not None:
            self._sizeRef.valueChanged.disconnect(self.__emit_size_change)
        self._sizeRef = sizeRef
        if sizeRef is not None:
            self.__check_ref()
            sizeRef._input.setMinimum(0)
            sizeRef._input.setMaximum(127)
            sizeRef.valueChanged.connect(self.__emit_size_change)
        self.__update_frame()
        self.__emit_size_change()

    def get_array_size(self) -> int:
        if self._sizeRef is not None:
            return self._sizeRef.get_value()
        return 0

    def get_property_count(self) -> int:
        return self._propCount

    def add_property(self, prop: A_ValueProperty):
        if not isinstance(prop, A_ValueProperty):
            raise TypeError("StructProperty can only contain properties")
        if prop.is_container():
            self._innerLayout.addWidget(prop)
            self._frameLayoutWidget = None
        else:
            if self._frameLayoutWidget is None:
                self._frameLayoutWidget = QWidget()
                self._formLayout = QFormLayout()
                self._formLayout.setContentsMargins(0, 4, 0, 4)
                self._formLayout.setSpacing(0)
                self._formLayout.setRowWrapPolicy(QFormLayout.WrapLongRows)
                self._formLayout.setFieldGrowthPolicy(
                    QFormLayout.AllNonFixedFieldsGrow)
                self._frameLayoutWidget.setLayout(self._formLayout)
                self._innerLayout.addWidget(self._frameLayoutWidget)
            self._formLayout.parentWidget().show()
            self._formLayout.addRow(prop.get_name(), prop)
        self._properties[prop.get_name()] = prop
        self._propCount += 1
        prop._parent = self._parent
        self.__adjust_properties(None, self.get_array_size())

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def set_value(self, value: Any) -> None:
        super().set_value(value)

    def get_value(self) -> Any:
        return super().get_value()

    def _update_input_depth(self) -> None:
        for prop in self.get_properties(deep=False):
            prop._update_input_depth()

    def __emit_size_change(self):
        self.__check_ref()
        self.sizeChanged.emit(self, self.get_array_size())

    def __update_frame(self):
        self._frame.setTitle(
            f"Size ref: {self._sizeRef.get_name()} ({self._sizeRef.get_value()})")
        if self._sizeRef is not None and self._sizeRef.get_value() > 0:
            if self.parent() is None:
                return
            self.show()
        else:
            self.hide()

    def __check_ref(self):
        if self._sizeRef.get_value() not in range(0, 128):
            print(
                f"Reference {self._sizeRef.get_qualified_name()} can't surpass 0-127, this is a safety measure")
            self._sizeRef.set_value(clamp(self._sizeRef.get_value(), 0, 127))

    @Slot(A_ValueProperty, int)
    def __adjust_properties(self, prop: "ArrayProperty", size: int):
        _count = 0
        for prop in self._properties.values():
            if prop.is_container():
                if _count < size:
                    prop.show()
                else:
                    prop.hide()
                _count += 1
            else:
                layout: QFormLayout = prop.parentWidget().layout()
                if _count < size:
                    prop.show()
                    layout.labelForField(prop).show()
                else:
                    prop.hide()
                    layout.labelForField(prop).hide()
                _count += 1

        self.__update_frame()


class TransformProperty(StructProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = Transform()

    def construct(self):
        super().construct()

        value = self.get_value()
        inputT = Vector3Property("Translation", False, value.translation)
        inputR = Vector3Property(
            "Rotation", False, value.rotation.to_euler())
        inputS = Vector3Property("Scale", False, value.scale)
        inputT.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 0))
        inputR.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 1))
        inputS.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 2))
        inputT.set_parent_property(self)
        inputR.set_parent_property(self)
        inputS.set_parent_property(self)
        self.__trsInputs: List[Vector3Property] = [inputT, inputR, inputS]

    def is_container(self) -> bool:
        return True

    @Slot(QWidget, object)
    def set_inputs(self):
        value = self.get_value()
        inputT = self.__trsInputs[0]
        inputR = self.__trsInputs[1]
        inputS = self.__trsInputs[2]
        inputT._value = value.translation
        inputR._value = value.rotation.to_euler()
        inputS._value = value.scale
        inputT.set_inputs()
        inputR.set_inputs()
        inputS.set_inputs()

    def set_minimum_value(self, value: Any) -> None:
        pass

    def set_maximum_value(self, value: Any) -> None:
        pass

    def get_value(self) -> Transform:
        return super().get_value()

    def set_value(self, value: Transform):
        if not isinstance(value, Transform):
            raise ValueError("Value is not a Transform type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        for prop in self.__trsInputs:
            prop._update_input_depth()

    def __update_trs(self, value: Vec3f, trs: int = 0):
        transform = self.get_value()
        if trs == 0:
            transform.translation = value
        elif trs == 1:
            transform.rotation = Quaternion.from_euler(value)
        elif trs == 2:
            transform.scale = value
        self.valueChanged.emit(self, transform)


class PropertyFactory():
    @staticmethod
    def create_property(
        *,
        name: str,
        valueType: ValueType,
        value: Optional[Any] = None,
        readOnly: bool = False,
        **kwargs
    ):
        """
        Creates a property. `valueType` must corrispond to `value`
        """
        hexadecimal = kwargs.get("hexadecimal", False)
        enumInfo = kwargs.get("enumInfo", {})

        if valueType == ValueType.BOOL:
            prop = BoolProperty(
                name, readOnly, value
            )
        elif valueType == ValueType.S8:
            prop = ByteProperty(
                name, readOnly, value, True, hexadecimal
            )
        elif valueType in {ValueType.BYTE, ValueType.CHAR, ValueType.U8}:
            prop = ByteProperty(
                name, readOnly, value, False, hexadecimal
            )
        elif valueType in {ValueType.S16, ValueType.SHORT}:
            prop = ShortProperty(
                name, readOnly, value, True, hexadecimal
            )
        elif valueType == ValueType.U16:
            prop = ShortProperty(
                name, readOnly, value, False, hexadecimal
            )
        elif valueType in {ValueType.S32, ValueType.INT}:
            prop = IntProperty(
                name, readOnly, value, True, hexadecimal
            )
        elif valueType == ValueType.U32:
            prop = IntProperty(
                name, readOnly, value, False, hexadecimal
            )
        elif valueType in {ValueType.F32, ValueType.FLOAT}:
            prop = FloatProperty(
                name, readOnly, value
            )
        elif valueType in {ValueType.F64, ValueType.DOUBLE}:
            prop = DoubleProperty(
                name, readOnly, value
            )
        elif valueType in {ValueType.STR, ValueType.STRING}:
            prop = StringProperty(
                name, readOnly, value
            )
        elif valueType == ValueType.COMMENT:
            prop = CommentProperty(
                name, value
            )
        elif valueType == ValueType.ENUM:
            prop = EnumProperty(
                name, readOnly, value, enumInfo
            )
        elif valueType == ValueType.VECTOR3:
            prop = Vector3Property(
                name, readOnly, value
            )
        elif valueType in {ValueType.C_RGBA, ValueType.C_RGBA8}:
            prop = RGBA8Property(
                name, readOnly, value
            )
        elif valueType == ValueType.C_RGB8:
            prop = RGB8Property(
                name, readOnly, value
            )
        elif valueType == ValueType.C_RGB32:
            prop = RGB32Property(
                name, readOnly, value
            )
        elif valueType == ValueType.TRANSFORM:
            prop = TransformProperty(
                name, readOnly, value
            )
        elif valueType == ValueType.STRUCT:
            prop = StructProperty(
                name, readOnly, value
            )
        return prop
