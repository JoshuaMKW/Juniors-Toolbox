from abc import abstractmethod
from hashlib import new
import shutil
import time
from cmath import exp
from enum import Enum, IntEnum, auto
from pathlib import Path, PurePath
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union

from numpy import source
from soupsieve import select
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
from juniors_toolbox.utils.filesystem import open_path_in_explorer
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
from PySide6.QtCore import (QAbstractItemModel, QDataStream, QEvent, QIODevice,
                            QLine, QMimeData, QModelIndex, QObject, QPoint,
                            QSize, Qt, QThread, QTimer, QUrl, Signal, QItemSelectionModel, QPersistentModelIndex,
                            SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QDragEnterEvent,
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
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

_ASSET_INIT_TABLE = {
    "Animation": {
        BCA: {
            "init_fn": BCA,
            "name": "Joint All",
            "icon": None
        },
        BCK: {
            "init_fn": BCK,
            "name": "Joint Key",
            "icon": None
        },
        BLA: {
            "init_fn": BLA,
            "name": "Cluster All",
            "icon": None
        },
        BLK: {
            "init_fn": BLK,
            "name": "Cluster Key",
            "icon": None
        },
        BPK: {
            "init_fn": BPK,
            "name": "Color Key",
            "icon": None
        },
        BRK: {
            "init_fn": BRK,
            "name": "TEV Register Key",
            "icon": None
        },
        BTK: {
            "init_fn": BTK,
            "name": "Texture SRT Key",
            "icon": None
        },
        BTP: {
            "init_fn": BTP,
            "name": "Texture Palette All",
            "icon": None
        },
        BVA: {
            "init_fn": BVA,
            "name": "Mesh Visibility All",
            "icon": None
        },
    },
    SMSScene: {
        "init_fn": SMSScene,
        "name": "Empty Scene",
        "icon": None
    },
    BMG: {
        "init_fn": BMG,
        "name": "Message Table",
        "icon": None
    },
    PrmFile: {
        "init_fn": PrmFile,
        "name": "Parameter Table",
        "icon": None
    },
}


def generate_asset_menu(parent: QWidget) -> QMenu:
    createMenu = QMenu("Create", parent)
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
                if assetInfo["icon"] is None:
                    action = ProjectCreateAction(_menu)
                    action._init_fn_ = assetInfo["init_fn"]
                    action.setText(assetInfo["name"])
                else:
                    action = QAction(
                        assetInfo["icon"], assetInfo["name"], _menu)
                _menu.addAction(action)

    traverse_structure(createMenu, _ASSET_INIT_TABLE)
    return createMenu


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
    class _EmptyFile(A_Serializable):
        @classmethod
        def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional[A_Serializable]:
            return ProjectCreateAction._EmptyFile()

        def to_bytes(self) -> bytes:
            return b""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def init_file(self) -> A_Serializable:
        return ProjectCreateAction._EmptyFile()


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


class ProjectFolderViewWidget(InteractiveListView, A_FileSystemViewer):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        A_FileSystemViewer.__init__(self)

        self.setUniformItemSizes(True)
        self.setFlow(QListView.LeftToRight)
        self.setGridSize(QSize(88, 98))
        self.setIconSize(QSize(64, 64))
        self.setResizeMode(QListView.Adjust)
        self.setViewMode(QListView.IconMode)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListView.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListView.ExtendedSelection)
        self.setSelectionBehavior(QListView.SelectItems)
        self.setEditTriggers(QListView.NoEditTriggers)

        self.__selectedItemsOnDrag: list[ProjectAssetListItem] = []

    def get_source_model(self) -> QAbstractItemModel:
        proxy: JSystemFSSortProxyModel = self.model()
        return proxy.sourceModel()

    def set_source_model(self, model: QAbstractItemModel) -> None:
        proxy: JSystemFSSortProxyModel = self.model()
        proxy.setSourceModel(model)

    def create_item(self, action: ProjectCreateAction) -> None:
        ...

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint) -> None:
        # Infos about the node selected.
        index = self.indexAt(point)

        createMenu = QMenu("Create", self)
        folderAction = ProjectCreateAction(createMenu)
        folderAction.setText("Folder")
        folderAction.triggered.connect(
            lambda _action: self.create_item(_action)
        )

        def traverse_structure(_menu: QMenu, initTable: dict):
            for assetKind, assetInfo in initTable.items():
                if isinstance(assetKind, str):
                    subMenu = QMenu(assetKind)
                    traverse_structure(subMenu, assetInfo)
                    _menu.addMenu(subMenu)
                    _menu.addSeparator()
                else:
                    if assetInfo["icon"] is None:
                        action = ProjectCreateAction(_menu)
                        action._init_fn_ = assetInfo["init_fn"]
                        action.setText(assetInfo["name"])
                    else:
                        action = QAction(
                            assetInfo["icon"], assetInfo["name"], _menu)
                    action.clicked.connect(
                        lambda _action: self.create_item(_action)
                    )
                    _menu.addAction(action)

        traverse_structure(createMenu, _ASSET_INIT_TABLE)

        viewAction = QAction("Show in Explorer", self)
        viewAction.triggered.connect(
            lambda clicked=None: self.openExplorerRequested.emit(index)
        )

        # We build the menu.
        if index.isValid():
            menu = self.get_context_menu(point)
            if menu is None:
                return

            openAction = QAction("Open", self)
            openAction.triggered.connect(
                lambda clicked=None: self.openRequested.emit(index)
            )
            beforeAction = menu.actions()
            beforeAction = beforeAction[0]
            menu.insertMenu(beforeAction, createMenu)
            menu.insertSeparator(beforeAction)
            menu.insertAction(beforeAction, viewAction)
            menu.insertSeparator(beforeAction)
            menu.insertAction(beforeAction, openAction)
        else:
            menu = QMenu(self)
            menu.addMenu(createMenu)
            menu.addSeparator()
            menu.addAction(viewAction)

        menu.exec(self.mapToGlobal(point))

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

        self.__selectedIndexesOnDrag = self.selectedIndexes()
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
            if hoveredIndex in self.__selectedIndexesOnDrag:
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
            self.move_indexes(self.__selectedIndexesOnDrag, hoveredIndex)
            event.accept()
        else:
            event.ignore()
        return

    @Slot(QKeyEvent)
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        indexes = self.selectedIndexes()

        if event.key() == Qt.Key_Delete:
            self.delete_indexes(indexes)
            event.accept()
            return

        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_C:
                mimeData = QMimeData()
                clipboard = QApplication.clipboard()

                urlList = []
                for index in indexes:
                    url = QUrl.fromLocalFile(
                        index.data(JSystemFSModel.FilePathRole)
                    )
                    urlList.append(url)
                mimeData.setUrls(urlList)
                clipboard.setMimeData(mimeData)
            elif key == Qt.Key_V:
                mimeData = QApplication.clipboard().mimeData()
                paths = []
                for url in mimeData.urls():
                    path = Path(url.toLocalFile())
                    paths.append(path)
                self.dropInRequested.emit(paths)

        event.accept()

    @Slot(list, QModelIndex)
    def move_indexes(self, indexesToMove: list[QModelIndex | QPersistentModelIndex], parentIndex: QModelIndex | QPersistentModelIndex) -> bool:
        proxyModel: JSystemFSSortProxyModel = self.model()
        sourceParent = proxyModel.mapToSource(parentIndex)
        sourceModel: JSystemFSModel = sourceParent.model()

        if not (sourceModel.is_dir(sourceParent) or sourceModel.is_archive(sourceParent)):
            return False

        conflictDialog = MoveConflictDialog(
            len(indexesToMove) > 1,
            self
        )

        for index in indexesToMove:
            sourceIndex = proxyModel.mapToSource(index)
            sourcePath: PurePath = sourceIndex.data(
                JSystemFSModel.FilePathRole)
            destPath: PurePath = sourceParent.data(
                JSystemFSModel.FilePathRole) / sourcePath.name

            destIndex = sourceModel.get_path_index(destPath)
            if destIndex.isValid() and not conflictDialog.apply_to_all():
                conflictDialog.set_paths(sourcePath, destPath.parent)

                action, role = conflictDialog.resolve()
                if action == QDialog.Rejected:
                    return False

                if role == MoveConflictDialog.ActionRole.REPLACE:
                    sourcePath.replace(destPath)
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
            sourceModel.move(sourceIndex, sourceParent)


