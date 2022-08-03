from abc import abstractmethod
from hashlib import new
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
from PySide6.QtCore import (QAbstractItemModel, QDataStream, QEvent, QIODevice, QByteArray,
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


class ProjectAssetListItem(InteractiveListWidgetItem):
    doubleClicked = Signal(InteractiveListWidgetItem)

    MIME_FORMAT = __name__
    _init_fn_: Callable[["ProjectAssetListItem"], Optional[A_Serializable]]

    @staticmethod
    def extension_to_icon_fname(ext: str):
        return ext.lstrip(".") + ".png"

    def __init__(self, item: Union["ProjectAssetListItem", str], isFolder: bool, icon: Optional[QIcon] = None):
        if isinstance(item, str):
            if isFolder:
                _type = ProjectAssetType.FOLDER
            else:
                _type = ProjectAssetType.extension_to_flag(item.split(".")[-1])
            super().__init__(item, type=_type.value)
        else:
            super().__init__(item)
            item = item.text()

        self.__isFolder = isFolder
        self.__icon: QIcon = QIcon()

        name = item.lower()
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
        font.setPointSize(7)
        self.setFont(font)

        self._init_fn_ = lambda self: None

    def copy(self) -> "ProjectAssetListItem":
        item = ProjectAssetListItem(
            self,
            self.__isFolder
        )
        return item

    def is_folder(self) -> bool:
        return self.__isFolder

    def get_type(self) -> ProjectAssetType:
        return self.__typeID

    def set_type(self, ty: ProjectAssetType):
        self.__typeID = ty

    def __lt__(self, other: "ProjectAssetListItem"):
        """ Used for sorting """
        if self.is_folder() and not other.is_folder():
            return True
        if other.is_folder() and not self.is_folder():
            return False
        return self.text() < other.text()


class ProjectHierarchyItem(QTreeWidgetItem):
    _init_fn_: Callable[["ProjectHierarchyItem"], Optional[A_Serializable]]

    def __init__(self, name: str, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        super().__init__(*args, **kwargs)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        self.setFlags(flags)
        self.setText(0, name)

        self._preRenamePath = ""

        self._init_fn_ = lambda self: None

    def get_relative_path(self) -> Path:
        subPath = self.text(0)
        parent = self.parent()
        while parent:
            next = parent.parent()
            if next is None and parent.text(0) == "scene":
                break
            subPath = f"{parent.text(0)}/{subPath}"
            parent = next
        return Path(subPath) if subPath != "scene" else Path()


class ProjectCreateAction(QAction):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.initializer = FileInitializer("Default", b"")


class ProjectFocusedMenuBarAction(QAction):
    clicked = Signal(QAction)
    triggered: Signal

    def __init__(self, isRoot: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.isRoot = isRoot
        self.triggered.connect(self.__click)

    def __click(self, toggled: bool) -> None:
        self.clicked.emit(self)


class A_FileSystemViewer(ABCWidget):
    openExplorerRequested = Signal(object)
    openRequested = Signal(object)
    createFolderRequested = Signal(str)
    copyRequested = Signal(
        list, list)
    moveRequested = Signal(list, object)
    renameRequested = Signal(object)
    deleteRequested = Signal(list)
    dropInRequested = Signal(list)
    dropOutRequested = Signal(object)

    _scenePath: Optional[Path] = None
    _focusedPath: Optional[Path] = None

    def __init__(self) -> None:
        self._scenePath: Optional[Path] = None
        self._focusedPath: Optional[Path] = None

    @property
    def scenePath(self) -> Path:
        return self._scenePath if self._scenePath is not None else Path.cwd()

    @scenePath.setter
    def scenePath(self, path: Path) -> None:
        self._scenePath = path
        self._focusedPath = Path()
        self.view(self._focusedPath)

    @property
    def focusedPath(self) -> Path:
        return self._focusedPath if self._focusedPath is not None else Path()

    @focusedPath.setter
    def focusedPath(self, path: Path) -> None:
        self.view(path)

    @abstractmethod
    def view(self, __p: Path, /) -> None: ...


class ProjectFocusedMenuBar(QMenuBar, A_FileSystemViewer):
    folderChangeRequested = Signal(Path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        A_FileSystemViewer.__init__(self)

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

        self._selectedIndexesOnDrag: list[ProjectAssetListItem] = []

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

        # Selected indexes
        selectedIndexes = self.selectedIndexes()

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
            lambda: self._copy_index_paths(contextIndex, relative=False)
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

            renameAction = QAction("Rename", self)
            renameAction.triggered.connect(
                lambda: self.edit(contextIndex)
            )

            deleteAction = QAction("Delete", self)
            deleteAction.triggered.connect(
                lambda: self._delete_paths(selectedIndexes)
            )
        else:
            pasteAction = QAction("Paste")
            pasteAction.setEnabled(
                self._is_import_ready(QClipboard().mimeData())
            )
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
            menu.addSeparator()

        menu.addAction(copyPathAction)

        if contextIndexValid:
            menu.addAction(copyRelativePathAction)
            menu.addSeparator()
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

        QClipboard.setText("\n".join(paths))

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
            print("Failed to copy path to clipboard")
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
            print("Failed to copy path to clipboard")
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
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.pos())

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


class ProjectTreeViewWidget(InteractiveTreeView, A_FileSystemViewer):
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
        self.__focusedPath: Optional[Path] = None
        self.__ignoreItemRename = False
        self.__openTable: Dict[str, Any] = {}

        self.fsModel = JSystemFSModel(Path("__doesnt_exist__"), False, self)

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

        # self.fsTreeWidget.itemClicked.connect(self.view_folder)

        # self.folderViewWidget.itemDoubleClicked.connect(
        #     self.handle_view_double_click)
        # self.folderViewWidget.openExplorerRequested.connect(self.explore_item)
        # self.folderViewWidget.openRequested.connect(self.open_item)
        # self.folderViewWidget.copyRequested.connect(self.copy_items)
        # self.folderViewWidget.deleteRequested.connect(self.delete_items)
        # self.folderViewWidget.renameRequested.connect(self.rename_item)
        # self.folderViewWidget.moveRequested.connect(self.move_items)
        # self.folderViewWidget.dropInRequested.connect(
        #     self.copy_paths_to_focused
        # )

        self.focusedViewWidget.folderChangeRequested.connect(self.view_folder)

        # self.fsTreeWidget.openExplorerRequested.connect(self.explore_item)
        # self.fsTreeWidget.openRequested.connect(self.open_item)
        # self.fsTreeWidget.deleteRequested.connect(self.delete_items)
        # self.fsTreeWidget.renameRequested.connect(self.rename_item)
        # self.fsTreeWidget.moveRequested.connect(self.move_items)
        # self.fsTreeWidget.dropInRequested.connect(
        #     self.copy_paths_to_focused
        # )

        self.focusedViewWidget.moveRequested.connect(self.move_items)

        self.fsModel.conflictFound.connect(self._show_conflict_dialog)

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
        self.focusedViewWidget.scenePath = path

    @property
    def focusedPath(self) -> Path:
        return self.__focusedPath if self.__focusedPath is not None else Path()

    @focusedPath.setter
    def focusedPath(self, path: Path) -> None:
        self.__focusedPath = path
        self.folderViewWidget.setRootIndex(
            self.fsModelViewProxy.mapFromSource(
                self.fsModel.get_path_index(path)
            )
        )
        self.focusedViewWidget.focusedPath = path

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        self.scenePath = args[0]
        self.focusedPath = Path()
        self.update()

    @Slot()
    def update(self) -> None:
        # self.fsTreeWidget.view_project(self.scenePath)
        self.focusedViewWidget.view(self.focusedPath)

    @Slot(ProjectHierarchyItem)
    @Slot(Path)
    def view_folder(self, item: ProjectHierarchyItem | Path) -> None:
        if isinstance(item, ProjectHierarchyItem):
            itemPath = item.get_relative_path()
        else:
            itemPath = item
            if item.is_absolute():
                itemPath = item.relative_to(self.scenePath)

        if not (self.scenePath / itemPath).is_dir():
            return

        if self.focusedPath == itemPath:
            return
        self.focusedPath = itemPath  # Set viewed directory

    @Slot(ProjectAssetListItem)
    def handle_view_double_click(self, item: ProjectAssetListItem) -> None:
        self.view_folder(self.focusedPath / item.text())

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def explore_item(self, item: Optional[ProjectHierarchyItem | ProjectAssetListItem]) -> None:
        if item is None:
            open_path_in_explorer(
                self.scenePath / self.focusedPath)
        else:
            if isinstance(item, ProjectHierarchyItem):
                open_path_in_explorer(
                    self.scenePath / item.get_relative_path())
            else:
                open_path_in_explorer(
                    self.scenePath / self.focusedPath / item.text())

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def open_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]) -> None:
        if isinstance(item, ProjectAssetListItem) and str(item.get_type()) in self.__openTable:
            self.__open_table[str(item.get_type())]()

    @Slot(list)
    def delete_items(self, _items: Union[list[ProjectHierarchyItem], list[ProjectAssetListItem]]) -> None:
        for item in _items:
            if isinstance(item, ProjectHierarchyItem):
                path = self.scenePath / item.get_relative_path()
            else:
                path = self.scenePath / self.focusedPath / item.text()

            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

            if isinstance(item, ProjectHierarchyItem):
                item.parent().removeChild(item)
                if path.parent.relative_to(self.scenePath) == self.focusedPath:
                    items = self.folderViewWidget.findItems(
                        path.name, Qt.MatchFlag.MatchExactly)
                    if len(items) == 1:
                        self.folderViewWidget.takeItem(
                            self.folderViewWidget.row(items[0]))
            else:
                self.folderViewWidget.takeItem(self.folderViewWidget.row(item))
                fsItem = self.fsTreeWidget.get_fs_tree_item(
                    path.relative_to(self.scenePath))
                if fsItem:
                    fsItem.parent().removeChild(fsItem)

            if path.relative_to(self.scenePath) == self.focusedPath:
                self.focusedPath = self.focusedPath.parent

            self.eventHandler.block_future_emit()

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def rename_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]) -> None:
        if self.__ignoreItemRename:
            return

        if isinstance(item, ProjectHierarchyItem):
            itemPath = item.get_relative_path()
        else:
            self.focusedPath / item.text()

        previousPath = self.focusedPath / item._prevName_
        if previousPath == itemPath:
            return

        oldPath = self.scenePath / previousPath
        newPath = self.scenePath / itemPath

        if oldPath.exists():
            oldPath.rename(newPath)
        else:
            with newPath.open("wb") as f:
                f.write(item._init_fn_().to_bytes())

        if self.focusedPath == previousPath:
            self.focusedPath = newPath

        if isinstance(item, ProjectHierarchyItem):
            self.fsTreeWidget.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        else:
            self.folderViewWidget.sortItems(Qt.SortOrder.AscendingOrder)
            if newPath.is_dir():
                fsItem = self.fsTreeWidget.get_fs_tree_item(
                    oldPath.relative_to(self.scenePath))
                if fsItem:
                    self.__ignoreItemRename = True
                    fsItem.setText(0, newPath.name)
                    self.__ignoreItemRename = False
                    self.fsTreeWidget.sortByColumn(
                        0, Qt.SortOrder.AscendingOrder)
        self.eventHandler.block_future_emit()

    @Slot(list, ProjectHierarchyItem)
    @Slot(list, ProjectAssetListItem)
    @Slot(list, Path)
    def move_items(
        self,
        items: list[ProjectHierarchyItem] | list[ProjectAssetListItem],
        target: Optional[ProjectHierarchyItem | ProjectAssetListItem | Path]
    ) -> None:
        if self.__ignoreItemRename:
            return

        if target is None:
            targetItemPath = Path()
        elif isinstance(target, (Path, str)):
            targetItemPath = Path(target)
        elif isinstance(target, ProjectHierarchyItem):
            targetItemPath = target.get_relative_path()
        else:
            targetItemPath = self.focusedPath / target.text()

        conflictDialog = MoveConflictDialog(len(items) > 1, self)
        for item in items:
            if isinstance(item, (Path, str)):
                itemPath = Path(item)
                self.__move_path(
                    self.scenePath / itemPath,
                    self.scenePath / targetItemPath,
                    conflictDialog
                )
            else:
                self.__move_item(
                    item,
                    targetItemPath,
                    conflictDialog
                )
        self.update()

    @Slot(list)
    def copy_items(
        self,
        _oldItems: list[ProjectHierarchyItem] | list[ProjectAssetListItem],
        _newItems: list[ProjectHierarchyItem] | list[ProjectAssetListItem]
    ) -> None:
        if self.__ignoreItemRename:
            return

        for oldItem, newItem in zip(_oldItems, _newItems):
            if isinstance(oldItem, ProjectHierarchyItem) and isinstance(newItem, ProjectHierarchyItem):
                itemPath = newItem.get_relative_path()
                previousPath = oldItem.get_relative_path()
            else:
                itemPath = self.focusedPath / newItem.text()
                previousPath = self.focusedPath / oldItem.text()

            if previousPath == itemPath:
                return

            oldPath = self.scenePath / previousPath
            newPath = self.scenePath / itemPath

            self.eventHandler.block_future_emit()
            if oldPath.is_file():
                shutil.copy(oldPath, newPath)
            else:
                shutil.copytree(oldPath, newPath, dirs_exist_ok=True)
            if self.focusedPath == previousPath:
                self.focusedPath = newPath

            if isinstance(oldItem, ProjectHierarchyItem) and isinstance(newItem, ProjectHierarchyItem):
                self.fsTreeWidget.sortByColumn(0, Qt.SortOrder.AscendingOrder)
            else:
                self.folderViewWidget.sortItems(Qt.SortOrder.AscendingOrder)
                if newPath.is_dir():
                    fsItem = self.fsTreeWidget.get_fs_tree_item(
                        oldPath.relative_to(self.scenePath))
                    if fsItem:
                        self.__ignoreItemRename = True
                        fsItem.setText(0, newPath.name)
                        self.__ignoreItemRename = False
                        self.fsTreeWidget.sortByColumn(
                            0, Qt.SortOrder.AscendingOrder)

    @Slot(list)
    def copy_paths_to_focused(self, paths: list[Path]) -> None:
        for path in paths:
            dest = self.scenePath / self.focusedPath
            dest = dest / _fs_resolve_name(path.name, dest)

            try:
                if path.is_file():
                    shutil.copy(path, dest)
                else:
                    shutil.copytree(path, dest, dirs_exist_ok=True)
            except PermissionError:
                continue

    def __move_path(self, src: Path, dst: Path, conflictDialog: MoveConflictDialog) -> bool:
        dst = dst / src.name
        if dst.exists():
            conflictDialog.set_paths(src, dst)
            action, role = conflictDialog.resolve()
            if action == QDialog.Rejected:
                return False
            if role == MoveConflictDialog.ActionRole.REPLACE:
                src.replace(dst)
            elif role == MoveConflictDialog.ActionRole.KEEP:
                src.rename(
                    dst.parent / _fs_resolve_name(
                        dst.name,
                        dst.parent
                    )
                )
            elif role == MoveConflictDialog.ActionRole.SKIP:
                return False
            else:
                return False
        else:
            src.rename(dst)

        self.eventHandler.block_future_emit()
        return True

    def __move_item(self, src: ProjectHierarchyItem | ProjectAssetListItem, dst: Path, conflictDialog: MoveConflictDialog) -> bool:
        if isinstance(src, ProjectHierarchyItem):
            itemPath = src.get_relative_path()
        else:
            itemPath = self.focusedPath / src.text()

        oldPath = self.scenePath / itemPath
        newPath = self.scenePath / dst / itemPath.name

        if oldPath.parent == newPath.parent:
            return False

        if not oldPath.exists():
            return False

        if newPath.exists():
            conflictDialog.set_paths(oldPath, newPath)
            action, role = conflictDialog.resolve()
            if action == QDialog.Rejected:
                return False
            if role == MoveConflictDialog.ActionRole.REPLACE:
                oldPath.replace(newPath)
            elif role == MoveConflictDialog.ActionRole.KEEP:
                oldPath.rename(
                    newPath.parent / _fs_resolve_name(
                        newPath.name,
                        newPath.parent
                    )
                )
            elif role == MoveConflictDialog.ActionRole.SKIP:
                return False
            else:
                return False
        else:
            oldPath.rename(newPath)

        self.eventHandler.block_future_emit()
        return True

    @Slot(QModelIndex)
    def _view_directory(self, index: QModelIndex | QPersistentModelIndex):
        sourceModel = self.fsModel
        viewModel = self.fsModelViewProxy
        sourceIndex = self.fsModelDirProxy.mapToSource(index)

        if not sourceModel.is_loaded(sourceIndex):
            sourceModel._cache_path(sourceIndex)

        self.folderViewWidget.setRootIndex(
            viewModel.mapFromSource(sourceIndex)
        )

    @Slot(QModelIndex)
    def _view_directory_from_view(self, index: QModelIndex | QPersistentModelIndex):
        sourceModel = self.fsModel
        dirModel = self.fsModelDirProxy
        sourceIndex = self.fsModelViewProxy.mapToSource(index)

        if not sourceModel.is_loaded(sourceIndex):
            sourceModel._cache_path(sourceIndex)

        self.folderViewWidget.setRootIndex(index)

        self.fsTreeWidget.expand(
            dirModel.mapFromSource(sourceIndex)
        )

    @Slot(PurePath, PurePath)
    def _show_conflict_dialog(self, src: PurePath, dst: PurePath):
        conflictDialog = MoveConflictDialog(True, self)
        conflictDialog.set_paths(src, dst)
        conflictDialog.exec()
        self.fsModel.set_conflict_action(conflictDialog._actionRole)
