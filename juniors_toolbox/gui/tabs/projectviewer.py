import time

from os import walk
from pathlib import Path
from threading import Event
from tokenize import Pointfloat
from typing import Any, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from PySide6.QtCore import QLine, QModelIndex, QObject, QSize, Qt, QTimer, Signal, SignalInstance, QThread, Slot, QAbstractItemModel, QPoint
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QIcon, QImage, QKeyEvent, QUndoCommand, QUndoStack, QPixmap, QAction
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QSplitter, QStyle, QTreeWidget,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QMenu)
from juniors_toolbox import scene

from juniors_toolbox.gui.images import get_icon, get_image
from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import ObjectAttribute
from juniors_toolbox.utils.filesystem import open_path_in_explorer
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


class ProjectAssetListItem(QListWidgetItem):
    doubleClicked: SignalInstance = Signal(QListWidgetItem)

    @staticmethod
    def extension_to_icon_fname(ext: str):
        return ext.lstrip(".") + ".png"

    def __init__(self, name: str, isFolder: bool, icon: Optional[QIcon] = None):
        super().__init__(name)
        self.__isFolder = isFolder
        self.__icon = icon

        name = name.lower()

        if icon is None:
            if isFolder:
                self.__icon = get_icon("generic_folder.png")
            else:
                ext = name.split(".")[-1]
                if name == "scene.bin":
                    self.__icon = get_icon("program.png")
                else:
                    _icon = get_icon(self.extension_to_icon_fname(ext))
                    pixmap: QPixmap = _icon.pixmap(
                        _icon.actualSize(QSize(512, 512)))
                    if not pixmap.isNull():
                        self.__icon = _icon
                    else:
                        self.__icon = get_icon("generic_file.png")

        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled | Qt.ItemIsEditable
        if isFolder:
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)
        self.setIcon(self.__icon)
        font = self.font()
        font.setPointSize(7)
        self.setFont(font)

    def is_folder(self) -> bool:
        return self.__isFolder


class ProjectHierarchyItem(QTreeWidgetItem):
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        self.setFlags(flags)
        self.setText(0, name)

    def get_path(self) -> Path:
        subPath = self.text(0)
        parent = self.parent()
        while parent:
            next = parent.parent()
            if next is None and parent.text(0) == "scene":
                break
            subPath = f"{parent.text(0)}/{subPath}"
            parent = next
        return Path(subPath)


