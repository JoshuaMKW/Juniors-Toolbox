from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, List, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import A_ValueProperty
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene