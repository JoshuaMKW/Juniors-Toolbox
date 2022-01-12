from os import walk
from pathlib import Path
from threading import Event
from typing import Any, Dict, List, Tuple, Union
from queue import LifoQueue

from PySide2.QtCore import QLine, QModelIndex, QObject, QSize, Qt, QTimer
from PySide2.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent
from PySide2.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListView, QListWidget, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QSplitter, QStyle, QTreeView,
                               QTreeWidget, QTreeWidgetItem, QUndoCommand, QUndoStack,
                               QVBoxLayout, QWidget)
from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import ObjectAttribute
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene

class ProjectViewerWidget(QWidget, GenericTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        listWidget = QListWidget()
        # Lays out horizontally instead of vertically
        listWidget.setFlow(QListView.LeftToRight)
        # Dynamically adjust contents
        listWidget.setResizeMode(QListView.Adjust)
        # This is an arbitrary value, but it forces the layout into a grid
        listWidget.setGridSize(QSize(64, 64))
        # As an alternative to using setGridSize(), set a fixed spacing in the layout:
        # listWidget->setSpacing(someInt);
        # And the most important part:
        listWidget.setViewMode(QListView.IconMode)
        self.folderViewWidget = listWidget

        treeWidget = QTreeView()
        self.treeViewWidget = treeWidget

        self.mainLayout = QHBoxLayout()

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.treeViewWidget)
        splitter.addWidget(self.folderViewWidget)
        self.splitter = splitter

        self.mainLayout.addWidget(self.splitter)
        self.setLayout(self.mainLayout)

        self.updateTimer = QTimer(self)
        self.updateTimer.timeout.connect(self.update_tree)
        self.updateTimer.start(10)

    def populate(self, data: Any, scenePath: Path):
        self.scenePath = scenePath
        self.update_tree()

    def update_tree(self):
        ...