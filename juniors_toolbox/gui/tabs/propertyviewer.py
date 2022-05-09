from abc import ABC
from ast import Call
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import A_ValueProperty, StructProperty, TransformProperty
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.objects.value import QualifiedName
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Transform, Vec3f
from juniors_toolbox.scene import SMSScene

class SelectedPropertiesWidget(A_DockingInterface):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.__defaultTitle = title

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.centralWidget = QWidget()
        self.gridLayout = QGridLayout()
        self.gridLayout.setVerticalSpacing(0)
        self.centralWidget.setLayout(self.gridLayout)

        self.scrollArea.setWidget(self.centralWidget)
        
        self.setWidget(self.scrollArea)

        # self.updateTimer = QTimer(self.centralWidget)
        # self.updateTimer.timeout.connect(self.checkVerticalIndents)
        # self.updateTimer.start(10)

        self.setMinimumSize(300, 80)

        self.value_setter: Callable[[Any], bool] = lambda _x: True
        self.value_getter: Callable[[], Any] = lambda: None

        self._properties: list[A_ValueProperty] = []

    def get_properties(self, *, deep: bool = True) -> Iterable[A_ValueProperty]:
        for prop in self._properties:
            yield prop
            if deep:
                yield from prop.get_properties(deep=deep)

    def get_property(self, name: QualifiedName) -> Optional[A_ValueProperty]:
        for prop in self._properties:
            if prop.get_qualified_name() == name:
                return prop
            if prop.get_qualified_name().scopes(name):
                return prop.get_property(name)
        return None

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        data: List[A_ValueProperty] = kwargs.get("properties", [])
        if "title" in kwargs:
            self.setWindowTitle(kwargs["title"])
        else:
            self.setWindowTitle(self.__defaultTitle)
        self.__populate_properties(data)
    
    def reset(self) -> None:
        clear_layout(self.gridLayout)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWindowTitle(self.__defaultTitle)

    def __populate_properties(self, properties: List[A_ValueProperty]) -> None:
        self.reset()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignVCenter)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setContentsMargins(0, 2, 0, 2)
        formRow = 0
        for prop in properties:
            if prop.is_container():
                self.gridLayout.addLayout(form, formRow, 0, 1, 1)
                self.gridLayout.addWidget(prop, formRow + 1, 0, 1, 1)
                self.gridLayout.setRowStretch(formRow, 0)
                self.gridLayout.setRowStretch(formRow + 1, 0)
                form = QFormLayout()
                form.setLabelAlignment(Qt.AlignVCenter)
                form.setRowWrapPolicy(QFormLayout.WrapLongRows)
                form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
                form.setContentsMargins(0, 2, 0, 2)
                formRow += 2
                continue
            form.addRow(prop.get_name(), prop)
        self.gridLayout.addLayout(form, formRow, 0, 1, 1)
        self.gridLayout.setRowStretch(formRow, 0)
        self.gridLayout.setRowStretch(formRow + 1, 1)