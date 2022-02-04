from hashlib import new
import shutil
import time
from cmath import exp
from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from juniors_toolbox.gui.dialogs.moveconflict import MoveConflictDialog

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
                            QSize, Qt, QThread, QTimer, QUrl, Signal, QItemSelectionModel, QPersistentModelIndex,
                            SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDrag, QDragEnterEvent,
                           QDragLeaveEvent, QDragMoveEvent, QDropEvent, QIcon,
                           QImage, QKeyEvent, QMouseEvent, QPaintDevice,
                           QPainter, QPaintEvent, QPalette, QPixmap, QPen,
                           QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QMenu, QMenuBar, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem,
                               QSplitter, QStyle, QStyleOptionComboBox,
                               QStylePainter, QTableWidget, QTableWidgetItem,
                               QToolBar, QTreeWidget, QTreeWidgetItem, QDialog, QDialogButtonBox, QApplication,
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

def _fs_resolve_name(name: str, dir: Path):
    maxIterations = 1000
    parts = name.rsplit(".", 1)
    name = parts[0]

    renameContext = 1
    ogName = name

    possibleNames = []
    for item in dir.iterdir():
        if renameContext > maxIterations:
            raise FileExistsError(
                f"Name exists beyond {maxIterations} unique iterations!")
        if item.name.startswith(ogName):
            possibleNames.append(item.name.rsplit(".", 1)[0])

    i = 0
    while True:
        if i >= len(possibleNames):
            break
        if renameContext > maxIterations:
            raise FileExistsError(
                f"Name exists beyond {maxIterations} unique iterations!")
        if possibleNames[i] == name:
            name = f"{ogName}{renameContext}"
            renameContext += 1
            i = 0
        else:
            i += 1
    if len(parts) == 2:
        name += f".{parts[1]}"
    return name


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
    QListWidgetItem
    openExplorerRequested: SignalInstance = Signal(object)
    openRequested: SignalInstance = Signal(object)
    createFolderRequested: SignalInstance = Signal(str)
    copyRequested: SignalInstance = Signal(
        list, list)
    moveRequested: SignalInstance = Signal(list, object)
    renameRequested: SignalInstance = Signal(object)
    deleteRequested: SignalInstance = Signal(list)
    dropInRequested: SignalInstance = Signal(list)
    dropOutRequested: SignalInstance = Signal(object)


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
        self.setDragDropMode(InteractiveListWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setUniformItemSizes(True)

        self.__scenePath: Path = None
        self.__focusedPath: Path = None
        self.__selectedItemsOnDrag: List[ProjectAssetListItem] = []

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
    def move_items(self, items: List[ProjectAssetListItem], targetItem: ProjectAssetListItem) -> List[Path]:
        """
        Moves the items in the filesystem
        """
        if not targetItem.is_folder():
            return

        self.moveRequested.emit(items, targetItem)

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

        # -- ICON -- #

        if supportedActions & Qt.MoveAction:
            items = self.selectedItems()
            if len(items) == 0:
                return

            pixmap = QPixmap(70, 80)
            pixmap.fill(Qt.transparent)

            #pen = QPen()

            painter = QPainter()
            painter.begin(pixmap)

            font = painter.font()
            font.setPointSize(6)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Qt.NoPen)

            painter.setBrush(QColor(20, 150, 220, 70))
            painter.drawRoundedRect(0, 0, 70, 80, 5, 5)

            if len(items) == 1:
                icon = items[0].icon()
                iconPixmap = QPixmap(icon.pixmap(icon.actualSize(QSize(64, 64)))).scaled(64, 64)
                painter.drawPixmap(3, 8, iconPixmap)
            else:
                fontMetrics = painter.fontMetrics()
                textWidth = fontMetrics.boundingRect(str(len(items))).width()
                painter.setPen(Qt.white)
                painter.setBrush(QColor(20, 110, 220, 255))
                painter.drawRect(27, 32, 16, 16)
                painter.drawText(35 - (textWidth/2), 43, str(len(items)))

            painter.end()

            drag.setPixmap(pixmap)
            drag.setHotSpot(pixmap.rect().center() + QPoint(0, 20))

        drag.exec(supportedActions)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if not event.mimeData().hasUrls():
            event.ignore()

        self.__selectedItemsOnDrag = self.selectedItems()
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        eventPos = event.pos()
        rect = self.rect()
        item: ProjectAssetListItem = self.itemAt(eventPos)
        if event.mimeData().hasUrls():
            if item is None:
                super().dragMoveEvent(event)
                if event.source() == self:
                    event.ignore()
                return
            else:
                if item.is_folder():
                    super().dragMoveEvent(event)
                    if item in self.__selectedItemsOnDrag:
                        event.ignore()
                    return
            if not rect.contains(eventPos):
                super().dragMoveEvent(event)
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        mimeData = event.mimeData()
        if not mimeData.hasUrls():
            return

        item: ProjectAssetListItem = self.itemAt(event.pos())
        if item is None and event.source() != self:
            paths = []
            for url in mimeData.urls():
                path = Path(url.toLocalFile())
                paths.append(path)
            self.dropInRequested.emit(paths)
            event.accept()
        if item is not None and item.is_folder():
            self.move_items(self.selectedItems(), item)
            event.accept()
        else:
            event.ignore()
        return

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete:
            self.delete_items(self.selectedItems())
            event.accept()
            return
        
        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_C:
                mimeData = QMimeData()
                clipboard = QApplication.clipboard()

                urlList = []
                for item in self.selectedItems():
                    path = QUrl.fromLocalFile(
                        self.scenePath / self.focusedPath / item.text())
                    urlList.append(path)
                mimeData.setUrls(urlList)
                clipboard.setMimeData(mimeData)
            elif key == Qt.Key_V:
                text = QApplication.clipboard().text()
                mimeData = QApplication.clipboard().mimeData()
                paths = []
                for url in mimeData.urls():
                    path = Path(url.toLocalFile())
                    paths.append(path)
                self.dropInRequested.emit(paths)
        event.accept()


class ProjectHierarchyViewWidget(QTreeWidget, FileSystemViewer):
    ExpandTime = 0.8  # Seconds

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
        self.__expandTimer = time.time()
        self.__dragHoverItem: ProjectHierarchyItem = None
        self.__dragPreSelected = False
        self.__expandCheckTimer = QTimer(self)
        self.__expandCheckTimer.timeout.connect(self.check_expand)
        self.__expandCheckTimer.start(10)

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

    def check_expand(self):
        if self.__dragHoverItem is None:
            self.__expandTimer = time.time()
            self.__dragPreSelected = False

        if time.time() - self.__expandTimer > self.ExpandTime:
            self.__dragHoverItem.setExpanded(True)
            self.__expandTimer = time.time()

    @Slot(ProjectHierarchyItem)
    def editItem(self, item: ProjectHierarchyItem):
        item._preRenamePath = item.get_relative_path()
        super().editItem(item)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent):
        mimeData = event.mimeData()
        
        if not mimeData.hasUrls():
            event.ignore()

        self.__dragHoverItem = self.itemAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverItem is None else self.__dragHoverItem.isSelected()
        self.__expandTimer = time.time()
        event.acceptProposedAction()
        return

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent):
        mimeData = event.mimeData()
        if not mimeData.hasUrls():
            event.ignore()

        if self.__dragHoverItem is None:
            event.acceptProposedAction()
    
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
    def dragLeaveEvent(self, event: QDragLeaveEvent):
        if self.__dragHoverItem is None:
            event.accept()
    
        if not self.__dragPreSelected:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Deselect | QItemSelectionModel.Rows
            )
        self.__expandTimer = time.time()
        self.__dragHoverItem = None
        self.__dragPreSelected = False


    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent):
        md = event.mimeData()
        targetItem = self.__dragHoverItem

        self.__dragHoverItem = None
        if md.hasUrls():
            paths = [url.toLocalFile() for url in md.urls()]
            self.moveRequested.emit(paths, targetItem)
            event.accept()
            return
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
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
        self.folderViewWidget.moveRequested.connect(self.move_items)
        self.folderViewWidget.dropInRequested.connect(
            self.copy_paths_to_focused
        )

        self.focusedViewWidget.folderChangeRequested.connect(self.view_folder)

        self.fsTreeWidget.openExplorerRequested.connect(self.explore_item)
        self.fsTreeWidget.openRequested.connect(self.open_item)
        self.fsTreeWidget.deleteRequested.connect(self.delete_items)
        self.fsTreeWidget.renameRequested.connect(self.rename_item)
        self.fsTreeWidget.moveRequested.connect(self.move_items)
        self.fsTreeWidget.dropInRequested.connect(
            self.copy_paths_to_focused
        )

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

    
    @Slot(list, ProjectHierarchyItem)
    @Slot(list, ProjectAssetListItem)
    @Slot(list, Path)
    def move_items(
        self,
        items: Union[List[ProjectHierarchyItem], List[ProjectAssetListItem]],
        target: Union[ProjectHierarchyItem, ProjectAssetListItem, Path]
    ):
        if self.__ignoreItemRename:
            return

        isFsItem = isinstance(target, ProjectHierarchyItem)
        isPath = isinstance(target, (Path, str))

        if target is None:
            targetItemPath = Path()
        elif isPath:
            targetItemPath = Path(target)
        elif isFsItem:
            targetItemPath = target.get_relative_path()
        else:
            targetItemPath = self.focusedPath / target.text()

        conflictDialog = MoveConflictDialog(len(items) > 1, self)
        for item in items:
            if isinstance(item, (Path, str)):
                item = Path(item)
                self.__move_path(
                    self.scenePath / item,
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

    @Slot(list)
    def copy_paths_to_focused(self, paths: List[Path]):
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

    def __move_item(self, src: Union[ProjectHierarchyItem, ProjectAssetListItem], dst: Path, conflictDialog: MoveConflictDialog) -> bool:
        isFsItem = isinstance(src, ProjectHierarchyItem)
        if isFsItem:
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

    def __show_conflicting_move(self, path: Path, target: Path, isMulti: bool) -> Tuple[QDialog.DialogCode, MoveConflictDialog.ActionRole, bool]:
        dialog = MoveConflictDialog(path, target, isMulti, self)
        return dialog.exec(), dialog.actionRole, dialog.allCheckBox.isChecked()