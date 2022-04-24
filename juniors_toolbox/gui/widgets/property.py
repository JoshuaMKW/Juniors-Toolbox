from abc import ABC, abstractmethod
from ctypes.wintypes import BYTE, SHORT
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, SignalInstance, Slot
from PySide6.QtWidgets import QWidget, QGridLayout, QFormLayout, QComboBox, QLabel, QFrame

from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.gui.widgets import ABCMetaWidget
from juniors_toolbox.objects.template import AttributeType
from juniors_toolbox.utils.types import RGB8, RGBA8, BasicColors, Transform, Vec3f
from juniors_toolbox.utils import clamp


class ValueProperty(QWidget, ABC, metaclass=ABCMetaWidget):
    """
    Represents an abstract widget that interfaces a property
    """
    valueChanged: SignalInstance = Signal(QWidget, object)
    IndentionWidth = 20

    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name = name
        self._value = None
        self._resetValue = None
        self._readOnly = readOnly
        self.setObjectName(name)

        self.valueChanged.connect(self.set_inputs)
        self.construct()

    def get_name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name

    def get_value(self) -> object:
        return self._value

    def set_value(self, value: object):
        self._value = value
        self.valueChanged.emit(self, value)

    def set_reset_value(self, value: object):
        self._resetValue = value

    def get_nested_depth(self) -> int:
        i = 0
        parent = self.parent()
        if not isinstance(parent, ValueProperty):
            return 0
        while parent:
            i += 1
            parent = parent.parent()
            if not isinstance(parent, ValueProperty):
                break
        return i

    def is_read_only(self) -> bool:
        return self._readOnly

    def reset(self):
        self.set_value(self._resetValue)

    @abstractmethod
    def construct(self): ...

    @abstractmethod
    @Slot(QWidget, object)
    def set_inputs(self): ...



class BoolProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = False

    def construct(self):
        lineEdit = QComboBox()
        lineEdit.addItem("False")
        lineEdit.addItem("True")
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setCurrentIndex(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.currentIndexChanged.connect(lambda value: self.set_value(bool(value)))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setCurrentIndex(int(self.get_value()))
        self.__input.blockSignals(False)

    def get_value(self) -> bool:
        return super().get_value()

    def set_value(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Value is not an bool type")
        super().set_value(value)


class ByteProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed
        self._resetValue = 0

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.BYTE,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setValue(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -128, 127) if self._signed else clamp(value, 0, 255)
        super().set_value(value)


class ShortProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed
        self._resetValue = 0

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.SHORT,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setValue(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -32768, 32767) if self._signed else clamp(value, 0, 65535)
        super().set_value(value)


class IntProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._signed = signed
        self._resetValue = 0

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.WORD,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setValue(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int):
        if not isinstance(value, int):
            raise ValueError("Value is not an int type")

        value = clamp(
            value, -0x80000000, 0x7FFFFFFF) if self._signed else clamp(value, 0, 0xFFFFFFFF)
        super().set_value(value)


class FloatProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=True, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setValue(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)


class DoubleProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=False, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setValue(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)


class StringProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = ExplicitLineEdit(
            self.get_name(), ExplicitLineEdit.FilterKind.STR)
        lineEdit.setText("")
        lineEdit.setCursorPosition(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.textChangedNamed.connect(lambda _, value: self.set_value(value))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setText(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")

        value = clamp(
            value, -0x80000000, 0x7FFFFFFF) if self._signed else clamp(value, 0, 0xFFFFFFFF)
        super().set_value(value)


class Vector3Property(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = Vec3f.zero

    def construct(self):
        propertyName = self.get_name()

        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 0, 0, 0)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)
        self.__xyzInputs: List[SpinBoxDragDouble] = []
        for i in range(3):
            axis = "XYZ"[i]
            spinBox = SpinBoxDragDouble(isFloat=True)
            spinBox.setObjectName(f"{propertyName}.{axis}")
            spinBox.setMinimumWidth(20)
            spinBox.setValue(0)
            entry = QFormLayout()
            entry.addRow(axis, spinBox)
            entry.setRowWrapPolicy(QFormLayout.WrapLongRows)
            entry.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            containerLayout.addLayout(entry, 0, i, 1, 1)
            containerLayout.setColumnStretch(i, 0)
            self.__xyzInputs.append(spinBox)
        containerLayout.setEnabled(not self.is_read_only())

        self.setLayout(containerLayout)

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


class TransformProperty(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = Transform()

    def construct(self):
        propertyName = self.get_name()

        layout = FrameLayout(propertyName)

        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 0, 0, 0)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)
        self.__trsInputs: List[Vector3Property] = []
        for i in range(3):
            field = ("Translation", "Rotation", "Scale")[i]
            prop = Vector3Property(field, False, self)
            self.__trsInputs.append(prop)
            entry = QFormLayout()
            entry.addRow(field, prop)
            entry.setRowWrapPolicy(QFormLayout.WrapLongRows)
            entry.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            containerLayout.addWidget(entry, i, 0, 1, 1)
        containerLayout.setEnabled(not self.is_read_only())

        layout.setLayout(containerLayout)
        self.setLayout(layout)

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


class RGBA8Property(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGBA8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        colorbutton = ColorButton("", color=RGBA8(BasicColors.WHITE))
        colorbutton.setFrameStyle(QFrame.Box)
        colorbutton.setMinimumHeight(20)
        colorbutton.setObjectName(self.get_name())
        colorbutton.colorChanged.connect(
            lambda _, value: self.set_value(value))
        self.__input = colorbutton
        layout.addWidget(colorbutton)
        self.setLayout(layout)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.__input.blockSignals(True)
        self.__input.setColor(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> RGBA8:
        return super().get_value()

    def set_value(self, value: RGBA8):
        if not isinstance(value, RGBA8):
            raise ValueError("Value is not a RGBA8 type")
        super().set_value(value)


class RGB8Property(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGB8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        colorbutton = ColorButton("", color=RGBA8(BasicColors.WHITE))
        
        colorbutton.setFrameStyle(QFrame.Box)
        colorbutton.setMinimumHeight(20)
        colorbutton.setObjectName(self.get_name())
        colorbutton.colorChanged.connect(
            lambda _, value: self.set_value(value))
        self.__input = colorbutton
        layout.addWidget(colorbutton)
        self.setLayout(layout)

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


class RGB32Property(ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        raise NotImplementedError("RGB32 has not been implemented as a property yet")


class PropertyFactory():
    @staticmethod
    def create_property(
        *,
        name: str,
        valueType: AttributeType,
        value: Optional[object] = None,
        readOnly: bool = False
    ):
        """
        Creates a property. `valueType` must corrispond to `value`
        """
        if valueType == AttributeType.BOOL:
            prop = BoolProperty(
                name, readOnly
            )
        elif valueType == AttributeType.S8:
            prop = ByteProperty(
                name, readOnly, True
            )
        elif valueType in {AttributeType.BYTE, AttributeType.CHAR, AttributeType.U8}:
            prop = ByteProperty(
                name, readOnly, False
            )
        elif valueType == AttributeType.S16:
            prop = ShortProperty(
                name, readOnly, True
            )
        elif valueType == AttributeType.U16:
            prop = ShortProperty(
                name, readOnly, False
            )
        elif valueType in {AttributeType.S32, AttributeType.INT}:
            prop = IntProperty(
                name, readOnly, True
            )
        elif valueType == AttributeType.U32:
            prop = IntProperty(
                name, readOnly, False
            )
        elif valueType in {AttributeType.F32, AttributeType.FLOAT}:
            prop = FloatProperty(
                name, readOnly
            )
        elif valueType in {AttributeType.F64, AttributeType.DOUBLE}:
            prop = DoubleProperty(
                name, readOnly
            )
        elif valueType in {AttributeType.STR, AttributeType.STRING}:
            prop = StringProperty(
                name, readOnly
            )
        elif valueType == AttributeType.VECTOR3:
            prop = Vector3Property(
                name, readOnly
            )
        elif valueType in {AttributeType.C_RGBA, AttributeType.C_RGBA8}:
            prop = RGBA8Property(
                name, readOnly
            )
        elif valueType == AttributeType.C_RGB8:
            prop = RGB8Property(
                name, readOnly
            )
        elif valueType == AttributeType.C_RGB32:
            prop = RGB32Property(
                name, readOnly
            )
        elif valueType == AttributeType.TRANSFORM:
            prop = TransformProperty(
                name, readOnly
            )

        prop.set_value(value)
        return prop


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
