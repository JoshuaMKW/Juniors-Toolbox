from enum import Enum, IntEnum, auto
import shutil
import time

from os import walk
from pathlib import Path
from threading import Event
from tkinter import EventType
from tokenize import Pointfloat
from typing import Any, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from PySide6.QtCore import QLine, QModelIndex, QObject, QSize, Qt, QTimer, Signal, SignalInstance, QThread, Slot, QAbstractItemModel, QPoint, QEvent
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QIcon, QImage, QKeyEvent, QUndoCommand, QUndoStack, QPixmap, QAction, QMouseEvent
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
from juniors_toolbox.utils.j3d.bmd import BMD
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


class ProjectAssetType(IntEnum):
    UNKNOWN = -1
    FOLDER = 0
    BIN = 10001
    BMD = auto()
    BMT = auto()
    BMG = auto()
    BTI = auto()
    COL = auto()
    JPA = auto()
    SB = auto()

    @classmethod
    def extension_to_flag(cls, extension: str) -> "ProjectAssetType":
        key = extension.lstrip(".").upper()
        if key not in cls._member_map_:
            return cls.UNKNOWN
        return cls[extension.lstrip(".").upper()]


class ProjectAssetListItem(QListWidgetItem):
    doubleClicked: SignalInstance = Signal(QListWidgetItem)

    @staticmethod
    def extension_to_icon_fname(ext: str):
        return ext.lstrip(".") + ".png"

    def __init__(self, name: str, isFolder: bool, icon: Optional[QIcon] = None):
        if isFolder:
            _type = ProjectAssetType.FOLDER
        else:
            _type = ProjectAssetType.extension_to_flag(name.split(".")[-1])
        super().__init__(name, type=_type)

        self.__isFolder = isFolder
        self.__icon = icon

        name = name.lower()
        if icon is None:
            if isFolder:
                self.__icon = get_icon("generic_folder.png")
                self.__typeID = ProjectAssetType.FOLDER
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
                self.__typeID = ProjectAssetType.extension_to_flag(ext)
        self.setIcon(self.__icon)

        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled | Qt.ItemIsEditable
        if isFolder:
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)

        font = self.font()
        font.setPointSizeF(7.4)
        self.setFont(font)

    def is_folder(self) -> bool:
        return self.__isFolder

    def get_type(self) -> ProjectAssetType:
        return self.__typeID

    def set_type(self, ty: ProjectAssetType):
        self.__typeID = ty


class FileSystemViewer():
    openExplorerRequested: SignalInstance = Signal(ProjectAssetListItem)
    openRequested: SignalInstance = Signal(ProjectAssetListItem)
    renameRequested: SignalInstance = Signal(ProjectAssetListItem, str)
    deleteRequested: SignalInstance = Signal(ProjectAssetListItem)


class ProjectFolderViewWidget(QListWidget, FileSystemViewer):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFlow(QListView.LeftToRight)
        self.setGridSize(QSize(88, 98))
        self.setIconSize(QSize(64, 64))
        self.setResizeMode(QListView.Adjust)
        self.setViewMode(QListView.IconMode)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.__preRenameName = ""

        self.itemChanged.connect(
            lambda item: self.renameRequested.emit(item, self.__preRenameName)
        )
        self.customContextMenuRequested.connect(
            self.custom_context_menu
        )

    def view(self, path: Path):
        self.setSortingEnabled(False)
        self.clear()
        if not path.is_dir():
            return
        for entry in path.iterdir():
            item = ProjectAssetListItem(entry.name, entry.is_dir())
            self.addItem(item)
        self.setSortingEnabled(True)
        self.sortItems(Qt.SortOrder.AscendingOrder)

    def editItem(self, item: ProjectAssetListItem):
        self.__preRenameName = item.text()
        super().editItem(item)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        item: ProjectAssetListItem = self.itemAt(event.pos())
        if not item.is_folder():
            event.ignore()
            return
        super().mouseDoubleClickEvent(event)

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint):
        # Infos about the node selected.
        item: ProjectHierarchyItem = self.itemAt(point)

        # We build the menu.
        menu = QMenu(self)

        viewAction = QAction("Open Path in Explorer", self)
        viewAction.triggered.connect(
            lambda clicked=None: self.openExplorerRequested.emit(item)
        )
        openAction = QAction("Open", self)
        openAction.triggered.connect(
            lambda clicked=None: self.openRequested.emit(item)
        )
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.deleteRequested.emit(item)
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item)
        )

        menu.addAction(viewAction)
        menu.addSeparator()
        menu.addAction(openAction)
        menu.addAction(deleteAction)
        menu.addAction(renameAction)

        menu.exec(self.mapToGlobal(point))

    
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
        return Path(subPath) if subPath != "scene" else Path()


