from abc import abstractmethod
from hashlib import new
from importlib.resources import path
import shutil
import sys
import time
from cmath import exp
from enum import Enum, IntEnum, auto
from pathlib import Path, PurePath
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union

from juniors_toolbox.gui.dialogs.moveconflict import MoveConflictDialog

from juniors_toolbox.gui.images import get_icon, get_image
from juniors_toolbox.gui.models.rarcfs import JSystemFSDirectoryProxyModel, JSystemFSModel, JSystemFSSortProxyModel
from juniors_toolbox.gui.widgets import ABCMetaWidget, ABCWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.interactivestructs import InteractiveListView, InteractiveTreeView, InteractiveListWidget, InteractiveListWidgetItem, InteractiveTreeWidget
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.bmg import BMG
from juniors_toolbox.utils.filesystem import open_path_in_explorer, open_path_in_terminal
from juniors_toolbox.utils.initializer import FileInitializer
from juniors_toolbox.utils.j3d.anim.bca import BCA
from juniors_toolbox.utils.j3d.anim.bck import BCK
from juniors_toolbox.utils.j3d.anim.bla import BLA
from juniors_toolbox.utils.j3d.anim.blk import BLK
from juniors_toolbox.utils.j3d.anim.bpk import BPK
from juniors_toolbox.utils.j3d.anim.brk import BRK
from juniors_toolbox.utils.j3d.anim.btk import BTK
from juniors_toolbox.utils.j3d.anim.btp import BTP
from juniors_toolbox.utils.j3d.anim.bva import BVA
from juniors_toolbox.utils.j3d.bmd import BMD
from juniors_toolbox.utils.prm import PrmFile
from juniors_toolbox.utils.types import RGB8, RGB32, RGBA8, Vec3f
from PySide6.QtCore import (QAbstractItemModel, QDataStream, QEvent, QIODevice, QByteArray, QThread, QRunnable,
                            QLine, QMimeData, QModelIndex, QObject, QPoint,
                            QSize, Qt, QThread, QTimer, QUrl, Signal, QItemSelectionModel, QPersistentModelIndex,
                            SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QDragEnterEvent, QClipboard,
                           QDragLeaveEvent, QDragMoveEvent, QDropEvent, QIcon,
                           QImage, QKeyEvent, QMouseEvent, QPaintDevice, QContextMenuEvent,
                           QPainter, QPaintEvent, QPalette, QPixmap, QPen,
                           QUndoCommand, QUndoStack)
from PySide6.QtTest import QAbstractItemModelTester
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QMenuBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem,
                               QSplitter, QStyle, QStyleOptionComboBox,
                               QStylePainter, QTableWidget, QTableWidgetItem,
                               QToolBar, QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox, QApplication, QTreeView,
                               QVBoxLayout, QWidget)

_ASSET_INIT_TABLE = {
    "Animation": {
        BCA: {
            "Initializer": FileInitializer("NewJointAnim.bca", BCA()),
            "ActionName": "Joint All",
            "ActionIcon": None
        },
        BCK: {
            "Initializer": FileInitializer("NewJointKeyAnim.bck", BCK()),
            "ActionName": "Joint Key",
            "ActionIcon": None
        },
        BLA: {
            "Initializer": FileInitializer("NewClusterAnim.bla", BLA()),
            "ActionName": "Cluster All",
            "ActionIcon": None
        },
        BLK: {
            "Initializer": FileInitializer("NewClusterKeyAnim.blk", BLK()),
            "ActionName": "Cluster Key",
            "ActionIcon": None
        },
        BPK: {
            "Initializer": FileInitializer("NewColorKeyAnim.bpk", BPK()),
            "ActionName": "Color Key",
            "ActionIcon": None
        },
        BRK: {
            "Initializer": FileInitializer("NewTEVRegisterKeyAnim.brk", BRK()),
            "ActionName": "TEV Register Key",
            "ActionIcon": None
        },
        BTK: {
            "Initializer": FileInitializer("NewTextureSRTKeyAnim.btk", BTK()),
            "ActionName": "Texture SRT Key",
            "ActionIcon": None
        },
        BTP: {
            "Initializer": FileInitializer("NewTexturePaletteAnim.btp", BTP()),
            "ActionName": "Texture Palette All",
            "ActionIcon": None
        },
        BVA: {
            "Initializer": FileInitializer("NewMeshVisibilityAnim.bva", BVA()),
            "ActionName": "Mesh Visibility All",
            "ActionIcon": None
        },
    },
    SMSScene: {
        "Initializer": FileInitializer("scene.bin", b""),
        "ActionName": "Empty Scene",
        "ActionIcon": None
    },
    BMG: {
        "Initializer": FileInitializer("NewMessage.bmg", BMG()),
        "ActionName": "Message Table",
        "ActionIcon": None
    },
    PrmFile: {
        "Initializer": FileInitializer("NewParams.prm", PrmFile()),
        "ActionName": "Parameter Table",
        "ActionIcon": None
    },
}