class ProjectViewerWidget(QWidget, GenericTabWidget):
    class ProjectWatcher(QObject, FileSystemEventHandler):
        fileSystemChanged: SignalInstance = Signal()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            FileSystemEventHandler.__init__(self)

            self.__block = False

        def on_closed(self, event: FileSystemEvent):
            ...#self.__changed = True

        def on_created(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_deleted(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_modified(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_moved(self, event: FileSystemEvent):
            self.signal_change(event)

        def signal_change(self, event: FileSystemEvent):
            if event.is_synthetic:
                return
            if not self.__block:
                self.fileSystemChanged.emit()
            self.__block = False

        def set_blocked(self, block: bool):
            """
            Blocks a single emit
            """
            self.__block = block

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenePath: Path = None
        self.focusedPath: Path = None
        self.__preRenamePath: Path = None
        self.__ignoreFsItemRename = False

        listWidget = QListWidget()
        # Lays out horizontally instead of vertically
        listWidget.setFlow(QListView.LeftToRight)
        # Dynamically adjust contents
        listWidget.setResizeMode(QListView.Adjust)
        # This is an arbitrary value, but it forces the layout into a grid
        listWidget.setGridSize(QSize(88, 88))
        # As an alternative to using setGridSize(), set a fixed spacing in the layout:
        # listWidget->setSpacing(someInt);
        # And the most important part:
        listWidget.setViewMode(QListView.IconMode)
        listWidget.setUniformItemSizes(True)
        listWidget.setIconSize(QSize(64, 64))
        listWidget.setWordWrap(True)
        # listWidget.setTextElideMode(Qt.ElideNone)
        listWidget.setAcceptDrops(True)
        # listWidget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.folderViewWidget = listWidget

        treeWidget = QTreeWidget()
        treeWidget.setHeaderHidden(True)
        treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
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
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.eventHandler = ProjectViewerWidget.ProjectWatcher()
        self.eventHandler.fileSystemChanged.connect(self.update_tree)
        self.observer = Observer()

        self.fsTreeWidget.itemClicked.connect(self.view_folder)
        self.fsTreeWidget.itemChanged.connect(self.rename_folder)
        self.fsTreeWidget.customContextMenuRequested.connect(
            self.fs_context_menu
        )

        #self.updateTimer = QTimer(self)
        # self.updateTimer.timeout.connect(self.update_tree)
        # self.updateTimer.start(10)

        #self.watcherThread = ProjectViewerWidget.ProjectWatcher(app.scenePath)
        # self.watcherThread.start()

    def populate(self, data: Any, scenePath: Path):
        self.scenePath = scenePath
        self.focusedPath = Path()
        self.update_tree()

        # Watch directory
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.observer = Observer()
        self.observer.schedule(
            self.eventHandler,
            self.scenePath,
            recursive=True
        )
        self.observer.start()

    @Slot()
    def update_tree(self):
        print("Updating tree")
        expandTree = self.__record_expand_tree()
        self.fsTreeWidget.clear()

        def __inner_recurse_tree(parent: ProjectHierarchyItem, path: Path):
            for entry in path.iterdir():
                if not entry.is_dir():
                    continue

                item = ProjectHierarchyItem(entry.name)
                __inner_recurse_tree(item, entry)
                parent.addChild(item)

        self.fsTreeWidget.setSortingEnabled(False)
        self.rootFsItem = ProjectHierarchyItem(self.scenePath.name)
        __inner_recurse_tree(self.rootFsItem, self.scenePath)
        self.fsTreeWidget.addTopLevelItem(self.rootFsItem)
        self.fsTreeWidget.setSortingEnabled(True)
        self.fsTreeWidget.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.__apply_expand_tree(expandTree)

        self.__populate_folder_view(self.focusedPath)

    @Slot(ProjectHierarchyItem)
    def view_folder(self, item: ProjectHierarchyItem):
        itemPath = item.get_path()
        if self.focusedPath == itemPath:
            return
        self.focusedPath = itemPath
        self.__populate_folder_view(self.focusedPath)

    @Slot(ProjectHierarchyItem)
    def rename_folder(self, item: ProjectHierarchyItem):
        if self.__ignoreFsItemRename:
            return

        itemPath = item.get_path()
        previousPath = self.__preRenamePath
        if previousPath == itemPath:
            return

        oldPath = self.scenePath / previousPath
        newPath = self.scenePath / itemPath
        resolvePath = newPath
        i = 1
        while resolvePath.exists(): # Failsafe limit = 1000
            if i > 1000:
                raise FileExistsError("Path exists beyond 1000 unique iterations!")
            resolvePath = resolvePath.with_name(f"{newPath.name} ({i})")
            if resolvePath.name == previousPath.name:
                self.__ignoreFsItemRename = True
                item.setText(0, resolvePath.name)
                self.__ignoreFsItemRename = False
                return
            i += 1
        newPath = resolvePath

        if i > 1: # Resolved path
            self.__ignoreFsItemRename = True
            item.setText(0, newPath.name)
            self.__ignoreFsItemRename = False

        oldPath.rename(newPath)
        if self.focusedPath == previousPath:
            self.focusedPath = newPath
        self.fsTreeWidget.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.eventHandler.set_blocked(True)

    @Slot(QPoint)
    def fs_context_menu(self, point: QPoint):
        # Infos about the node selected.
        index = self.fsTreeWidget.indexAt(point)

        if not index.isValid():
            return

        item: ProjectHierarchyItem = self.fsTreeWidget.itemAt(point)

        # We build the menu.
        menu = QMenu(self.fsTreeWidget)

        viewAction = QAction(
            "Open Path in Explorer",
            self.fsTreeWidget
        )
        viewAction.triggered.connect(
            lambda clicked=None, x=self.scenePath /
            item.get_path(): open_path_in_explorer(x)
        )
        openAction = QAction(
            "Open",
            self.fsTreeWidget
        )
        openAction.triggered.connect(
            lambda clicked=None, x=item: self.open_item(x)
        )
        deleteAction = QAction(
            "Delete",
            self.fsTreeWidget
        )
        deleteAction.triggered.connect(
            lambda clicked=None, x=item: self.delete_item(x)
        )
        renameAction = QAction(
            "Rename",
            self.fsTreeWidget
        )
        renameAction.triggered.connect(
            lambda clicked=None, x=item: self.rename_item(x)
        )

        menu.addAction(viewAction)
        menu.addSeparator()
        menu.addAction(openAction)
        menu.addAction(deleteAction)
        menu.addAction(renameAction)

        menu.exec(self.fsTreeWidget.mapToGlobal(point))

    @Slot(ProjectHierarchyItem)
    def open_item(self, item: ProjectHierarchyItem):
        ...

    @Slot(ProjectHierarchyItem)
    def delete_item(self, item: ProjectHierarchyItem):
        path = self.scenePath / item.get_path()
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()

    @Slot(ProjectHierarchyItem)
    def rename_item(self, item: ProjectHierarchyItem):
        self.__preRenamePath = item.get_path()
        self.fsTreeWidget.editItem(item, 0)

    def __populate_folder_view(self, subPath: Path):
        self.folderViewWidget.setSortingEnabled(False)
        self.folderViewWidget.clear()
        focusedPath = self.scenePath / subPath
        if not focusedPath.is_dir():
            return
        for entry in focusedPath.iterdir():
            item = ProjectAssetListItem(entry.name, entry.is_dir())
            self.folderViewWidget.addItem(item)
        self.folderViewWidget.setSortingEnabled(True)
        self.folderViewWidget.sortItems(Qt.SortOrder.AscendingOrder)

    def __record_expand_tree(self) -> dict:
        tree = {}
        def __inner_recurse(parent: ProjectHierarchyItem):
            nonlocal tree
            for i in range(parent.childCount()):
                child: ProjectHierarchyItem = parent.child(i)
                __inner_recurse(child)
                tree[child.get_path()] = child.isExpanded()
        for i in range(self.fsTreeWidget.topLevelItemCount()):
            child: ProjectHierarchyItem = self.fsTreeWidget.topLevelItem(i)
            __inner_recurse(child)
            tree[child.get_path()] = child.isExpanded()
        return tree

    def __apply_expand_tree(self, tree: dict):
        def __inner_recurse(parent: ProjectHierarchyItem):
            nonlocal tree
            for i in range(parent.childCount()):
                child: ProjectHierarchyItem = parent.child(i)
                __inner_recurse(child)
                child.setExpanded(tree.setdefault(child.get_path(), False))
        for i in range(self.fsTreeWidget.topLevelItemCount()):
            child: ProjectHierarchyItem = self.fsTreeWidget.topLevelItem(i)
            __inner_recurse(child)
            child.setExpanded(tree.setdefault(child.get_path(), False))
