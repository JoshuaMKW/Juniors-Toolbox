from io import BytesIO
from os import walk
from pathlib import Path
from queue import LifoQueue
from threading import Event
from typing import Any, Dict, List, Optional, Tuple, Union
from juniors_toolbox import scene

from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.interactivestructs import InteractiveListView
from juniors_toolbox.gui.widgets.listinterface import ListInterfaceWidget
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.jdrama import NameRef
from juniors_toolbox.utils.prm import PrmEntry, PrmFile
from juniors_toolbox.utils.types import RGB8, RGB32, RGBA8, Vec3f
from PySide6.QtCore import (QByteArray, QDataStream, QLine, QMimeData, QSize, QIODevice,
                            QModelIndex, QObject, QPersistentModelIndex, Qt,
                            QTimer, Signal, SignalInstance, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDragEnterEvent, QStandardItemModel, QStandardItem,
                           QDropEvent, QKeyEvent, QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QBoxLayout, QFileDialog, QFormLayout, QFrame, QComboBox, QListView, QDialog, QCompleter, QFileSystemModel, QTreeView,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListWidget, QMenu,
                               QMenuBar, QPushButton, QScrollArea, QSizePolicy,
                               QSpacerItem, QSplitter, QStyle, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)


class PrmEntryItem(QStandardItem):
    _entry: PrmEntry

    def __init__(self, other: PrmEntry | Optional["PrmEntryItem"] = None):
        if isinstance(other, PrmEntryItem):
            super().__init__(other)
            self._entry = other._entry.copy(deep=True)
            return

        super().__init__()

        self._entry = PrmEntry(
            "((null))",
            ""
        )
        if other is None:
            return

        self._entry = other

    def isAutoTristate(self) -> bool:
        return False

    def isCheckable(self) -> bool:
        return False

    def isDragEnabled(self) -> bool:
        return True

    def isDropEnabled(self) -> bool:
        return True

    def isEditable(self) -> bool:
        return True

    def isSelectable(self) -> bool:
        return True

    def isUserTristate(self) -> bool:
        return False

    def read(self, in_: QDataStream) -> None:
        data = QByteArray()
        in_ >> data

        entry = PrmEntry.from_bytes(
            data
        )
        if entry is None:
            return

        self._entry = entry

    def write(self, out: QDataStream) -> None:
        out << self._entry.to_bytes()

    def data(self, role: int = Qt.UserRole + 1) -> Any:
        if role == Qt.DisplayRole:
            return self._entry.key

        if role == Qt.EditRole:
            return self._entry.key

        elif role == Qt.SizeHintRole:
            return QSize(40, self.font().pointSize() * 2)

        elif role == Qt.UserRole + 1:
            return self._entry

    def setData(self, value: Any, role: int = Qt.UserRole + 1) -> None:
        if role == Qt.DisplayRole:
            self._entry.key = value

        if role == Qt.EditRole:
            self._entry.key = value

        elif role == Qt.UserRole + 1:
            self._entry = value

    def clone(self) -> "PrmEntryItem":
        return PrmEntryItem(self)