class ProjectHierarchyViewWidget(QTreeWidget, FileSystemViewer):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.__preRenamePath = ""
        self.__rootFsItem: ProjectHierarchyItem = None

        self.itemChanged.connect(
            lambda item: self.renameRequested.emit(item, self.__preRenamePath)
        )
        self.customContextMenuRequested.connect(
            self.custom_context_menu
        )


    def view(self, path: Path):
        def __inner_recurse_tree(parent: ProjectHierarchyItem, path: Path):
            for entry in path.iterdir():
                if not entry.is_dir():
                    continue

                item = ProjectHierarchyItem(entry.name)
                __inner_recurse_tree(item, entry)
                parent.addChild(item)

        expandTree = self.__record_expand_tree()

        self.clear()
        self.setSortingEnabled(False)

        self.__rootFsItem = ProjectHierarchyItem(path.name)
        self.__rootFsItem.setFlags(
            Qt.ItemIsEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsSelectable)
        self.__rootFsItem.setExpanded(True)
        __inner_recurse_tree(self.__rootFsItem, path)

        self.addTopLevelItem(self.__rootFsItem)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)

        self.__apply_expand_tree(expandTree)

    def editItem(self, item: ProjectHierarchyItem):
        self.__preRenamePath = item.get_path()
        super().editItem(item)

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint):
        # Infos about the node selected.
        index = self.indexAt(point)

        if not index.isValid():
            return

        item: ProjectHierarchyItem = self.itemAt(point)

        # We build the menu.
        menu = QMenu(self)

        viewAction = QAction("Open Path in Explorer", self)
        viewAction.triggered.connect(
            lambda clicked=None: self.openExplorerRequested.emit(item)
        )
        openAction = QAction("Open", self)
        openAction.setEnabled(False)
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.deleteRequested.emit(item)
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item, 0)
        )

        menu.addAction(viewAction)
        menu.addSeparator()
        menu.addAction(openAction)
        menu.addAction(deleteAction)
        menu.addAction(renameAction)

        menu.exec(self.mapToGlobal(point))

    def __record_expand_tree(self) -> dict:
        tree = {}

        def __inner_recurse(parent: ProjectHierarchyItem):
            nonlocal tree
            for i in range(parent.childCount()):
                child: ProjectHierarchyItem = parent.child(i)
                __inner_recurse(child)
                tree[child.get_path()] = child.isExpanded()
        for i in range(self.topLevelItemCount()):
            child: ProjectHierarchyItem = self.topLevelItem(i)
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
        for i in range(self.topLevelItemCount()):
            child: ProjectHierarchyItem = self.topLevelItem(i)
            __inner_recurse(child)
            child.setExpanded(tree.setdefault(child.get_path(), False))