class ProjectHierarchyViewWidget(QTreeWidget, A_FileSystemViewer):
    ExpandTime = 0.8  # Seconds

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.__rootFsItem: Optional[ProjectHierarchyItem] = None
        self.__dragHoverItem: Optional[ProjectHierarchyItem] = None
        self.__dragPreSelected = False
        self.__expandTimer = time.time()
        self.__expandCheckTimer = QTimer(self)
        self.__expandCheckTimer.timeout.connect(self.check_expand)
        self.__expandCheckTimer.start(10)

        self.itemChanged.connect(
            lambda item: self.renameRequested.emit(item)
        )
        self.customContextMenuRequested.connect(
            self.custom_context_menu
        )

    def get_fs_tree_item(self, path: Optional[Path]) -> Optional[ProjectHierarchyItem]:
        if path is None:
            return None
        if path == Path():
            return self.topLevelItem(0)
        possibleItems: list[ProjectHierarchyItem] = self.findItems(
            path.name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        if len(possibleItems) == 0:
            return None
        for pItem in possibleItems:
            pPath = pItem.get_relative_path()
            if pPath == path:
                return pItem
        return None

    def view(self, __p: Path, /) -> None:
        fsItem = self.get_fs_tree_item(self.focusedPath)
        while fsItem:
            fsItem.setExpanded(False)
            fsItem = fsItem.parent()

        self._focusedPath = __p

        fsItem = self.get_fs_tree_item(__p)
        while fsItem:
            fsItem.setExpanded(True)
            fsItem = fsItem.parent()

    def view_project(self, path: Path) -> None:
        """
        Path is absolute to scene
        """
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
            Qt.ItemIsEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsSelectable
        )
        __inner_recurse_tree(self.__rootFsItem, path)

        self.addTopLevelItem(self.__rootFsItem)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)

        self.__apply_expand_tree(expandTree)

        self.__rootFsItem.setExpanded(True)

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint) -> None:
        # Infos about the node selected.
        index = self.indexAt(point)

        if not index.isValid():
            return

        item: ProjectHierarchyItem = self.itemAt(point)
        itemList = [item]

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
            lambda clicked=None: self.deleteRequested.emit(itemList)
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

    def check_expand(self) -> None:
        if self.__dragHoverItem is None:
            self.__expandTimer = time.time()
            self.__dragPreSelected = False
            return

        if time.time() - self.__expandTimer > self.ExpandTime:
            self.__dragHoverItem.setExpanded(True)
            self.__expandTimer = time.time()

    @Slot(ProjectHierarchyItem)
    def editItem(self, item: ProjectHierarchyItem) -> None:
        item._preRenamePath = item.get_relative_path()
        super().editItem(item)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mimeData = event.mimeData()

        if not mimeData.hasUrls():
            event.ignore()

        self.__dragHoverItem = self.itemAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverItem is None else self.__dragHoverItem.isSelected()
        self.__expandTimer = time.time()
        event.acceptProposedAction()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        mimeData = event.mimeData()
        if not mimeData.hasUrls():
            event.ignore()

        if self.__dragHoverItem is None:
            event.acceptProposedAction()
            return

        item = self.itemAt(event.pos())
        if item != self.__dragHoverItem:
            if not self.__dragPreSelected:
                self.setSelection(
                    self.visualItemRect(self.__dragHoverItem),
                    QItemSelectionModel.Deselect | QItemSelectionModel.Rows
                )
            self.__expandTimer = time.time()
            self.__dragHoverItem = item
            self.__dragPreSelected = False if item is None else item.isSelected()

        if not self.__dragHoverItem in self.selectedItems():
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Select | QItemSelectionModel.Rows
            )

        if self.__dragHoverItem:
            for url in mimeData.urls():
                path = Path(url.toLocalFile())
                if path.parent == self.scenePath / self.__dragHoverItem.get_relative_path():
                    event.ignore()
        event.acceptProposedAction()

    @Slot(QDragLeaveEvent)
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        if self.__dragHoverItem is None:
            event.accept()
            return

        if not self.__dragPreSelected:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Deselect | QItemSelectionModel.Rows
            )
        self.__expandTimer = time.time()
        self.__dragHoverItem = None
        self.__dragPreSelected = False

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        targetItem = self.__dragHoverItem

        self.__dragHoverItem = None
        if md.hasUrls():
            paths = [url.toLocalFile() for url in md.urls()]
            self.moveRequested.emit(paths, targetItem)
            event.accept()
            return
        event.ignore()

    @Slot(QMouseEvent)
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        event.ignore()

    def __record_expand_tree(self) -> dict:
        tree = {}

        def __inner_recurse(parent: ProjectHierarchyItem):
            nonlocal tree
            for i in range(parent.childCount()):
                child: ProjectHierarchyItem = parent.child(i)
                __inner_recurse(child)
                tree[child.get_relative_path()] = child.isExpanded()
        for i in range(self.topLevelItemCount()):
            child: ProjectHierarchyItem = self.topLevelItem(i)
            __inner_recurse(child)
            tree[child.get_relative_path()] = child.isExpanded()
        return tree

    def __apply_expand_tree(self, tree: dict):
        def __inner_recurse(parent: ProjectHierarchyItem):
            nonlocal tree
            for i in range(parent.childCount()):
                child: ProjectHierarchyItem = parent.child(i)
                __inner_recurse(child)
                child.setExpanded(tree.setdefault(
                    child.get_relative_path(), False))
        for i in range(self.topLevelItemCount()):
            child: ProjectHierarchyItem = self.topLevelItem(i)
            __inner_recurse(child)
            child.setExpanded(tree.setdefault(
                child.get_relative_path(), False))


class ProjectTreeViewWidget(InteractiveTreeView, A_FileSystemViewer):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

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

        newAssetMenu = generate_asset_menu(self)
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

        menu.addMenu(newAssetMenu)
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

        self.fsModel = JSystemFSModel(None, False, self)

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
