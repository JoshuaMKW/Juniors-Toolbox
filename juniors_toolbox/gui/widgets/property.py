from abc import ABC, abstractmethod
from ctypes.wintypes import BYTE, SHORT
from optparse import Option
from typing import Any, Iterable, List, Optional, Sequence, Type

from PySide6.QtGui import QPainter, QPaintEvent, QStandardItemModel, QPalette
from PySide6.QtCore import Qt, Signal, SignalInstance, Slot, QModelIndex
from PySide6.QtWidgets import QWidget, QGridLayout, QFormLayout, QComboBox, QLabel, QFrame, QLineEdit, QStyleOptionComboBox

from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton, ColorButtonRGB8, ColorButtonRGBA8
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
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
    IndentionWidth = 20

    def __init__(self, name: str, readOnly: bool, parent: Optional["A_ValueProperty"] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._value = None
        self._resetValue = None
        self._readOnly = readOnly
        self._parent: Optional["A_ValueProperty"] = None
        self.setObjectName(name)

        self.valueChanged.connect(self.set_inputs)
        self.construct()
        self.set_parent_property(parent)

    def get_qualified_name(self) -> QualifiedName:
        """
        Get the full formatted name of this `Member`, as is scoped from its parents
        """
        scopes = [self.get_name()]
        parent = self.get_parent_property()
        while parent is not None:
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
    def _update_input_depth(self) -> None: ...

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
        lineEdit.setMinimumWidth(80)
        lineEdit.setCurrentIndex(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.currentIndexChanged.connect(
            lambda value: self.set_value(bool(value)))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self) -> None:
        self._input.blockSignals(True)
        self._input.setCurrentIndex(int(self.get_value()))
        self._input.blockSignals(False)

    def get_value(self) -> bool:
        return bool(super().get_value())

    def set_value(self, value: Any) -> None:
        if not isinstance(value, bool):
            raise ValueError("Value is not an bool type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class ByteProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(name, readOnly, parent)
        self._signed = signed
        self._resetValue = 0

    def construct(self) -> None:
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.BYTE,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

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
            max(80 - (10 * self.get_nested_depth()), 0))


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
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

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
            max(80 - (10 * self.get_nested_depth()), 0))


class IntProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, signed: bool, parent: Optional[QWidget] = None):
        self._signed = signed
        self._resetValue = 0
        super().__init__(name, readOnly, parent)

    def construct(self):
        lineEdit = SpinBoxDragInt(
            intSize=SpinBoxDragInt.IntSize.WORD,
            signed=self._signed
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

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
            max(80 - (10 * self.get_nested_depth()), 0))


class FloatProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=True, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class DoubleProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = 0.0

    def construct(self):
        lineEdit = SpinBoxDragDouble(
            isFloat=False, parent=self
        )
        lineEdit.setObjectName(self.get_name())
        lineEdit.setMinimumWidth(80)
        lineEdit.setValue(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.valueChangedExplicit.connect(
            lambda _, value: self.set_value(value))
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setValue(self.get_value())
        self._input.blockSignals(False)

    def get_value(self) -> float:
        return super().get_value()

    def set_value(self, value: float):
        if not isinstance(value, float):
            raise ValueError("Value is not an float type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class StringProperty(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = QLineEdit(self.get_name())
        lineEdit.setText("")
        lineEdit.setCursorPosition(0)
        lineEdit.setEnabled(not self.is_read_only())
        lineEdit.textChanged.connect(self.set_value)
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setText(self.get_value())
        self._input.blockSignals(False)

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class CommentProperty(A_ValueProperty):
    def __init__(self, name: str, parent: Optional[QWidget] = None):
        super().__init__(name, True, parent)
        self._resetValue = ""

    def construct(self):
        lineEdit = QLabel(self.get_name())
        lineEdit.setText("")
        self._input = lineEdit

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(lineEdit)
        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.setText(self.get_value())
        self._input.blockSignals(False)

    def get_value(self) -> str:
        return super().get_value()

    def set_value(self, value: str):
        if not isinstance(value, str):
            raise ValueError("Value is not an str type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class EnumProperty(A_ValueProperty):
    class _EnumFlagList(QComboBox):
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
            texts: list[str] = []
            for i in range(model.rowCount()):
                item = model.item(i, 0)
                if item.checkState() == Qt.Checked:
                    texts.append(item.text())
            self._displayText = "|".join(texts)
            self.setText(self._displayText)

        def setText(self, text: str) -> None:
            l = self.lineEdit()
            l.blockSignals(True)
            l.setText(self._displayText)
            l.blockSignals(False)

        def get_value(self) -> int:
            model: QStandardItemModel = self.model()
            value = 0
            for i in range(self.count()):
                name = self.itemText(i)
                data = self.itemData(i, Qt.UserRole)
                if model.item(i, 0).checkState() == Qt.Checked:
                    value |= data
            return value

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


    class _EnumList(QComboBox):
        def get_value(self) -> int:
            return self.itemData(self.currentIndex(), Qt.UserRole)

    def __init__(self, name: str, enumInfo: dict[str, Any], readOnly: bool, parent: Optional["A_ValueProperty"] = None) -> None:
        self._enumInfo = enumInfo
        super().__init__(name, readOnly, parent)

    def construct(self) -> None:
        if self._enumInfo["Multi"] is True:
            self._checkList = EnumProperty._EnumFlagList()
        else:
            self._checkList = EnumProperty._EnumList()

        for name, value in self._enumInfo["Flags"].items():
            self._checkList.addItem(name, value)

        entry = QGridLayout()
        entry.setContentsMargins(0, 2, 0, 2)
        entry.addWidget(self._checkList)

        self.setLayout(entry)

    @Slot(QWidget, object)
    def set_inputs(self):
        pass

    def get_value(self) -> int:
        return super().get_value()

    def set_value(self, value: int) -> None:
        super().set_value(value)

    def __update_value_from_flags(self):
        self.set_value(self._checkList.get_value())


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

        inputX = SpinBoxDragDouble(isFloat=True)
        inputY = SpinBoxDragDouble(isFloat=True)
        inputZ = SpinBoxDragDouble(isFloat=True)
        self.__xyzInputs: List[SpinBoxDragDouble] = [inputX, inputY, inputZ]
        for i in range(3):
            axis = "XYZ"[i]
            spinBox = self.__xyzInputs[i]
            spinBox.setObjectName(f"{propertyName}.{axis}")
            spinBox.setMinimumWidth(80)
            spinBox.setValue(0)
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
        for i, _input in enumerate(self.__xyzInputs):
            _input.setValue(self.get_value()[i])
        self.blockSignals(False)

    def get_value(self) -> Vec3f:
        return super().get_value()

    def set_value(self, value: Vec3f):
        if not isinstance(value, Vec3f):
            raise ValueError("Value is not a Vec3f type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        for inputBox in self.__xyzInputs:
            inputBox.setMinimumWidth(
                max(80 - (10 * self.get_nested_depth()), 0))

    def __update_axis(self, value: float, axis: int = 0):
        self.get_value()[axis] = value
        self.valueChanged.emit(self, self.get_value())


class RGBA8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGBA8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        colorbutton = ColorButtonRGBA8()
        colorbutton.set_color(RGBA8(BasicColors.WHITE))
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

    def get_value(self) -> RGBA8:
        return super().get_value()

    def set_value(self, value: RGBA8):
        if not isinstance(value, RGBA8):
            raise ValueError("Value is not a RGBA8 type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        self._input.setMinimumWidth(
            max(80 - (10 * self.get_nested_depth()), 0))


class RGB8Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = RGB8(BasicColors.WHITE)

    def construct(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        colorbutton = ColorButtonRGB8()
        colorbutton.set_color(RGB8(BasicColors.WHITE))
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
            max(80 - (10 * self.get_nested_depth()), 0))

    @Slot(QWidget, object)
    def set_inputs(self):
        self._input.blockSignals(True)
        self._input.set_color(self.get_value())
        self._input.blockSignals(False)

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

    def construct(self) -> None:
        # TODO: PUT FRAMELAYOUT CHILDREN IN FORMLAYOUT
        self._frameLayout = FrameLayout(title=self.get_name())
        self._frameLayout._main_v_layout.setContentsMargins(0, 2, 0, 2)
        self._frameLayout._content_layout.setContentsMargins(10, 2, 0, 2)

        self._formLayout = QFormLayout()
        self._formLayout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._formLayout.setFieldGrowthPolicy(
            QFormLayout.AllNonFixedFieldsGrow)
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
                if p.get_qualified_name().scopes(name) and isinstance(p, StructProperty):
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
            self._frameLayout.addLayout(self._formLayout)
        else:
            self._formLayout.addRow(prop.get_name(), prop)
        self._properties[prop.get_name()] = prop
        prop._parent = self

    def set_value(self, value: Any) -> None:
        super().set_value(value)

    def get_value(self) -> Any:
        return super().get_value()

    def _update_input_depth(self) -> None:
        for prop in self.get_properties(deep=False):
            prop._update_input_depth()


class TransformProperty(StructProperty):
    def __init__(self, name: str, readOnly: bool, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, parent)
        self._resetValue = Transform()

    def construct(self):
        super().construct()

        inputT = Vector3Property("Translation", False, self)
        inputR = Vector3Property("Rotation", False, self)
        inputS = Vector3Property("Scale", False, self)
        inputT.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 0))
        inputR.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 1))
        inputS.valueChanged.connect(lambda _, _v: self.__update_trs(_v, 2))
        self.__trsInputs: List[Vector3Property] = [inputT, inputR, inputS]

    def is_container(self) -> bool:
        return True

    @Slot(QWidget, object)
    def set_inputs(self):
        inputT = self.__trsInputs[0]
        inputR = self.__trsInputs[1]
        inputS = self.__trsInputs[2]
        inputT._value = self.get_value().translation
        inputR._value = self.get_value().rotation.to_euler()
        inputS._value = self.get_value().scale
        inputT.set_inputs()
        inputR.set_inputs()
        inputS.set_inputs()

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
        elif valueType in {ValueType.S16, ValueType.SHORT}:
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
        elif valueType == ValueType.COMMENT:
            prop = CommentProperty(
                name
            )
        elif valueType == ValueType.ENUM:
            prop = EnumProperty(
                name, kwargs.get("enumInfo", {}), readOnly
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
        elif valueType == ValueType.STRUCT:
            prop = StructProperty(
                name, readOnly
            )

        prop.set_value(value)
        return prop
