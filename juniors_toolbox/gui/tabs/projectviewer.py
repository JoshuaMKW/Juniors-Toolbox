import time

from os import walk
from pathlib import Path
from threading import Event
from tokenize import Pointfloat
from typing import Any, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from PySide6.QtCore import QLine, QModelIndex, QObject, QSize, Qt, QTimer, Signal, SignalInstance, QThread, Slot, QAbstractItemModel
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QIcon, QImage, QKeyEvent, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QSplitter, QStyle, QTreeWidget,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from juniors_toolbox.gui.images import get_icon, get_image
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


class ProjectAssetListItem(QListWidgetItem):
    doubleClicked: SignalInstance = Signal(QListWidgetItem)

    def __init__(self, name: str, isFolder: bool, icon: Optional[QIcon] = None):
        super().__init__(name)
        self.__isFolder = isFolder
        self.__icon = icon

        if icon is None:
            if isFolder:
                self.__icon = get_icon("generic_folder.png")
            else:
                self.__icon = get_icon("generic_file.png")

        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if isFolder:
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)
        self.setIcon(self.__icon)


class ProjectHierarchyItem(QTreeWidgetItem):
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if isDir:
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)
        """
        self.setText(0, name)


class ProjectViewerWidget(QWidget, GenericTabWidget):
    class ProjectWatcher(QObject, FileSystemEventHandler):
        fileSystemChanged: SignalInstance = Signal()

        def on_any_event(self, event):
            self.fileSystemChanged.emit()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenePath = None
        self.focusedPath = None

        listWidget = QListWidget()
        # Lays out horizontally instead of vertically
        listWidget.setFlow(QListView.LeftToRight)
        # Dynamically adjust contents
        listWidget.setResizeMode(QListView.Adjust)
        # This is an arbitrary value, but it forces the layout into a grid
        listWidget.setGridSize(QSize(100, 100))
        # As an alternative to using setGridSize(), set a fixed spacing in the layout:
        # listWidget->setSpacing(someInt);
        # And the most important part:
        listWidget.setViewMode(QListView.IconMode)
        listWidget.setUniformItemSizes(True)
        listWidget.setIconSize(QSize(64, 64))
        listWidget.setWordWrap(True)
        listWidget.setSortingEnabled(True)
        listWidget.setAcceptDrops(True)
        #listWidget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.folderViewWidget = listWidget

        treeWidget = QTreeWidget()
        treeWidget.setHeaderHidden(True)
        self.fsTreeWidget = treeWidget

        self.mainLayout = QHBoxLayout()

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.fsTreeWidget)
        splitter.addWidget(self.folderViewWidget)
        self.splitter = splitter

        self.mainLayout.addWidget(self.splitter)
        self.setLayout(self.mainLayout)
        self.setMinimumSize(420, 200)

        self.eventHandler = ProjectViewerWidget.ProjectWatcher()
        self.eventHandler.fileSystemChanged.connect(self.update_tree)
        self.observer = Observer()

        #self.updateTimer = QTimer(self)
        # self.updateTimer.timeout.connect(self.update_tree)
        # self.updateTimer.start(10)

        #self.watcherThread = ProjectViewerWidget.ProjectWatcher(app.scenePath)
        # self.watcherThread.start()

    def populate(self, data: Any, scenePath: Path):
        self.scenePath = scenePath
        self.focusedPath = None
        self.update_tree()
        
        # Watch directory
        self.observer = Observer()
        self.observer.schedule(self.eventHandler, self.scenePath, recursive=True)
        self.observer.start()
        print(self.observer)
        """
        try:
            while observer.isAlive():
                observer.join(1)
        finally:
            observer.stop()
            observer.join()
        """

    @Slot()
    def update_tree(self):
        self.folderViewWidget.clear()
        self.fsTreeWidget.clear()

        def __inner_recurse_tree(parent: ProjectHierarchyItem, path: Path):
            for entry in path.iterdir():
                if not entry.is_dir():
                    continue
                
                item = ProjectHierarchyItem(entry.name)
                __inner_recurse_tree(item, entry)
                parent.addChild(item)

        for entry in self.scenePath.iterdir():
            isDir = entry.is_dir()
            
            item = ProjectAssetListItem(entry.name, isDir)
            self.folderViewWidget.addItem(item)

            if not isDir:
                continue

            item = ProjectHierarchyItem(entry.name)
            __inner_recurse_tree(item, entry)
            self.fsTreeWidget.addTopLevelItem(item)