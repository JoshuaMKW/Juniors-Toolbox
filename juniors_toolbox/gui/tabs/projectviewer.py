import shutil
import time
from cmath import exp
from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from juniors_toolbox.gui.images import get_icon, get_image
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.interactivelist import InteractiveListWidget, InteractiveListWidgetItem
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import Serializable
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
                            QSize, Qt, QThread, QTimer, QUrl, Signal,
                            SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QDragEnterEvent,
                           QDragLeaveEvent, QDragMoveEvent, QDropEvent, QIcon,
                           QImage, QKeyEvent, QMouseEvent, QPaintDevice,
                           QPainter, QPaintEvent, QPalette, QPixmap,
                           QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QMenuBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem,
                               QSplitter, QStyle, QStyleOptionComboBox,
                               QStylePainter, QTableWidget, QTableWidgetItem,
                               QToolBar, QTreeWidget, QTreeWidgetItem,
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
    doubleClicked: SignalInstance = Signal(InteractiveListWidgetItem)

    MIME_FORMAT = __name__
    _init_fn_: Callable[[], Serializable]

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
        self.__icon = icon

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

        self._init_fn_ = None

    def clone(self) -> "ProjectAssetListItem":
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
    _init_fn_: Callable[[], Serializable]

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        self.setFlags(flags)
        self.setText(0, name)

        self._preRenamePath = ""

        self._init_fn_ = None

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
    clicked: SignalInstance = Signal(QAction)

    def __init__(self, initFn: Callable[[], Serializable], parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._init_fn_ = initFn
        self.triggered.connect(self.__click)

    def __click(self, toggled: bool):
        self.clicked.emit(self)


class ProjectFocusedMenuBarAction(QAction):
    clicked: SignalInstance = Signal(QAction)

    def __init__(self, isRoot: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.isRoot = isRoot
        self.triggered.connect(self.__click)

    def __click(self, toggled: bool):
        self.clicked.emit(self)


class FileSystemViewer():
    openExplorerRequested: SignalInstance = Signal(ProjectAssetListItem)
    openRequested: SignalInstance = Signal(ProjectAssetListItem)
    createFolderRequested: SignalInstance = Signal(str)
    copyRequested: SignalInstance = Signal(
        list, list)
    renameRequested: SignalInstance = Signal(ProjectAssetListItem)
    deleteRequested: SignalInstance = Signal(list)
    dropInRequested: SignalInstance = Signal(Path)
    dropOutRequested: SignalInstance = Signal(ProjectAssetListItem)


class ProjectFocusedMenuBar(QMenuBar):
    folderChangeRequested: SignalInstance = Signal(Path)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setNativeMenuBar(False)
        # self.setFloatable(False)

        self.__scenePath: Path = None
        self.__focusedPath: Path = None

        self.__parts: List[ProjectFocusedMenuBarAction] = []

        font = self.font()
        font.setBold(True)
        self.setFont(font)

    @property
    def scenePath(self) -> Path:
        return self.__scenePath

    @scenePath.setter
    def scenePath(self, path: Path):
        self.__scenePath = path
        self.__focusedPath = Path()
        self.view(self.__focusedPath)

    @property
    def focusedPath(self) -> Path:
        return self.__focusedPath

    @focusedPath.setter
    def focusedPath(self, path: Path):
        self.view(path)

    def get_focused_path_to(self, item: Union[ProjectFocusedMenuBarAction, QMenu], name: str):
        if isinstance(item, ProjectFocusedMenuBarAction) and item.isRoot:
            return self.scenePath

        subPath = Path()
        for part in self.__parts:
            if part == item:
                break
            if isinstance(part, ProjectFocusedMenuBarAction) and not part.isRoot:
                subPath = subPath / part.text()

        return subPath / name

    def view(self, path: Path):
        """
        Path is relative to scene path
        """
        self.clear()
        self.__parts.clear()
        if not path.is_absolute():
            self.__focusedPath = path
        else:
            self.__focusedPath = path.relative_to(self.scenePath)

        sceneItem = ProjectFocusedMenuBarAction(True, self)
        sceneItem.setText(self.scenePath.name)
        sceneItem.clicked.connect(self.check_clicked)
        self.addAction(sceneItem)

        self.__parts.append(sceneItem)
        self.__populate_from_path(self.__focusedPath)

    @Slot(ProjectFocusedMenuBarAction)
    def check_clicked(self, clicked: ProjectFocusedMenuBarAction):
        parent = clicked.parent()
        tname = clicked.text()
        if isinstance(parent, QMenu):
            target = parent
        else:
            target = clicked
        path = self.get_focused_path_to(target, tname)
        if self.__focusedPath == path:
            clicked.setChecked(True)
        else:
            self.folderChangeRequested.emit(path)

    def __populate_from_path(self, path: Path):
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


class ProjectFolderViewWidget(InteractiveListWidget, FileSystemViewer):
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

        self.__scenePath: Path = None
        self.__focusedPath: Path = None

    @property
    def scenePath(self) -> Path:
        return self.__scenePath

    @scenePath.setter
    def scenePath(self, path: Path):
        self.__scenePath = path
        self.__focusedPath = Path()
        self.view(self.__focusedPath)

    @property
    def focusedPath(self) -> Path:
        return self.__focusedPath

    @focusedPath.setter
    def focusedPath(self, path: Path):
        self.view(path)

    def view(self, path: Path):
        """
        Path is relative to scenePath
        """
        self.setSortingEnabled(False)
        self.clear()
        if not path.is_absolute():
            path = self.scenePath / path
            self.__focusedPath = path
        else:
            self.__focusedPath = path.relative_to(self.scenePath)
        if not path.is_dir():
            return
        for entry in path.iterdir():
            item = ProjectAssetListItem(entry.name, entry.is_dir())
            self.addItem(item)
        self.setSortingEnabled(True)
        self.sortItems(Qt.SortOrder.AscendingOrder)

    def create_item(self, action: ProjectCreateAction, isFolder: bool):
        item = ProjectAssetListItem("untitled", isFolder)
        item._init_fn_ = action._init_fn_
        self.addItem(item)
        self.editItem(item)

    @Slot(list)
    def delete_items(self, items: List[ProjectAssetListItem]):
        super().delete_items(items)
        if len(items) == 0:
            return
        self.deleteRequested.emit(items)

    @Slot(ProjectAssetListItem, result=str)
    def rename_item(self, item: ProjectAssetListItem) -> ProjectAssetListItem:
        """
        Returns the new name of the item
        """
        name = super().rename_item(item)
        if name == "":
            return None
        self.renameRequested.emit(item)
        return item

    @Slot(list, result=list)
    def duplicate_items(self, items: List[ProjectAssetListItem]) -> List[ProjectAssetListItem]:
        """
        Returns the new name of the item
        """
        nitems = super().duplicate_items(items)
        if len(nitems) == 0:
            return []
        self.copyRequested.emit(items, nitems)
        return nitems

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint):
        # Infos about the node selected.
        item: ProjectHierarchyItem = self.itemAt(point)

        createMenu = QMenu("Create", self)
        folderAction = ProjectCreateAction(None, createMenu)
        folderAction.setText("Folder")
        folderAction.triggered.connect(
            lambda _action: self.create_item(_action, True))

        def traverse_structure(_menu: QMenu, initTable: dict):
            for assetKind, assetInfo in initTable.items():
                if isinstance(assetKind, str):
                    subMenu = QMenu(assetKind)
                    traverse_structure(subMenu, assetInfo)
                    _menu.addMenu(subMenu)
                    _menu.addSeparator()
                else:
                    if assetInfo["icon"] is None:
                        action = ProjectCreateAction(
                            assetInfo["init_fn"], _menu)
                        action.setText(assetInfo["name"])
                    else:
                        action = QAction(
                            assetInfo["icon"], assetInfo["name"], _menu)
                    action.clicked.connect(
                        lambda _action: self.create_item(_action, False))
                    _menu.addAction(action)

        traverse_structure(createMenu, _ASSET_INIT_TABLE)

        viewAction = QAction("Show in Explorer", self)
        viewAction.triggered.connect(
            lambda clicked=None: self.openExplorerRequested.emit(item)
        )

        # We build the menu.
        if item is not None:
            menu = self.get_context_menu(point)
            openAction = QAction("Open", self)
            openAction.triggered.connect(
                lambda clicked=None: self.openRequested.emit(item)
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

    def _resolve_name(self, name: str, filterItem: InteractiveListWidgetItem = None) -> str:
        parts = name.rsplit(".", 1)
        name = parts[0]

        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.count()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = self.item(i)
            if item == filterItem:
                continue
            if item.text().startswith(ogName):
                possibleNames.append(item.text().rsplit(".", 1)[0])

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

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        item: ProjectAssetListItem = self.itemAt(event.pos())
        if not item.is_folder():
            event.ignore()
            return
        super().mouseDoubleClickEvent(event)

    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        drag = QDrag(self)
        items = self.selectedItems()
        indexes = self.selectedIndexes()
        mime = self.model().mimeData(indexes)
        urlList = []
        for item in items:
            urlList.append(QUrl.fromLocalFile(
                self.scenePath / self.focusedPath / item.text()))
        mime.setUrls(urlList)
        drag.setMimeData(mime)
        drag.exec(supportedActions)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        from juniors_toolbox.gui.application import JuniorsToolbox
        md = event.mimeData()
        if md.hasUrls():
            app = JuniorsToolbox.get_instance()
            appRect = app.gui.rect()
            for url in md.urls():
                path = Path(url.toLocalFile())
                if appRect.contains(self.mapTo(app.gui, event.pos())):
                    self.dropInRequested.emit(path)
                else:
                    self.dropOutRequested.emit(path)
            event.acceptProposedAction()


class ProjectHierarchyViewWidget(QTreeWidget, FileSystemViewer):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.__scenePath: Path = None
        self.__focusedPath: Path = None
        self.__rootFsItem: ProjectHierarchyItem = None
        self.__dragHasFolders = False

        self.itemChanged.connect(
            lambda item: self.renameRequested.emit(item)
        )
        self.customContextMenuRequested.connect(
            self.custom_context_menu
        )

    @property
    def scenePath(self) -> Path:
        return self.__scenePath

    @scenePath.setter
    def scenePath(self, path: Path):
        self.__scenePath = path
        self.view(self.__scenePath)

    @property
    def focusedPath(self) -> Path:
        return self.__focusedPath

    @focusedPath.setter
    def focusedPath(self, path: Path):
        fsItem = self.get_fs_tree_item(self.__focusedPath)
        while fsItem:
            fsItem.setExpanded(False)
            fsItem = fsItem.parent()

        self.__focusedPath = path

        fsItem = self.get_fs_tree_item(path)
        while fsItem:
            fsItem.setExpanded(True)
            fsItem = fsItem.parent()

    def get_fs_tree_item(self, path: Path) -> ProjectHierarchyItem:
        if path is None:
            return None
        if path == Path():
            return self.topLevelItem(0)
        possibleItems: List[ProjectHierarchyItem] = self.findItems(
            path.name, Qt.MatchExactly | Qt.MatchRecursive, 0)
        if len(possibleItems) == 0:
            return None
        for pItem in possibleItems:
            pPath = pItem.get_relative_path()
            if pPath == path:
                return pItem
        return None

    def view(self, path: Path):
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

    def editItem(self, item: ProjectHierarchyItem):
        item._preRenamePath = item.get_relative_path()
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
            lambda clicked=None: self.editItem(item)
        )

        menu.addAction(viewAction)
        menu.addSeparator()
        menu.addAction(openAction)
        menu.addAction(deleteAction)
        menu.addAction(renameAction)

        menu.exec(self.mapToGlobal(point))

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent):
        mimeData = event.mimeData()
        isInternal = isinstance(event.source(), ProjectFolderViewWidget)
        if mimeData.hasUrls():
            for url in mimeData.urls():
                if Path(url.toLocalFile()).is_dir():
                    self.__dragHasFolders = True
                    event.acceptProposedAction()
                    return
        self.__dragHasFolders = False
        event.ignore()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent):
        if self.__dragHasFolders:
            event.acceptProposedAction()
        else:
            event.ignore()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent): ...

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
        self.__scenePath: Path = None
        self.__focusedPath: Path = None
        self.__ignoreItemRename = False
        self.__openTable = {}

        self.mainLayout = QHBoxLayout()

        self.fsTreeWidget = ProjectHierarchyViewWidget()

        self.folderWidget = QWidget()

        self.folderViewLayout = QVBoxLayout()
        self.folderViewLayout.setContentsMargins(0, 0, 0, 0)

        self.focusedViewWidget = ProjectFocusedMenuBar()
        self.folderViewWidget = ProjectFolderViewWidget()

        self.folderViewLayout.addWidget(self.focusedViewWidget)
        self.folderViewLayout.addWidget(self.folderViewWidget)

        self.folderWidget.setLayout(self.folderViewLayout)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.fsTreeWidget)
        splitter.addWidget(self.folderWidget)
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
        self.folderViewWidget.copyRequested.connect(self.copy_items)
        self.folderViewWidget.deleteRequested.connect(self.delete_items)
        self.folderViewWidget.renameRequested.connect(self.rename_item)
        self.folderViewWidget.dropInRequested.connect(
            self.copy_path_to_focused)

        self.focusedViewWidget.folderChangeRequested.connect(self.view_folder)

        self.fsTreeWidget.openExplorerRequested.connect(self.explore_item)
        self.fsTreeWidget.openRequested.connect(self.open_item)
        self.fsTreeWidget.deleteRequested.connect(self.delete_items)
        self.fsTreeWidget.renameRequested.connect(self.rename_item)

        #self.updateTimer = QTimer(self)
        # self.updateTimer.timeout.connect(self.update_tree)
        # self.updateTimer.start(10)

        #self.watcherThread = ProjectViewerWidget.ProjectWatcher(app.scenePath)
        # self.watcherThread.start()

    @property
    def scenePath(self) -> Path:
        return self.__scenePath

    @scenePath.setter
    def scenePath(self, path: Path):
        self.__scenePath = path
        self.fsTreeWidget.scenePath = path
        self.folderViewWidget.scenePath = path
        self.focusedViewWidget.scenePath = path

    @property
    def focusedPath(self) -> Path:
        return self.__focusedPath

    @focusedPath.setter
    def focusedPath(self, path: Path):
        self.__focusedPath = path
        self.fsTreeWidget.focusedPath = path
        self.folderViewWidget.focusedPath = path
        self.focusedViewWidget.focusedPath = path

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

    @Slot()
    def update(self):
        self.fsTreeWidget.view(self.scenePath)
        self.folderViewWidget.view(self.focusedPath)
        self.focusedViewWidget.view(self.focusedPath)

    @Slot(ProjectHierarchyItem)
    @Slot(Path)
    def view_folder(self, item: Union[ProjectHierarchyItem, Path]):
        isFsItem = isinstance(item, ProjectHierarchyItem)
        if isFsItem:
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
    def handle_view_double_click(self, item: ProjectAssetListItem):
        self.view_folder(self.focusedPath / item.text())

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def explore_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
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
    def open_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
        if isinstance(item, ProjectAssetListItem) and str(item.get_type()) in self.__openTable:
            self.__open_table[str(item.get_type())]()

    @Slot(list)
    def delete_items(self, _items: Union[List[ProjectHierarchyItem], List[ProjectAssetListItem]]):
        for item in _items:
            isFsItem = isinstance(item, ProjectHierarchyItem)
            if isFsItem:
                path = self.scenePath / item.get_relative_path()
            else:
                path = self.scenePath / self.focusedPath / item.text()

            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

            if isFsItem:
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
                if self.focusedPath.parent is None:
                    self.focusedPath = Path()
                else:
                    self.focusedPath = self.focusedPath.parent

            self.eventHandler.block_future_emit()

    @Slot(ProjectHierarchyItem)
    @Slot(ProjectAssetListItem)
    def rename_item(self, item: Union[ProjectHierarchyItem, ProjectAssetListItem]):
        if self.__ignoreItemRename:
            return

        isFsItem = isinstance(item, ProjectHierarchyItem)

        itemPath = item.get_relative_path() if isFsItem else self.focusedPath / item.text()
        previousPath = self.focusedPath / item._prevName_
        if previousPath == itemPath:
            return

        oldPath = self.scenePath / previousPath
        newPath = self.scenePath / itemPath
        """
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
        """

        if oldPath.exists():
            oldPath.rename(newPath)
        else:
            with newPath.open("wb") as f:
                f.write(item._init_fn_().to_bytes())

        if self.focusedPath == previousPath:
            self.focusedPath = newPath

        if isFsItem:
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

    @Slot(list)
    def copy_items(
        self,
        _oldItems: Union[List[ProjectHierarchyItem], List[ProjectAssetListItem]],
        _newItems: Union[List[ProjectHierarchyItem], List[ProjectAssetListItem]]
    ):
        if self.__ignoreItemRename:
            return

        for oldItem, newItem in zip(_oldItems, _newItems):
            isFsItem = isinstance(oldItem, ProjectHierarchyItem)

            itemPath = newItem.get_relative_path() if isFsItem else self.focusedPath / \
                newItem.text()
            previousPath = oldItem.get_relative_path() if isFsItem else self.focusedPath / \
                oldItem.text()
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

            if isFsItem:
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

    @Slot(Path)
    def copy_path_to_focused(self, path: Path):
        dest = self.scenePath / self.focusedPath / path.name
        if dest == path:
            return

        try:
            if path.is_file():
                shutil.copy(path, self.scenePath /
                            self.focusedPath / path.name)
            else:
                shutil.copytree(path, self.scenePath /
                                self.focusedPath / path.name, dirs_exist_ok=True)
        except PermissionError:
            return

        self.folderViewWidget.addItem(
            ProjectAssetListItem(path.name, path.is_dir()))

    @Slot(str, Path)
    def move_path_from_focused(self, path: Path, dst: Path):
        return
        try:
            shutil.move(self.scenePath / self.focusedPath / name, dst)
        except PermissionError:
            return

        self.folderViewWidget.takeItem(
            self.folderViewWidget.findItems(name, Qt.MatchFlag.MatchExactly))