class PrmEntryListModel(QStandardItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setItemPrototype(PrmEntryItem())

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.CopyAction | Qt.MoveAction

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.CopyAction | Qt.MoveAction

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.UserRole + 1) -> Any:
        if section == 0:
            return "Entries"
        return None

    def itemData(self, index: Union[QModelIndex, QPersistentModelIndex]) -> dict[int, Any]:
        roles = {}
        for i in range(Qt.UserRole + 2):
            variant = self.data(index, i)
            if variant:
                roles[i] = variant
        return roles

    def mimeTypes(self) -> list[str]:
        return ["application/x-prmentrylist"]

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        mimeType = self.mimeTypes()[0]

        encodedData = data.data(mimeType)
        stream = QDataStream(
            encodedData,
            QIODevice.ReadOnly
        )

        itemCount = stream.readInt32()
        if action & Qt.CopyAction:
            for i in range(itemCount):
                item = PrmEntryItem()
                item.read(stream)
                item.setData(
                    self._resolve_name(item.data(Qt.DisplayRole)),
                    Qt.DisplayRole
                )
                self.insertRow(row + i, item)
        else:
            oldItems: list[PrmEntryItem] = []
            for i in range(itemCount):
                item = PrmEntryItem()
                item.read(stream)
                name = item.data(Qt.DisplayRole)
                oldItems.append(
                    self.findItems(name)[0]
                )
                self.insertRow(row + i, item)
            for item in oldItems:
                self.removeRow(item.row())

        return action == Qt.CopyAction

    def mimeData(self, indexes: list[int]) -> QMimeData:
        mimeType = self.mimeTypes()[0]
        mimeData = QMimeData()

        encodedData = QByteArray()
        stream = QDataStream(
            encodedData,
            QIODevice.WriteOnly
        )

        stream.writeInt32(len(indexes))
        for index in indexes:
            item = self.itemFromIndex(index)  # type: ignore
            item.write(stream)

        mimeData.setData(
            mimeType,
            encodedData
        )
        return mimeData

    def _resolve_name(self, name: str, filterItem: Optional[QStandardItem] = None) -> str:
        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.rowCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = self.item(i)
            if item == filterItem:
                continue
            itemText: str = item.data(Qt.DisplayRole)
            if itemText.startswith(ogName):
                possibleNames.append(itemText)

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
        return name


class PrmLocalListModel(QFileSystemModel):
    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = Qt.UserRole + 4) -> Any:
        fp = Path(self.filePath(index))

        if role == Qt.UserRole + 4:
            return PrmFile.from_bytes(
                BytesIO(fp.read_bytes())
            )
        
        return super().data(index, role)

    def setData(self, index: Union[QModelIndex, QPersistentModelIndex], value: Any, role: int = Qt.UserRole + 4) -> bool:
        fp = Path(self.filePath(index))

        if role == Qt.UserRole + 4:
            fp.write_bytes(
                value.to_bytes()
            )
            return True

        return super().setData(index, value, role)


