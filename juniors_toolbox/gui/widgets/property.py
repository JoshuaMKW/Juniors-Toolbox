from abc import ABC, abstractmethod
from ctypes.wintypes import BYTE, SHORT
from optparse import Option
from typing import Any, List, Optional, Type

from PySide6.QtCore import Qt, Signal, SignalInstance, Slot
from PySide6.QtWidgets import QWidget, QGridLayout, QFormLayout, QComboBox, QLabel, QFrame, QLineEdit

from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton, ColorButtonRGB8, ColorButtonRGBA8
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.gui.widgets import ABCWidget
from juniors_toolbox.objects.value import QualifiedName, ValueType
from juniors_toolbox.utils.gx import color
from juniors_toolbox.utils.types import RGB8, RGBA8, BasicColors, Transform, Vec3f
from juniors_toolbox.utils import clamp


class A_ValueProperty(QWidget, ABCWidget):
    """
    Represents an abstract widget that interfaces a property
    """
    valueChanged = Signal(QWidget, object)
    IndentionWidth = 20

    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._value = None
        self._resetValue = None
        self._readOnly = readOnly
        self._parent: Optional["A_ValueProperty"] = None
        self.setObjectName(name)

        self.valueChanged.connect(self.set_inputs)
        self.construct()

    def get_qualified_name(self) -> QualifiedName:
        """
        Get the full formatted name of this `Member`, as is scoped from its parents
        """
        scopes = [self.get_name()]
        parent = self.get_parent()
        while parent is not None:
            scopes.append(parent.get_formatted_name())
            parent = parent.get_parent()
        return QualifiedName(*scopes[::-1])

    def get_name(self) -> str:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name

    def get_value(self) -> object:
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = value
        self.valueChanged.emit(self, value)

    def set_reset_value(self, value: Any) -> None:
        self._resetValue = value

    def get_nested_depth(self) -> int:
        i = 0
        parent = self.parent()
        if not isinstance(parent, A_ValueProperty):
            return 0
        while parent:
            i += 1
            parent = parent.parent()
            if not isinstance(parent, A_ValueProperty):
                break
        return i

    def is_read_only(self) -> bool:
        return self._readOnly

    def reset(self) -> None:
        self.set_value(self._resetValue)

    def get_parent_property(self) -> "A_ValueProperty":
        return self._parent

    def set_parent_property(self, prop: "A_ValueProperty"):
        self._parent = prop
        prop.add_property(self)

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
    @Slot(QWidget, object)
    def set_inputs(self) -> None: ...


class BoolProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, parent)
        self._resetValue = False

    def construct(self) -> None:
        lineEdit = QComboBox()
        lineEdit.addItem("False")
        lineEdit.addItem("True")
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setCurrentIndex(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.currentIndexChanged.connect(
            lambda value: self.set_value(bool(value)))
        self.__input = lineEdit

        entry = QGridLayout()
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self) -> None:
        self.__input.blockSignals(True)
        self.__input.setCurrentIndex(int(self.get_value()))
        self.__input.blockSignals(False)

    def get_value(self) -> bool:
        return bool(super().get_value())

    def set_value(self, value: Any) -> None:
        if not isinstance(value, bool):
            raise ValueError("Value is not an bool type")
        super().set_value(value)


class ByteProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, parent)
        self._signed = signed
        self._resetValue = 0

    def construct(self) -> None:
        lineEdit = SpinBoxDragInt(
            intSize=int(SpinBoxDragInt.IntSize.BYTE),
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(20)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
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


class ShortProperty(A_ValueProperty):
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
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
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


class IntProperty(A_ValueProperty):
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
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
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


class FloatProperty(A_ValueProperty):
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
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
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


class DoubleProperty(A_ValueProperty):
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
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
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


class StringProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = QLineEdit(
            self.get_name(), QLineEdit.FilterKind.STR)
        lineEdit.setText("")
        lineEdit.setCursorPosition(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.textChangedNamed.connect(
            lambda _, value: self.set_value(value))
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


class Vector3Property(A_ValueProperty):
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


class TransformProperty(A_ValueProperty):
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


class RGBA8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGBA8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        colorbutton = ColorButtonRGBA8()
        colorbutton.set_color(RGBA8(BasicColors.WHITE))
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
        self.__input.set_color(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> RGBA8:
        return super().get_value()

    def set_value(self, value: RGBA8):
        if not isinstance(value, RGBA8):
            raise ValueError("Value is not a RGBA8 type")
        super().set_value(value)


class RGB8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGB8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        colorbutton = ColorButtonRGB8()
        colorbutton.set_color(RGB8(BasicColors.WHITE))
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
        self.__input.set_color(self.get_value())
        self.__input.blockSignals(False)

    def get_value(self) -> RGB8:
        return super().get_value()

    def set_value(self, value: RGB8):
        if not isinstance(value, RGB8):
            raise ValueError("Value is not a RGB8 type")
        super().set_value(value)


class RGB32Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        raise NotImplementedError(
            "RGB32 has not been implemented as a property yet")


class StructProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, parent)
        self._frameLayout = FrameLayout(title=name)
        self._properties: dict[str, A_ValueProperty] = {}

    def get_property(self, name: QualifiedName) -> Optional["A_ValueProperty"]:
        qualname = str(name)
        if qualname in self._properties:
            return self._properties[qualname]

        def _search(prop: "StructProperty") -> Optional["A_ValueProperty"]:
            for p in prop._properties.values():
                if p.get_qualified_name().scopes(name) and isinstance(p, StructProperty):
                    return _search(p)
            return None

        return _search(self)

    def add_property(self, prop: "A_ValueProperty"):
        if not isinstance(prop, A_ValueProperty):
            raise TypeError("StructProperty can only contain properties")
        self._frameLayout.addWidget(prop)
        self._properties[prop.get_name()] = prop
        prop._parent = self


class PropertyFactory():
    @staticmethod
    def create_property(
        *,
        name: str,
        valueType: ValueType,
        value: Optional[object] = None,
        readOnly: bool = False
    ):
        """
        Creates a property. `valueType` must corrispond to `value`
        """
        if valueType == ValueType.BOOL:
            prop = BoolProperty(
                name, readOnly
            )
        elif valueType == ValueType.S8:
            prop = ByteProperty(
                name, readOnly, True
            )
        elif valueType in {ValueType.BYTE, ValueType.CHAR, ValueType.U8}:
            prop = ByteProperty(
                name, readOnly, False
            )
        elif valueType == ValueType.S16:
            prop = ShortProperty(
                name, readOnly, True
            )
        elif valueType == ValueType.U16:
            prop = ShortProperty(
                name, readOnly, False
            )
        elif valueType in {ValueType.S32, ValueType.INT}:
            prop = IntProperty(
                name, readOnly, True
            )
        elif valueType == ValueType.U32:
            prop = IntProperty(
                name, readOnly, False
            )
        elif valueType in {ValueType.F32, ValueType.FLOAT}:
            prop = FloatProperty(
                name, readOnly
            )
        elif valueType in {ValueType.F64, ValueType.DOUBLE}:
            prop = DoubleProperty(
                name, readOnly
            )
        elif valueType in {ValueType.STR, ValueType.STRING}:
            prop = StringProperty(
                name, readOnly
            )
        elif valueType == ValueType.VECTOR3:
            prop = Vector3Property(
                name, readOnly
            )
        elif valueType in {ValueType.C_RGBA, ValueType.C_RGBA8}:
            prop = RGBA8Property(
                name, readOnly
            )
        elif valueType == ValueType.C_RGB8:
            prop = RGB8Property(
                name, readOnly
            )
        elif valueType == ValueType.C_RGB32:
            prop = RGB32Property(
                name, readOnly
            )
        elif valueType == ValueType.TRANSFORM:
            prop = TransformProperty(
                name, readOnly
            )

        prop.set_value(value)
        return prop
