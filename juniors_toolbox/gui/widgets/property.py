from abc import ABC, abstractmethod
from ctypes.wintypes import BYTE, SHORT
from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal, SignalInstance, Slot
from PySide6.QtWidgets import QWidget, QGridLayout, QFormLayout, QComboBox

from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.gui.widgets import ABCMetaWidget
from juniors_toolbox.objects.template import AttributeType
from juniors_toolbox.utils.types import Transform, Vec3f
from juniors_toolbox.utils import clamp


class ValuePropertyWidget(QWidget, ABC, metaclass=ABCMetaWidget):
    """
    Represents an abstract widget that interfaces a property
    """
    valueChanged: SignalInstance = Signal(QWidget, object)
    IndentionWidth = 20

    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__()
        self._name = name
        self._value = None
        self._readOnly = readOnly
        self._parent = parent
        self.setObjectName(name)

        self.valueChanged.connect(self.set_inputs)
        self.construct()

    def get_name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name

    def get_value(self) -> Any:
        return self._value

    def set_value(self, value: Any):
        self._value = value
        self.valueChanged.emit(self, value)

    def get_nested_depth(self) -> int:
        i = 0
        parent = self.parent()
        while parent:
            i += 1
            parent = parent.parent()
        return i

    def is_read_only(self) -> bool:
        return self._readOnly

    @abstractmethod
    def construct(self): ...

    @abstractmethod
    @Slot(QWidget, object)
    def set_inputs(self): ...

    @abstractmethod
    def reset(self): ...


class BoolProperty(ValuePropertyWidget):
    def construct(self):
        lineEdit = QComboBox()
        lineEdit.addItem("False")
        lineEdit.addItem("True")
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setCurrentIndex(0)

        entry = EntryLayout(
            f"{self.get_name()} (Layout)",
            lineEdit,
            bool,
            [lineEdit],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=180 + (self.IndentionWidth * self.get_nested_depth())
        )
        # lineEdit.currentIndexChanged.connect(
        #     lambda index: entry.updateFromChild(lineEdit, index))
        lineEdit.setEnabled(not self.is_read_only())
        self.__input = lineEdit

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.setCurrentIndex(int(self.get_value()))

    def get_value(self) -> bool:
        return super().get_value()

    def set_value(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Value is not an bool type")
        super().set_value(value)


class ByteProperty(ValuePropertyWidget):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.BYTE,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)

        entry = EntryLayout(
            f"{self.get_name()} (Layout)",
            lineEdit,
            int,
            [lineEdit],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=180 + (self.IndentionWidth * self.get_nested_depth())
        )

        lineEdit.valueChangedExplicit.connect(entry.updateFromChild)
        lineEdit.setEnabled(not self.is_read_only())
        self.__input = lineEdit

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.setValue(self.get_value())

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -128, 127) if self._signed else clamp(value, 0, 255)
        super().set_value(value)


class ShortProperty(ValuePropertyWidget):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.SHORT,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)

        entry = EntryLayout(
            f"{self.get_name()} (Layout)",
            lineEdit,
            int,
            [lineEdit],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=180 + (self.IndentionWidth * self.get_nested_depth())
        )

        lineEdit.valueChangedExplicit.connect(entry.updateFromChild)
        lineEdit.setEnabled(not self.is_read_only())
        self.__input = lineEdit

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.setValue(self.get_value())

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -32768, 32767) if self._signed else clamp(value, 0, 65535)
        super().set_value(value)


class IntProperty(ValuePropertyWidget):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.WORD,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)

        entry = EntryLayout(
            f"{self.get_name()} (Layout)",
            lineEdit,
            int,
            [lineEdit],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=180 + (self.IndentionWidth * self.get_nested_depth())
        )

        lineEdit.valueChangedExplicit.connect(entry.updateFromChild)
        lineEdit.setEnabled(not self.is_read_only())
        self.__input = lineEdit

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.setValue(self.get_value())

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -0x80000000, 0x7FFFFFFF) if self._signed else clamp(value, 0, 0xFFFFFFFF)
        super().set_value(value)


class StringProperty(ValuePropertyWidget):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed

    def construct(self):
        lineEdit = ExplicitLineEdit(self.get_name(), ExplicitLineEdit.FilterKind.STR)
        lineEdit.setText("")
        lineEdit.setCursorPosition(0)
        entry = EntryLayout(
            f"{self.get_name()} (Layout)",
            lineEdit,
            str,
            [lineEdit],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=180 + (self.IndentionWidth * self.get_nested_depth())
        )
        lineEdit.textChangedNamed.connect(entry.updateFromChild)
        lineEdit.setEnabled(not self.is_read_only())
        self.__input = lineEdit

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.setText(self.get_value())

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")

        value = clamp(
            value, -0x80000000, 0x7FFFFFFF) if self._signed else clamp(value, 0, 0xFFFFFFFF)
        super().set_value(value)