class PrmEntryListWidget(InteractiveListView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(150, 100)

    @Slot(PrmEntryItem)
    def rename_item(self, item: PrmEntryItem):
        name = super().rename_item(item)
        item.entry.key = NameRef(name)

    @Slot(PrmEntryItem)
    def duplicate_item(self, item: PrmEntryItem):
        nitem = super().duplicate_item(item)
        nitem.entry.key = NameRef(nitem.text())


class PrmLocalTreeWidget(QTreeView):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(150, 100)
        self.setUniformRowHeights(True)
        self.setAutoExpandDelay(1)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setEditTriggers(QTreeView.DoubleClicked)
        self.setSelectionBehavior(QTreeView.ExtendedSelection)


class PrmEditorWidget(A_DockingInterface):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(685, 300)

        self.mainLayout = QGridLayout()

        self.scrollArea = QScrollArea()

        self.vBoxLayout = QVBoxLayout()
        self.vBoxLayout.setContentsMargins(10, 0, 10, 10)

        prmEntryListBox = PrmEntryListWidget()
        prmEntryListBox.currentItemChanged.connect(self.show_entry)
        self.prmEntryListBox = prmEntryListBox

        prmEntryListInterface = ListInterfaceWidget()
        prmEntryListInterface.addRequested.connect(self.new_entry)
        prmEntryListInterface.removeRequested.connect(
            self.remove_selected_entries)
        prmEntryListInterface.copyRequested.connect(self.duplicate_selected_entries)
        self.prmEntryListInterface = prmEntryListInterface

        prmEntryListLayout = QVBoxLayout()
        prmEntryListLayout.addWidget(prmEntryListInterface)
        prmEntryListLayout.addWidget(prmEntryListBox)
        prmEntryListLayout.setContentsMargins(0, 0, 0, 0)

        prmEntryListWidget = QWidget()
        prmEntryListWidget.setLayout(prmEntryListLayout)
        prmEntryListWidget.setEnabled(False)
        self.prmEntryListWidget = prmEntryListWidget

        prmEntryEditor = PrmEntryListWidget()
        prmEntryEditor.entryUpdateRequested.connect(
            self.update_entry
        )
        self.prmEntryEditor = prmEntryEditor

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(prmEntryListWidget)
        splitter.addWidget(prmEntryEditor)
        self.splitter = splitter

        self.vBoxLayout.addWidget(self.splitter)

        self.scrollArea.setLayout(self.vBoxLayout)
        
        self.mainLayout.addWidget(self.scrollArea)
        self.setLayout(self.mainLayout)

        self.entries: List[PrmEntry] = []

        self.__cachedOpenPath: Optional[Path] = None

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs):
        data = args[0]
        if not isinstance(data, PrmFile):
            return

        self.prmEntryListBox.clear()

        for i, entry in enumerate(data.iter_entries()):
            if entry.key == "":
                raise ValueError("Empty Key is invalid")
            listItem = PrmEntryItem(entry.key.get_ref(), entry)
            self.prmEntryListBox.addItem(listItem)

        if self.prmEntryListBox.count() > 0:
            self.prmEntryListBox.setCurrentRow(0)
            self.prmEntryListWidget.setEnabled(True)

    @Slot()
    def new_prm(self):
        self.populate(PrmFile())
        self.prmEntryListWidget.setEnabled(True)

    @Slot(Path)
    def open_prm(self, path: Optional[Path] = None):
        if path is None:
            dialog = QFileDialog(
                parent=self,
                caption="Open PRM...",
                directory=str(
                    self.__cachedOpenPath.parent if self.__cachedOpenPath else Path.home()
                ),
                filter="Parameters (*.prm);;All files (*)"
            )

            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setFileMode(QFileDialog.AnyFile)

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self.__cachedOpenPath = path

        with path.open("rb") as f:
            prm = PrmFile.from_bytes(f)

        manager = ToolboxManager.get_instance()
        self.populate(manager.get_scene(), prm)

    @Slot()
    def close_prm(self):
        self.prmEntryListBox.clear()
        self.prmEntryEditor.setEnabled(False)

    @Slot(Path, bool)
    def save_bmg(self, path: Optional[Path] = None):
        dialog = QFileDialog(
            parent=self,
            caption="Save PRM...",
            directory=str(
                self.__cachedOpenPath.parent if self.__cachedOpenPath else Path.home()
            ),
            filter="Parameters (*.prm);;All files (*)"
        )

        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setFileMode(QFileDialog.AnyFile)

        if path is None:
            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self.__cachedOpenPath = path

        prm = PrmFile()
        for row in range(self.prmEntryListBox.count()):
            item: PrmEntryItem = self.prmEntryListBox.item(row)
            prm.add_entry(item.entry)

        with path.open("wb") as f:
            f.write(prm.to_bytes())

    @Slot(PrmEntryItem)
    def show_entry(self, item: PrmEntryItem):
        if item is None or item.text() == "":
            self.prmEntryEditor.setEnabled(False)
            return

        self.prmEntryEditor.set_entry(item.entry)
        self.prmEntryEditor.setEnabled(True)

    @Slot()
    def new_entry(self):
        name = self.prmEntryListBox._resolve_name("message")
        item = PrmEntryItem(
            name,
            PrmEntry(name, 0, 4)
        )
        self.prmEntryListBox.blockSignals(True)
        self.prmEntryListBox.addItem(item)
        self.prmEntryListBox.blockSignals(False)
        self.prmEntryListBox.editItem(item, new=True)

    @Slot()
    def remove_selected_entries(self):
        self.prmEntryListBox.takeItem(self.prmEntryListBox.currentRow())

    @Slot()
    def duplicate_selected_entries(self):
        self.prmEntryListBox.duplicate_item(self.prmEntryListBox.currentItem())

    @Slot()
    def update_message_text(self):
        ...

    @Slot(str, int, int)
    def update_entry(self, soundName: str, startFrame: int, endFrame: int):
        ...