class ProjectCreateAction(QAction):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.initializer = FileInitializer("Default", b"")


class ProjectCacheUpdater(QObject, QRunnable):
    cacheUpdated = Signal()

    def __init__(self, model: JSystemFSModel, indexToCache: QModelIndex | QPersistentModelIndex, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.model = model
        self.indexToCache = indexToCache

    def run(self) -> None:
        self.model._cache_path(self.indexToCache)


class ProjectFocusedMenuBarAction(QAction):
    clicked = Signal(QAction)
    triggered: Signal

    def __init__(self, isRoot: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.isRoot = isRoot
        self.triggered.connect(self.__click)

    def __click(self, toggled: bool) -> None:
        self.clicked.emit(self)


class ProjectFocusedMenuBar(QMenuBar):
    folderChangeRequested = Signal(Path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setNativeMenuBar(False)
        self.setAcceptDrops(True)
        # self.setFloatable(False)

        self.__parts: list[ProjectFocusedMenuBarAction] = []

        font = self.font()
        font.setBold(True)
        self.setFont(font)

    def get_focused_path_to(self, item: Union[ProjectFocusedMenuBarAction, QMenu], name: str) -> Path:
        if isinstance(item, ProjectFocusedMenuBarAction) and item.isRoot:
            return self.scenePath

        subPath = Path()
        for part in self.__parts:
            if part == item:
                break
            if isinstance(part, ProjectFocusedMenuBarAction) and not part.isRoot:
                subPath = subPath / part.text()

        return subPath / name

    def view(self, __p: Path, /) -> None:
        """
        Path is relative to scene path
        """
        self.clear()
        self.__parts.clear()
        if not __p.is_absolute():
            self._focusedPath = __p
        else:
            self._focusedPath = __p.relative_to(self.scenePath)

        sceneItem = ProjectFocusedMenuBarAction(True, self)
        sceneItem.setText(self.scenePath.name)
        sceneItem.clicked.connect(self.check_clicked)
        self.addAction(sceneItem)

        self.__parts.append(sceneItem)
        self.__populate_from_path(self._focusedPath)

    @Slot(ProjectFocusedMenuBarAction)
    def check_clicked(self, clicked: ProjectFocusedMenuBarAction) -> None:
        parent = clicked.parent()
        tname = clicked.text()
        if isinstance(parent, QMenu):
            target = parent
        else:
            target = clicked
        path = self.get_focused_path_to(target, tname)
        if self._focusedPath == path:
            clicked.setChecked(True)
        else:
            self.folderChangeRequested.emit(path)

    def __populate_from_path(self, path: Path) -> None:
        curSubPath = Path()
        for part in path.parts:
            expandItem = QMenu(self)
            expandItem.setTitle(">")
            self.addAction(expandItem.menuAction())
            self.__parts.append(expandItem)

            folderItem = ProjectFocusedMenuBarAction(False, self)
            folderItem.setText(part)
            folderItem.clicked.connect(self.check_clicked)
            self.addAction(folderItem)
            self.__parts.append(folderItem)

            for child in (self.scenePath / curSubPath).iterdir():
                if child.is_dir():
                    action = ProjectFocusedMenuBarAction(False, expandItem)
                    action.setText(child.name)
                    action.setCheckable(True)
                    action.setChecked(child.name.lower() == part.lower())
                    action.clicked.connect(self.check_clicked)
                    expandItem.addAction(action)

            curSubPath = curSubPath / part

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()

        event.acceptProposedAction()

    @Slot(QDragMoveEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        item: ProjectFocusedMenuBarAction = self.actionAt(event.pos())
        if item is None or item.text() == ">":
            event.ignore()
            return

        event.acceptProposedAction()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        mimeData = event.mimeData()
        if not mimeData.hasUrls():
            event.ignore()
            return

        item: Optional[ProjectFocusedMenuBarAction] = self.actionAt(
            event.pos())
        if item is None:
            event.ignore()
            return

        dst = self.get_focused_path_to(item, item.text())
        paths = [Path(url.toLocalFile()) for url in mimeData.urls()]
        self.moveRequested.emit(paths, dst)


class ProjectFolderViewWidget(InteractiveListView):
    class PathUndoCommand(QUndoCommand):
        def __init__(self, target: "ProjectFolderViewWidget"):
            super().__init__("Cmd")
            self.target = target
            self.prevPath = PurePath()
            self.curPath = PurePath()

        def set_prev(self, path: PurePath):
            self.prevPath = path

        def set_current(self, path: PurePath):
            self.curPath = path

        def redo(self):
            pathIndex = self._get_cur_index()
            self.target.setRootIndex(pathIndex)
            self._focusedPath = self.curPath

        def undo(self):
            pathIndex = self._get_prev_index()
            self.target.setRootIndex(pathIndex)
            self._focusedPath = self.prevPath

        def _get_cur_index(self) -> QModelIndex:
            model: JSystemFSModel = self.target.get_source_model()
            proxyModel: JSystemFSSortProxyModel = self.target.model()
            return proxyModel.mapFromSource(
                model.get_path_index(self.curPath)
            )

        def _get_prev_index(self) -> QModelIndex:
            model: JSystemFSModel = self.target.get_source_model()
            proxyModel: JSystemFSSortProxyModel = self.target.model()
            return proxyModel.mapFromSource(
                model.get_path_index(self.prevPath)
            )

    class PathUndoStack(QUndoStack):
        def canRedo(self) -> bool:
            index = self.index()
            command: ProjectFolderViewWidget.PathUndoCommand = self.command(
                index)
            if not command._get_cur_index().isValid():
                return False
            return super().canRedo()

        def canUndo(self) -> bool:
            index = self.index()
            command: ProjectFolderViewWidget.PathUndoCommand = self.command(
                index)
            if not command._get_prev_index().isValid():
                return False
            return super().canUndo()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setUniformItemSizes(True)
        self.setGridSize(QSize(88, 98))
        self.setIconSize(QSize(64, 64))
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setResizeMode(QListView.Adjust)

        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setEditTriggers(QListView.NoEditTriggers)

        self._selectedIndexesOnDrag: list[QModelIndex |
                                          QPersistentModelIndex] = []

        self._pathHistory = ProjectFolderViewWidget.PathUndoStack(self)

    def set_tracked_root_index(self, index: QModelIndex | QPersistentModelIndex) -> None:
        if self.rootIndex() == index:
            return

        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        sourceCurIndex = proxyModel.mapToSource(index)
        sourcePrevIndex = proxyModel.mapToSource(self.rootIndex())

        command = ProjectFolderViewWidget.PathUndoCommand(self)
        command.set_prev(model.get_path(sourcePrevIndex))
        command.set_current(model.get_path(sourceCurIndex))
        self._pathHistory.push(command)

    def get_source_model(self) -> QAbstractItemModel:
        proxy: JSystemFSSortProxyModel = self.model()
        return proxy.sourceModel()

    def set_source_model(self, model: QAbstractItemModel) -> None:
        proxy: JSystemFSSortProxyModel = self.model()
        proxy.setSourceModel(model)

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        menu = QMenu(self)

        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        # Infos about the node selected.
        contextIndex = self.indexAt(point)
        contextIndexValid = contextIndex.isValid()

        sourceContextIndex = proxyModel.mapToSource(contextIndex)
        isChildOfArchive = model.get_parent_archive(
            sourceContextIndex).isValid()
        isFolder = model.is_dir(sourceContextIndex)

        # Selected indexes
        selectedIndexes = self.selectedIndexes()
        singularSelection = len(selectedIndexes) == 1

        newAssetMenu = self.generate_asset_menu(contextIndex)
        newFolderAction = QAction("New Folder", self)
        newFolderAction.triggered.connect(
            lambda: self._create_folder_index(parent=contextIndex))

        if not isChildOfArchive:
            explorerAction = QAction("Open in Explorer", self)
            explorerAction.triggered.connect(
                lambda: self._open_index_in_explorer(contextIndex)
            )
            terminalAction = QAction("Open in Terminal", self)
            terminalAction.triggered.connect(
                lambda: self._open_index_in_terminal(contextIndex)
            )

        copyPathAction = QAction("Copy Path", self)
        copyPathAction.triggered.connect(
            lambda: self._copy_index_paths(selectedIndexes, relative=False)
        )

        if contextIndexValid:
            cutAction = QAction("Cut", self)
            cutAction.triggered.connect(
                lambda: self._cut_paths(selectedIndexes)
            )

            copyAction = QAction("Copy", self)
            copyAction.triggered.connect(
                lambda: self._copy_paths(selectedIndexes)
            )

            copyRelativePathAction = QAction("Copy Relative Path", self)
            copyRelativePathAction.triggered.connect(
                lambda: self._copy_index_paths(contextIndex, relative=True)
            )

            if singularSelection:
                renameAction = QAction("Rename", self)
                renameAction.triggered.connect(
                    lambda: self.edit(contextIndex)
                )

            deleteAction = QAction("Delete", self)
            deleteAction.triggered.connect(
                lambda: self._delete_paths(selectedIndexes)
            )

        pasteAction = QAction("Paste", self)
        pasteAction.setEnabled(
            self._is_import_ready(QClipboard().mimeData())
        )
        if isFolder:
            pasteAction.triggered.connect(
                lambda: self._paste_paths(contextIndex)
            )
        else:
            pasteAction.triggered.connect(
                lambda: self._paste_paths(self.rootIndex())
            )

        menu.addMenu(newAssetMenu)
        menu.addAction(newFolderAction)

        if not isChildOfArchive:
            menu.addAction(explorerAction)
            menu.addAction(terminalAction)

        menu.addSeparator()

        if contextIndexValid:
            menu.addAction(cutAction)
            menu.addAction(copyAction)
            if isFolder:
                menu.addAction(pasteAction)
        else:
            menu.addAction(pasteAction)

        menu.addSeparator()

        menu.addAction(copyPathAction)

        if contextIndexValid:
            menu.addAction(copyRelativePathAction)
            menu.addSeparator()
            if singularSelection:
                menu.addAction(renameAction)
            menu.addAction(deleteAction)

        return menu

    def generate_asset_menu(self, parent: QModelIndex) -> QMenu:
        createMenu = QMenu("Create", self)
        folderAction = ProjectCreateAction(createMenu)
        folderAction.setText("Folder")

        def traverse_structure(_menu: QMenu, initTable: dict):
            for assetKind, assetInfo in initTable.items():
                if isinstance(assetKind, str):
                    subMenu = QMenu(assetKind)
                    traverse_structure(subMenu, assetInfo)
                    _menu.addMenu(subMenu)
                    _menu.addSeparator()
                else:
                    action = ProjectCreateAction(_menu)
                    action.setText(assetInfo["ActionName"])
                    if assetInfo["ActionIcon"]:
                        action.setIcon(assetInfo["ActionIcon"])

                    action.initializer = assetInfo["Initializer"]
                    action.triggered.connect(
                        lambda: self._write_action_initializer(
                            parent, action.initializer
                        )
                    )

                    _menu.addAction(action)

        traverse_structure(createMenu, _ASSET_INIT_TABLE)
        return createMenu

    def _is_import_ready(self, mimeData: QMimeData) -> bool:
        # Has virtual archive data
        if mimeData.hasFormat("x-application/jsystem-fs-data"):
            return True

        return mimeData.hasUrls()

    def _open_index_in_explorer(self, index: QModelIndex | QPersistentModelIndex) -> None:
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        if not index.isValid():
            index = self.rootIndex()

        if index.model() == proxyModel:
            index = proxyModel.mapToSource(index)

        open_path_in_explorer(Path(model.get_path(index)))

    def _open_index_in_terminal(self, index: QModelIndex | QPersistentModelIndex) -> None:
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        if not index.isValid():
            index = self.rootIndex()

        if index.model() == proxyModel:
            index = proxyModel.mapToSource(index)

        open_path_in_terminal(Path(model.get_path(index)))

    def _copy_index_paths(self, indexes: list[QModelIndex | QPersistentModelIndex], relative: bool = True) -> None:
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        mappedIndexes = []
        for index in indexes:
            if not index.isValid():
                index = self.rootIndex()

            if index.model() == proxyModel:
                index = proxyModel.mapToSource(index)
            mappedIndexes.append(index)

        paths: list[str] = []
        for index in mappedIndexes:
            path = model.get_path(index)
            if relative and model.rootPath:
                path = path.relative_to(model.rootPath)
                if sys.platform == "win32":
                    paths.append(f".\{path}")
                else:
                    paths.append(f"./{path}")
            else:
                paths.append(str(path))

        QClipboard().setText("\n".join(paths))

    def _copy_paths(self, indexes: list[QModelIndex | QPersistentModelIndex]):
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        mappedIndexes = []
        for index in indexes:
            if not index.isValid():
                continue

            if index.model() == proxyModel:
                index = proxyModel.mapToSource(index)
            mappedIndexes.append(index)

        mimeData = QMimeData()

        successful = model.export_paths(mimeData, mappedIndexes)
        if not successful:
            print("Failed to copy path to clipboard")
            return

        QClipboard().setMimeData(mimeData)

    def _cut_paths(self, indexes: list[QModelIndex | QPersistentModelIndex]):
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        mappedIndexes = []
        for index in indexes:
            if not index.isValid():
                continue

            if index.model() == proxyModel:
                index = proxyModel.mapToSource(index)
            mappedIndexes.append(index)

        mimeData = QMimeData()

        data = QByteArray()
        stream = QDataStream(data, QIODevice.WriteOnly)
        stream.setByteOrder(QDataStream.LittleEndian)
        stream << 2

        mimeData.setData("Preferred DropEffect", data)

        successful = model.export_paths(mimeData, mappedIndexes)
        if not successful:
            print("Failed to cut path to clipboard")
            return

        QClipboard().setMimeData(mimeData)

    def _paste_paths(self, index: QModelIndex | QPersistentModelIndex):
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        if not index.isValid():
            index = self.rootIndex()

        if index.model() == proxyModel:
            index = proxyModel.mapToSource(index)

        mimeData = QClipboard().mimeData()

        successful = model.import_paths(mimeData, index)
        if not successful:
            print("Failed to paste clipboard to path")
            return

    def _delete_paths(self, indexes: list[QModelIndex | QPersistentModelIndex]):
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()
        selectionModel = self.selectionModel()

        mappedIndexes = []
        for index in indexes:
            if not index.isValid():
                continue

            self.selectionModel().select(index, QItemSelectionModel.Deselect)

            if index.model() == proxyModel:
                index = proxyModel.mapToSource(index)
            mappedIndexes.append(index)

        for index in mappedIndexes:
            model.remove(index)

    def _write_action_initializer(self, index: QModelIndex | QPersistentModelIndex, initializer: FileInitializer) -> None:
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        if not index.isValid():
            index = self.rootIndex()

        if index.model() == proxyModel:
            index = proxyModel.mapToSource(index)

        initPath = model._resolve_path_conflict(initializer.get_name(), index)
        if initPath is None:
            raise RuntimeError("Failed to find unique path for init")
        initName = initPath.name

        newIndex = model.mkfile(initName,
                                initializer.get_identity(), index)
        proxyModel.invalidate()
        proxyIndex = proxyModel.mapFromSource(newIndex)
        self.edit(proxyIndex)

    def _create_folder_index(self, name: str = "New Folder", parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> None:
        """
        Creates a folder and sets up the Widget to rename
        """
        model: JSystemFSModel = self.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.model()

        if not parent.isValid():
            parent = self.rootIndex()

        if parent.model() == proxyModel:
            parent = proxyModel.mapToSource(parent)

        initPath = model._resolve_path_conflict(name, parent)
        if initPath is None:
            raise RuntimeError("Failed to find unique path for init")
        initName = initPath.name

        newIndex = model.mkdir(initName, parent)

        proxyModel.invalidate()
        proxyIndex = proxyModel.mapFromSource(newIndex)
        self.edit(proxyIndex)

    def _resolve_name(self, name: str, filterItem: Optional[QModelIndex | QPersistentModelIndex] = None) -> str:
        model = self.model()

        parts = name.rsplit(".", 1)
        name = parts[0]

        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(model.rowCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = model.index(i, 0)
            if item == filterItem:
                continue
            itemText: str = item.data(Qt.DisplayRole)
            if itemText.startswith(ogName):
                possibleNames.append(itemText.rsplit(".", 1)[0])

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        if len(parts) == 2:
            name += f".{parts[1]}"
        return name

    def _create_asset_index(self, name: str = "New Asset", parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> None:
        model: JSystemFSModel = self.get_source_model()
        if parent.model() == model:
            newIndex = model.mkdir(name, parent)
        else:
            proxyModel: JSystemFSSortProxyModel = self.model()
            newIndex = model.mkdir(name, proxyModel.mapToSource(parent))
        newProxyIndex = proxyModel.mapFromSource(newIndex)
        self.edit(newProxyIndex)

    @Slot(QMouseEvent)
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.BackButton:
            self._pathHistory.undo()
            event.accept()
            return

        if event.button() == Qt.ForwardButton:
            self._pathHistory.redo()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    @Slot(QMouseEvent)
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        model: JSystemFSSortProxyModel = self.model()
        sourceIndex = model.mapToSource(index)

        sourceModel: JSystemFSModel = sourceIndex.model()
        if not sourceModel.is_populated(sourceIndex):
            event.ignore()
            return

        super().mouseDoubleClickEvent(event)

    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        indexes = self.selectedIndexes()
        drag = QDrag(self)
        mime = self.model().mimeData(indexes)
        urlList = []
        for index in indexes:
            urlList.append(
                QUrl.fromLocalFile(
                    index.data(JSystemFSModel.FilePathRole)
                )
            )
        mime.setUrls(urlList)
        drag.setMimeData(mime)

        # -- ICON -- #

        if supportedActions & Qt.MoveAction:
            if len(indexes) == 0:
                return

            pixmap = QPixmap(70, 80)
            pixmap.fill(Qt.transparent)

            painter = QPainter()
            painter.begin(pixmap)

            font = painter.font()
            font.setPointSize(6)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Qt.NoPen)

            painter.setBrush(QColor(20, 150, 220, 70))
            painter.drawRoundedRect(0, 0, 70, 80, 5, 5)

            if len(indexes) == 1:
                icon: QIcon = indexes[0].data(Qt.DisplayRole).icon()
                iconPixmap = QPixmap(icon.pixmap(
                    icon.actualSize(QSize(64, 64)))).scaled(64, 64)
                painter.drawPixmap(3, 8, iconPixmap)
            else:
                fontMetrics = painter.fontMetrics()
                textWidth = fontMetrics.boundingRect(str(len(indexes))).width()
                painter.setPen(Qt.white)
                painter.setBrush(QColor(20, 110, 220, 255))
                painter.drawRect(27, 32, 16, 16)
                painter.drawText(35 - (textWidth // 2), 43, str(len(indexes)))

            painter.end()

            drag.setPixmap(pixmap)
            drag.setHotSpot(pixmap.rect().center() + QPoint(0, 20))

        drag.exec(supportedActions)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()

        self._selectedIndexesOnDrag = self.selectedIndexes()
        super().dragEnterEvent(event)

    @Slot(QDragMoveEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        eventPos = event.pos()
        hoveredIndex = self.indexAt(eventPos)

        proxyModel: JSystemFSSortProxyModel = self.model()
        sourceIndex = proxyModel.mapToSource(hoveredIndex)
        sourceModel: JSystemFSModel = sourceIndex.model()

        event.accept()  # Accept by default
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        if not hoveredIndex.isValid():
            super().dragMoveEvent(event)
            if event.source() == self:
                event.ignore()
            return

        if sourceModel.is_dir(sourceIndex) or sourceModel.is_archive(sourceIndex):
            super().dragMoveEvent(event)
            if hoveredIndex in self._selectedIndexesOnDrag:
                event.ignore()
            return

        event.ignore()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        mimeData = event.mimeData()
        if not mimeData.hasUrls():
            return

        eventPos = event.pos()
        hoveredIndex = self.indexAt(eventPos)

        proxyModel: JSystemFSSortProxyModel = self.model()
        sourceIndex = proxyModel.mapToSource(hoveredIndex)
        sourceModel: JSystemFSModel = sourceIndex.model()

        if not hoveredIndex.isValid():
            if event.source() == self:
                event.ignore()
            paths = []
            for url in mimeData.urls():
                path = Path(url.toLocalFile())
                paths.append(path)
            self.dropInRequested.emit(paths)
            event.accept()
            return

        if sourceModel.is_dir(sourceIndex) or sourceModel.is_archive(sourceIndex):
            self.move_indexes(self._selectedIndexesOnDrag, hoveredIndex)
            event.accept()
        else:
            event.ignore()
        return

    @Slot(QKeyEvent)
    def keyPressEvent(self, event: QKeyEvent) -> None:
        print(event.key())
        print(event.keyCombination())
        super().keyPressEvent(event)

    @Slot(QKeyEvent)
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        indexes = self.selectedIndexes()

        if event.key() == Qt.Key_Delete:
            self._delete_paths(indexes)
            event.accept()
            return

        key = event.key()
        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.ControlModifier:
            if modifiers & Qt.ShiftModifier:
                if key == Qt.Key_C:
                    self._copy_index_paths(indexes, relative=False)
                elif key == Qt.Key_X:
                    self._copy_index_paths(indexes, relative=True)
                event.accept()
                return

            if key == Qt.Key_C:
                self._copy_paths(indexes)
            elif key == Qt.Key_X:
                self._cut_paths(indexes)
            elif key == Qt.Key_V:
                self._paste_paths(self.rootIndex())
            elif key == Qt.Key_O:
                if len(indexes) != 1:
                    return
                self._open_index_in_explorer(indexes[0])
            elif key == Qt.Key_T:
                if len(indexes) != 1:
                    return
                self._open_index_in_terminal(indexes[0])
            elif key == Qt.Key_R:
                if len(indexes) != 1:
                    return
                self.edit(indexes[0])

        event.accept()

    @Slot(list, QModelIndex)
    def move_indexes(self, indexesToMove: list[QModelIndex | QPersistentModelIndex], parentIndex: QModelIndex | QPersistentModelIndex):
        proxyModel: JSystemFSSortProxyModel = self.model()
        sourceParent = proxyModel.mapToSource(parentIndex)
        sourceModel: JSystemFSModel = sourceParent.model()

        if not (sourceModel.is_dir(sourceParent) or sourceModel.is_archive(sourceParent)):
            print("Destination folder is invalid")
            return False

        for index in indexesToMove:
            sourceIndex = proxyModel.mapToSource(index)
            sourceModel.move(sourceIndex, sourceParent)


class ProjectTreeViewWidget(InteractiveTreeView):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(QTreeView.NoEditTriggers)

    def get_source_model(self) -> QAbstractItemModel:
        proxy: JSystemFSDirectoryProxyModel = self.model()
        return proxy.sourceModel()

    def set_source_model(self, model: QAbstractItemModel) -> None:
        proxy: JSystemFSDirectoryProxyModel = self.model()
        proxy.setSourceModel(model)

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        menu = QMenu(self)

        # Infos about the node selected.
        selectedIndex = self.indexAt(point)
        selectedIndexValid = selectedIndex.isValid()

        newFolderAction = QAction("New Folder", self)

        explorerAction = QAction("Open in Explorer", self)
        terminalAction = QAction("Open in Terminal", self)
        copyPathAction = QAction("Copy Path", self)

        if selectedIndexValid:
            cutAction = QAction("Cut", self)
            copyAction = QAction("Copy", self)
            copyRelativePathAction = QAction("Copy Relative Path", self)
            renameAction = QAction("Rename", self)
            deleteAction = QAction("Delete", self)

        menu.addAction(newFolderAction)
        menu.addAction(explorerAction)
        menu.addAction(terminalAction)
        menu.addSeparator()

        if selectedIndexValid:
            menu.addAction(cutAction)
            menu.addAction(copyAction)
            menu.addSeparator()

        menu.addAction(copyPathAction)

        if selectedIndexValid:
            menu.addAction(copyRelativePathAction)
            menu.addSeparator()
            menu.addAction(renameAction)
            menu.addAction(deleteAction)

        return menu


class ProjectViewerWidget(A_DockingInterface):
    def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__scenePath: Optional[Path] = None
        self._focusedPath = PurePath()

        self.fsModel = JSystemFSModel(
            Path("__doesnt_exist__"), False, self)

        self.fsModelViewProxy = JSystemFSSortProxyModel(self)
        self.fsModelViewProxy.setSourceModel(self.fsModel)
        self.fsModelDirProxy = JSystemFSDirectoryProxyModel(self)
        self.fsModelDirProxy.setSourceModel(self.fsModel)

        self.mainLayout = QHBoxLayout()

        self.fsTreeWidget = ProjectTreeViewWidget()
        self.fsTreeWidget.setModel(self.fsModelDirProxy)

        self.folderWidget = QWidget()

        self.folderViewLayout = QVBoxLayout()
        self.folderViewLayout.setContentsMargins(0, 0, 0, 0)

        self.focusedViewWidget = ProjectFocusedMenuBar()

        # self._modelTester = QAbstractItemModelTester(
        #     self.fsModelViewProxy,
        #     QAbstractItemModelTester.FailureReportingMode.Warning,
        #     self
        # )

        # self._modelTester2 = QAbstractItemModelTester(
        #     self.fsModelDirProxy,
        #     QAbstractItemModelTester.FailureReportingMode.Warning,
        #     self
        # )

        self.folderViewWidget = ProjectFolderViewWidget()
        self.folderViewWidget.setModel(self.fsModelViewProxy)
        self.folderViewWidget.doubleClicked.connect(
            self._view_directory_from_view
        )

        self.fsTreeWidget.clicked.connect(
            self._view_directory
        )

        self.folderViewLayout.addWidget(self.focusedViewWidget)
        self.folderViewLayout.addWidget(self.folderViewWidget)

        self.folderWidget.setLayout(self.folderViewLayout)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.fsTreeWidget)
        splitter.addWidget(self.folderWidget)
        self.splitter = splitter

        # self.mainLayout.addWidget(self.splitter)
        self.setWidget(self.splitter)
        # self.setLayout(self.mainLayout)
        self.setMinimumSize(420, 200)

    @property
    def scenePath(self) -> Path:
        return self.__scenePath if self.__scenePath is not None else Path.cwd()

    @scenePath.setter
    def scenePath(self, path: Path) -> None:
        self.__scenePath = path
        self.fsModel.rootPath = path
        self.fsModelViewProxy.sort(0, Qt.AscendingOrder)
        self.fsTreeWidget.expand(
            self.fsModelDirProxy.index(0, 0, QModelIndex())
        )
        self.folderViewWidget.setRootIndex(
            self.fsModelViewProxy.index(0, 0)
        )

    @property
    def focusedPath(self) -> PurePath:
        return self._focusedPath

    @focusedPath.setter
    def focusedPath(self, path: PurePath) -> None:
        if self._focusedPath == path:
            return

        model: JSystemFSModel = self.folderViewWidget.get_source_model()
        proxyModel: JSystemFSSortProxyModel = self.folderViewWidget.model()

        focusedIndex = model.get_path_index(path)
        self.folderViewWidget.set_tracked_root_index(
            proxyModel.mapFromSource(focusedIndex))

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        self.scenePath = args[0]
        self.focusedPath = Path()
        self.update()

    @Slot()
    def update(self) -> None:
        # self.fsTreeWidget.view_project(self.scenePath)
        # self.focusedViewWidget.view(self.focusedPath)
        ...

    @Slot(QModelIndex)
    def _view_directory(self, index: QModelIndex | QPersistentModelIndex):
        sourceModel = self.fsModel
        viewModel = self.fsModelViewProxy
        sourceIndex = self.fsModelDirProxy.mapToSource(index)

        if not sourceModel.is_loaded(sourceIndex):
            sourceModel._cache_path(sourceIndex)

        self.folderViewWidget.set_tracked_root_index(
            viewModel.mapFromSource(sourceIndex)
        )

    @Slot(QModelIndex)
    def _view_directory_from_view(self, index: QModelIndex | QPersistentModelIndex):
        sourceModel = self.fsModel
        dirModel = self.fsModelDirProxy
        sourceIndex = self.fsModelViewProxy.mapToSource(index)

        if not sourceModel.is_loaded(sourceIndex):
            sourceModel._cache_path(sourceIndex)

        self.folderViewWidget.set_tracked_root_index(index)

        self.fsTreeWidget.expand(
            dirModel.mapFromSource(sourceIndex)
        )
