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

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import A_ValueProperty
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import BaseObject
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Transform, Vec3f
from juniors_toolbox.scene import SMSScene

class SelectedPropertiesWidget(A_DockingInterface):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.mainLayout = QGridLayout()

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.centralWidget = QWidget()
        self.gridLayout = QGridLayout()
        self.centralWidget.setLayout(self.gridLayout)

        self.scrollArea.setWidget(self.centralWidget)
        
        self.mainLayout.addWidget(self.scrollArea)
        self.setLayout(self.mainLayout)

        # self.updateTimer = QTimer(self.centralWidget)
        # self.updateTimer.timeout.connect(self.checkVerticalIndents)
        # self.updateTimer.start(10)

        self.setMinimumSize(300, 80)

        self.value_setter: Callable[[Any], bool] = lambda _x: True
        self.value_getter: Callable[[], Any] = lambda: None

    def populate(self, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        data: List[A_ValueProperty] = args[0]
        self.__populate_properties(data)
    
    def reset(self) -> None:
        clear_layout(self.gridLayout)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def __populate_properties(self, properties: List[A_ValueProperty]) -> None:
        self.reset()
        form = QFormLayout()
        for prop in properties:
            if isinstance(prop.get_value(), Transform):
                form.addWidget(prop)
                continue
            form.addRow(prop.get_name(), prop)
        self.gridLayout.addLayout(form, 0, 0, 0, 0)