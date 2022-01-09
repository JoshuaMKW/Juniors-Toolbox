from pathlib import Path
from typing import Any, Union
from PySide2.QtCore import QLine, QModelIndex, QObject, Qt, QTimer
from PySide2.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent
from PySide2.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle,
                               QTreeWidget, QTreeWidgetItem, QUndoCommand, QUndoStack,
                               QVBoxLayout, QWidget)

from nodeeditor.node_scene import Scene
from nodeeditor.node_node import Node
from nodeeditor.node_editor_widget import NodeEditorWidget

from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.bmg import BMG

class EscapeNode(Node):
    ...


class PureEscapeNode(EscapeNode):
    ...


class ColorNode(EscapeNode): # - [0x1A06FF0000xx]
    ...


class FormatNode(EscapeNode): # - [0x1A050200xx] && [0x1A060200040x]
    ...


class OptionNode(EscapeNode): # - [0x1Ayy0100xx]SSS
    ...


class SpeedNode(EscapeNode): # - [0x1A06000000xx]
    ...


class PreDefProgressionNode(EscapeNode): # - [0x1A050000xx]
    ...


class SubStringNode(Node): # - shift-jis string
    ...


class BMGNodeEditorWidget(NodeEditorWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(300, 300)

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, BMG):
            return

        scene = Scene()
        for message in data.iter_messages():
            self.scene