class ProjectViewerWidget(QWidget, GenericTabWidget):
    class ProjectWatcher(QObject, FileSystemEventHandler):
        fileSystemChanged: SignalInstance = Signal()
        finished: SignalInstance = Signal()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            FileSystemEventHandler.__init__(self)

            self.updateInterval = 0.5

            self.__blocking = True
            self.__softBlock = False
            self.__lastEventTime = 0.0
            self.__lastEvent: FileSystemEvent = None

        def run(self):
            while True:
                if self.__blocking:
                    if time.time() - self.__lastEventTime < self.updateInterval:
                        time.sleep(0.1)
                        continue
                    if self.__lastEvent is None:
                        time.sleep(0.1)
                        continue
                if not self.__softBlock:
                    self.fileSystemChanged.emit()
                self.__softBlock = False
                self.__lastEvent = None
                self.__lastEventTime = time.time()

        def on_created(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_modified(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_deleted(self, event: FileSystemEvent):
            self.signal_change(event)

        def on_moved(self, event: FileSystemEvent):
            self.signal_change(event)

        def signal_change(self, event: FileSystemEvent):
            if event.is_synthetic:
                return
            if self.__lastEvent is None:
                self.__lastEventTime = time.time()
            self.__lastEvent = event

        def is_blocking_enabled(self) -> bool:
            return self.__blocking

        def set_blocking_enabled(self, enabled: bool):
            self.__blocking = enabled

        def block_future_emit(self):
            self.__softBlock = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenePath: Path = None
        self.focusedPath: Path = None
        self.__ignoreItemRename = False
        self.__openTable = {}

        self.mainLayout = QHBoxLayout()
        self.folderViewWidget = ProjectFolderViewWidget()
        self.fsTreeWidget = ProjectHierarchyViewWidget()

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.fsTreeWidget)
        splitter.addWidget(self.folderViewWidget)
        self.splitter = splitter

        self.mainLayout.addWidget(self.splitter)
        self.setLayout(self.mainLayout)
        self.setMinimumSize(420, 200)

        self.watcherThread = QThread()
        self.eventHandler = ProjectViewerWidget.ProjectWatcher()
        self.eventHandler.fileSystemChanged.connect(self.update)
        self.eventHandler.moveToThread(self.watcherThread)
        self.watcherThread.started.connect(self.eventHandler.run)
        self.eventHandler.finished.connect(self.watcherThread.quit)
        self.eventHandler.finished.connect(self.eventHandler.deleteLater)
        self.watcherThread.finished.connect(self.watcherThread.deleteLater)

        self.observer = Observer()

        self.fsTreeWidget.itemClicked.connect(self.view_folder)

        self.folderViewWidget.itemDoubleClicked.connect(
            self.handle_view_double_click)
        self.folderViewWidget.openExplorerRequested.connect(self.explore_item)
        self.folderViewWidget.openRequested.connect(self.open_item)
        self.folderViewWidget.deleteRequested.connect(self.delete_item)
        self.folderViewWidget.renameRequested.connect(self.rename_item)

        self.fsTreeWidget.openExplorerRequested.connect(self.explore_item)
        self.fsTreeWidget.openRequested.connect(self.open_item)
        self.fsTreeWidget.deleteRequested.connect(self.delete_item)
        self.fsTreeWidget.renameRequested.connect(self.rename_item)

        #self.updateTimer = QTimer(self)
        # self.updateTimer.timeout.connect(self.update_tree)
        # self.updateTimer.start(10)

        #self.watcherThread = ProjectViewerWidget.ProjectWatcher(app.scenePath)
        # self.watcherThread.start()

    def populate(self, data: Any, scenePath: Path):
        self.scenePath = scenePath
        self.focusedPath = Path()
        self.update()

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
        self.watcherThread.start()

    def get_fs_tree_item(self, path: Path) -> ProjectHierarchyItem:
        possibleItems: List[ProjectHierarchyItem] = self.fsTreeWidget.findItems(
            path.name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        if len(possibleItems) == 0:
            return None
        for pItem in possibleItems:
            pPath = pItem.get_path()
            if pPath == path:
                return pItem
        return None

    @Slot()
    def update(self):
        self.fsTreeWidget.view(self.scenePath)
        self.folderViewWidget.view(self.scenePath / self.focusedPath)

    @Slot(ProjectHierarchyItem)
    def view_folder(self, item: ProjectHierarchyItem):
        itemPath = item.get_path()
        if self.focusedPath == itemPath:
            return
        self.focusedPath = itemPath
        self.folderViewWidget.view(self.scenePath / self.focusedPath)

    @Slot(ProjectAssetListItem)
    def handle_view_double_click(self, item: ProjectAssetListItem):
        if item.is_folder():
            targetItem = self.get_fs_tree_item(
                self.focusedPath / item.text())
            if targetItem is None:
                raise ValueError(
                    f"Can't view folder `{item.text()}` as there is no filesystem match!")
            self.view_folder(targetItem)

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def explore_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
        if isinstance(item, ProjectHierarchyItem):
            open_path_in_explorer(self.scenePath / item.get_path())
        else:
            open_path_in_explorer(self.scenePath / self.focusedPath / item.text())

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def open_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
        if isinstance(item, ProjectAssetListItem) and str(item.get_type()) in self.__openTable:
            self.__open_table[str(item.get_type())]()

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def delete_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
        isFsItem = isinstance(item, ProjectHierarchyItem)
        if isFsItem:
            path = self.scenePath / item.get_path()
        else:
            path = self.scenePath / self.focusedPath / item.text()

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

        if isFsItem:
            item.parent().removeChild(item)
            if path.parent.relative_to(self.scenePath) == self.focusedPath:
                items = self.folderViewWidget.findItems(path.name, Qt.MatchFlag.MatchExactly)
                if len(items) == 1:
                    self.folderViewWidget.takeItem(self.folderViewWidget.row(items[0]))
        else:
            self.folderViewWidget.takeItem(self.folderViewWidget.row(item))
            fsItem = self.get_fs_tree_item(path.relative_to(self.scenePath))
            if fsItem:
                fsItem.parent().removeChild(fsItem)

        if path.relative_to(self.scenePath) == self.focusedPath:
            if self.focusedPath.parent is None:
                self.folderViewWidget.view(self.scenePath)
                self.focusedPath = Path()
            else:
                self.folderViewWidget.view(self.scenePath / self.focusedPath.parent)
                self.focusedPath = self.focusedPath.parent

        self.eventHandler.block_future_emit()

    @Slot(ProjectHierarchyItem, str)
    @Slot(ProjectAssetListItem, str)
    def rename_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem], previousPath: str):
        if self.__ignoreItemRename:
            return

        isFsItem = isinstance(item, ProjectHierarchyItem)

        itemPath = item.get_path() if isFsItem else self.focusedPath / item.text()
        previousPath = Path(previousPath) if isFsItem else self.focusedPath / previousPath
        if previousPath == itemPath:
            return

        oldPath = self.scenePath / previousPath
        newPath = self.scenePath / itemPath
        resolvePath = newPath
        i = 1
        while resolvePath.exists():  # Failsafe limit = 1000
            if i > 1000:
                raise FileExistsError(
                    "Path exists beyond 1000 unique iterations!")
            resolvePath = resolvePath.with_name(f"{newPath.name} ({i})")
            if resolvePath.name == previousPath.name:
                self.__ignoreItemRename = True
                item.setText(0, resolvePath.name) if isFsItem else item.setText(
                    resolvePath.name)
                self.__ignoreItemRename = False
                return
            i += 1
        newPath = resolvePath

        if i > 1:  # Resolved path
            self.__ignoreItemRename = True
            item.setText(0, newPath.name) if isFsItem else item.setText(
                newPath.name)
            self.__ignoreItemRename = False

        oldPath.rename(newPath)
        if self.focusedPath == previousPath:
            self.focusedPath = newPath
        
        if isFsItem:
            self.fsTreeWidget.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        else:
            self.folderViewWidget.sortItems(Qt.SortOrder.AscendingOrder)
            if newPath.is_dir():
                fsItem = self.get_fs_tree_item(oldPath.relative_to(self.scenePath))
                if fsItem:
                    self.__ignoreItemRename = True
                    fsItem.setText(0, newPath.name)
                    self.__ignoreItemRename = False
                    self.fsTreeWidget.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.eventHandler.block_future_emit()