from abc import ABC
from ast import Call
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)

from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import ValueProperty
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import AttributeType, ObjectAttribute
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


def create_vec3f_entry(
    attribute: GameObject.Value,
    nestedDepth: int = 0,
    indentWidth: int = 25,
    readOnly: bool = False
):
    _qualname = attribute.name
    _attrname = _qualname.split(".")[-1]
    _attrtype = attribute.type
    _attrvalue = attribute.value

    if _attrtype != AttributeType.VECTOR3:
        return None

    widget = QWidget()
    containerLayout = QGridLayout()
    containerLayout.setContentsMargins(0, 0, 0, 0)
    containerLayout.setRowStretch(0, 0)
    containerLayout.setRowStretch(1, 0)
    container = EntryLayout(
        _attrname,
        widget,
        Vec3f,
        [],
        labelWidth=100 - (indentWidth * nestedDepth),
        minEntryWidth=260
    )
    container.setObjectName(attribute.name)
    for i, component in enumerate(_attrvalue):
        axis = "XYZ"[i]
        spinBox = SpinBoxDragDouble(isFloat=True)
        spinBox.setObjectName(f"{_attrname}.{axis}")
        spinBox.setMinimumWidth(20)
        spinBox.setValue(component)
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
    widget.setLayout(containerLayout)
    container.setEnabled(not readOnly)
    return container


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


class SelectedPropertiesWidget(QScrollArea, GenericTabWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.object = None
        self.centralWidget = QWidget()
        self.setWidgetResizable(True)
        self.setWidget(self.centralWidget)

        self.gridLayout = QGridLayout()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.centralWidget.setLayout(self.gridLayout)

        self.updateTimer = QTimer(self.centralWidget)
        self.updateTimer.timeout.connect(self.checkVerticalIndents)
        self.updateTimer.start(10)

        self.setMinimumSize(300, 80)

        self.value_setter: Callable[[Any], bool] = lambda: True
        self.value_getter: Callable[[], Any] = lambda: None

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, list):
            return
    
    def reset(self):
        clear_layout(self.gridLayout)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def __populate_properties(self, properties: List[ValueProperty]):
        self.reset()
        for property in properties:
            self.gridLayout.addWidget(property)

import cv2