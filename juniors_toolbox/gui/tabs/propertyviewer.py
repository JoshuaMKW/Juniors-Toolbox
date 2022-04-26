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
from juniors_toolbox.gui.tabs import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import A_ValueProperty
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import BaseObject
from juniors_toolbox.objects.template import ValueType, ObjectAttribute
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Transform, Vec3f
from juniors_toolbox.scene import SMSScene

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

        # self.updateTimer = QTimer(self.centralWidget)
        # self.updateTimer.timeout.connect(self.checkVerticalIndents)
        # self.updateTimer.start(10)

        self.setMinimumSize(300, 80)

        self.value_setter: Callable[[Any], bool] = lambda: True
        self.value_getter: Callable[[], Any] = lambda: None

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, list):
            return
        self.__populate_properties(data)
    
    def reset(self):
        clear_layout(self.gridLayout)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def __populate_properties(self, properties: List[A_ValueProperty]):
        self.reset()
        form = QFormLayout()
        for prop in properties:
            if isinstance(prop.get_value(), Transform):
                form.addWidget(prop)
                continue
            form.addRow(prop.get_name(), prop)
        self.gridLayout.addLayout(form)