class Vector3Property(ValuePropertyWidget):
    def construct(self):
        propertyName = self.get_name()

        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 0, 0, 0)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)
        container = EntryLayout(
            self.get_name(),
            self,
            Vec3f,
            [],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=260
        )
        container.setObjectName(f"{propertyName} (Container)")
        self.__xyzInputs: List[SpinBoxDragDouble] = []
        for i in range(3):
            axis = "XYZ"[i]
            spinBox = SpinBoxDragDouble(isFloat=True)
            spinBox.setObjectName(f"{propertyName}.{axis}")
            spinBox.setMinimumWidth(20)
            spinBox.setValue(0)
            entry = EntryLayout(
                axis,
                spinBox,
                float,
                [],
                labelWidth=14,
                newlining=False,
                labelFixed=True
            )
            containerLayout.addLayout(entry, 0, i, 1, 1)
            containerLayout.setColumnStretch(i, 0)
            container.addDirectChild(spinBox)
            self.__xyzInputs.append(spinBox)
        self.setLayout(containerLayout)
        container.setEnabled(not self.is_read_only())

    @Slot(QWidget, object)
    def set_inputs(self):
        for i, _input in enumerate(self.__xyzInputs):
            _input.setValue(self.get_value()[i])

    def get_value(self) -> Vec3f:
        return super().get_value()

    def set_value(self, value: Vec3f):
        if not isinstance(value, Vec3f):
            raise ValueError("Value is not a Vec3f type")
        super().set_value(value)


class TransformProperty(ValuePropertyWidget):
    def construct(self):
        propertyName = self.get_name()

        layout = FrameLayout(propertyName)
        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 0, 0, 0)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)
        container = EntryLayout(
            self.get_name(),
            self,
            Vec3f,
            [],
            labelWidth=100 - (self.IndentionWidth * self.get_nested_depth()),
            minEntryWidth=260
        )
        container.setObjectName(f"{propertyName} (Container)")
        self.__trsInputs: List[Vector3Property] = []
        for i in range(3):
            field = ("Translation", "Rotation", "Scale")[i]
            self.__trsInputs.append(Vector3Property(field, self.is_read_only(), self))
        self.setLayout(layout)
        container.setEnabled(not self.is_read_only())

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__trsInputs[0].set_value(self.get_value().translation)
        self.__trsInputs[1].set_value(self.get_value().rotation)
        self.__trsInputs[2].set_value(self.get_value().scale)

    def get_value(self) -> Transform:
        return super().get_value()

    def set_value(self, value: Transform):
        if not isinstance(value, Transform):
            raise ValueError("Value is not a Transform type")
        super().set_value(value)


def create_single_entry(
    attribute: GameObject.Value,
    nestedDepth: int = 0,
    indentWidth: int = 25,
    readOnly: bool = False
):
    _qualname = attribute.name
    _attrname = _qualname.split(".")[-1]
    _attrtype = attribute.type
    _attrvalue = attribute.value

    if _attrtype not in {
        AttributeType.BOOL,
        AttributeType.BYTE,
        AttributeType.CHAR,
        AttributeType.S8,
        AttributeType.U8,
        AttributeType.S16,
        AttributeType.U16,
        AttributeType.S32,
        AttributeType.INT,
        AttributeType.U32,
        AttributeType.F32,
        AttributeType.FLOAT,
        AttributeType.F64,
        AttributeType.DOUBLE,
        AttributeType.STR,
        AttributeType.STRING
    }:
        print(_attrtype)
        return None

    layout = QFormLayout()
    layout.setObjectName("EntryForm " + _attrname)
    if _attrtype in {
        AttributeType.STR,
        AttributeType.STRING
    }:
        lineEdit = ExplicitLineEdit(_attrname, ExplicitLineEdit.FilterKind.STR)
        lineEdit.setText(_attrvalue)
        lineEdit.setCursorPosition(0)
        entry = EntryLayout(
            _attrname,
            lineEdit,
            attribute.type.to_type(),
            [lineEdit],
            labelWidth=100 - (indentWidth * nestedDepth),
            minEntryWidth=180 + (indentWidth * nestedDepth)
        )
        lineEdit.textChangedNamed.connect(entry.updateFromChild)
        lineEdit.setEnabled(not readOnly)
    elif _attrtype == AttributeType.BOOL:
        lineEdit = QComboBox()
        lineEdit.addItem("False")
        lineEdit.addItem("True")
        lineEdit.setObjectName(attribute.name)
        lineEdit.setMinimumWidth(20)
        lineEdit.setCurrentIndex(int(_attrvalue))
        entry = EntryLayout(
            _attrname,
            lineEdit,
            attribute.type.to_type(),
            [lineEdit],
            labelWidth=100 - (indentWidth * nestedDepth),
            minEntryWidth=180 + (indentWidth * nestedDepth)
        )
        lineEdit.currentIndexChanged.connect(
            lambda index: entry.updateFromChild(lineEdit, index))
        lineEdit.setEnabled(not readOnly)
    else:
        if _attrtype in {
            AttributeType.F32,
            AttributeType.FLOAT,
            AttributeType.F64,
            AttributeType.DOUBLE
        }:
            lineEdit = SpinBoxDragDouble(isFloat=True)
            lineEdit.setObjectName(attribute.name)
            lineEdit.setMinimumWidth(20)
            lineEdit.setValue(_attrvalue)
        else:
            lineEdit = SpinBoxDragInt(
                intSize=SpinBoxDragInt.IntSize(attribute.type.get_size()),
                signed=attribute.type.is_signed()
            )
            lineEdit.setObjectName(attribute.name)
            lineEdit.setMinimumWidth(20)
            lineEdit.setValue(_attrvalue)
        entry = EntryLayout(
            _attrname,
            lineEdit,
            attribute.type.to_type(),
            [lineEdit],
            labelWidth=100 - (indentWidth * nestedDepth),
            minEntryWidth=180 + (indentWidth * nestedDepth)
        )
        lineEdit.valueChangedExplicit.connect(entry.updateFromChild)
        lineEdit.setEnabled(not readOnly)

    entry.setObjectName(attribute.name)
    return entry
