from os import walk
from pathlib import Path
from threading import Event
from typing import Any, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer, SignalInstance, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QAction
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QPushButton, QMenuBar, QMenu,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle,
                               QTreeWidget, QTreeWidgetItem, QSplitter, QFileDialog,
                               QVBoxLayout, QWidget)
from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import A_ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.interactivestructs import InteractiveListWidget, InteractiveListWidgetItem
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.jdrama import NameRef
from juniors_toolbox.utils.prm import PrmEntry, PrmFile
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


class PrmEntryListItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["PrmEntryListItem", str], entry: PrmEntry):
        super().__init__(item)
        self.entry = entry

    def copy(self) -> "PrmEntryListItem":
        entry = PrmEntry(
            self.entry.key,
            self.entry.value
        )
        item = PrmEntryListItem(self, entry)
        return item


class PrmEntryListWidget(InteractiveListWidget):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(150, 100)

    @Slot(PrmEntryListItem)
    def rename_item(self, item: PrmEntryListItem):
        name = super().rename_item(item)
        item.entry.key = NameRef(name)

    @Slot(PrmEntryListItem)
    def duplicate_item(self, item: PrmEntryListItem):
        nitem = super().duplicate_item(item)
        nitem.entry.key = NameRef(nitem.text())


class PrmEntryListInterfaceWidget(QWidget):
    addRequested = Signal()
    removeRequested = Signal()
    copyRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setFixedHeight(45)

        addButton = QPushButton("New", self)
        addButton.clicked.connect(self.addRequested.emit)
        self.__addButton = addButton

        removeButton = QPushButton("Remove", self)
        removeButton.clicked.connect(self.removeRequested.emit)
        self.__removeButton = removeButton

        copyButton = QPushButton("Copy", self)
        copyButton.clicked.connect(self.copyRequested.emit)
        self.__copyButton = copyButton

        layout = QHBoxLayout(self)
        layout.addWidget(self.__addButton)
        layout.addWidget(self.__removeButton)
        layout.addWidget(self.__copyButton)

        self.setLayout(layout)


class PrmEditorMenuBar(QMenuBar):
    newRequested = Signal()
    openRequested = Signal()
    closeRequested = Signal()
    saveRequested = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setNativeMenuBar(False)
        self.setFixedHeight(28)

        fileMenu = QMenu(self)
        fileMenu.setTitle("File")

        newAction = QAction(self)
        newAction.setText("New")
        newAction.triggered.connect(lambda toggled: self.newRequested.emit())

        openAction = QAction(self)
        openAction.setText("Open...")
        openAction.triggered.connect(lambda toggled: self.openRequested.emit())

        saveAction = QAction(self)
        saveAction.setText("Save")
        saveAction.triggered.connect(
            lambda toggled: self.saveRequested.emit(False))

        saveAsAction = QAction(self)
        saveAsAction.setText("Save As...")
        saveAsAction.triggered.connect(
            lambda toggled: self.saveRequested.emit(True))

        closeAction = QAction(self)
        closeAction.setText("Close")
        closeAction.triggered.connect(
            lambda toggled: self.closeRequested.emit())

        fileMenu.addAction(newAction)
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(saveAction)
        fileMenu.addAction(saveAsAction)
        fileMenu.addSeparator()
        fileMenu.addAction(closeAction)

        self.addMenu(fileMenu)


class PrmPropertyEditorWidget(QScrollArea):
    entryUpdateRequested = Signal(str, object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        mainWidget = QWidget()
        
        gridLayout = QGridLayout()
        self.gridLayout = gridLayout
        
        mainWidget.setLayout(gridLayout)
        self.mainWidget = mainWidget

        self.setWidget(mainWidget)

    def set_entry(self, _entry: PrmEntry): ...
    

    def checkVerticalIndents(self): ...

    def updateObjectValue(self, qualname: str, value: Any):
        self.entryUpdateRequested.emit(qualname, value)


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
        prmEntryListBox.currentItemChanged.connect(self.show_message)
        self.prmEntryListBox = prmEntryListBox

        prmEntryListInterface = PrmEntryListInterfaceWidget()
        prmEntryListInterface.addRequested.connect(self.new_message)
        prmEntryListInterface.removeRequested.connect(
            self.remove_selected_message)
        prmEntryListInterface.copyRequested.connect(self.copy_selected_message)
        self.prmEntryListInterface = prmEntryListInterface

        prmEntryListLayout = QVBoxLayout()
        prmEntryListLayout.addWidget(prmEntryListInterface)
        prmEntryListLayout.addWidget(prmEntryListBox)
        prmEntryListLayout.setContentsMargins(0, 0, 0, 0)

        prmEntryListWidget = QWidget()
        prmEntryListWidget.setLayout(prmEntryListLayout)
        prmEntryListWidget.setEnabled(False)
        self.prmEntryListWidget = prmEntryListWidget

        prmEntryEditor = PrmPropertyEditorWidget()
        prmEntryEditor.entryUpdateRequested.connect(
            self.update_entry
        )
        self.prmEntryEditor = prmEntryEditor

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(prmEntryListWidget)
        splitter.addWidget(prmEntryEditor)
        self.splitter = splitter

        menuBar = PrmEditorMenuBar(self)
        menuBar.newRequested.connect(self.new_bmg)
        menuBar.openRequested.connect(self.open_bmg)
        menuBar.closeRequested.connect(self.close_bmg)
        menuBar.saveRequested.connect(
            lambda saveAs: self.save_bmg(saveAs=saveAs))
        self.menuBar = menuBar

        self.vBoxLayout.addWidget(self.menuBar)
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
            listItem = PrmEntryListItem(entry.key.get_ref(), entry)
            self.prmEntryListBox.addItem(listItem)

        if self.prmEntryListBox.count() > 0:
            self.prmEntryListBox.setCurrentRow(0)
            self.prmEntryListWidget.setEnabled(True)

    @Slot()
    def new_bmg(self):
        self.populate(PrmFile())
        self.prmEntryListWidget.setEnabled(True)

    @Slot(Path)
    def open_bmg(self, path: Optional[Path] = None):
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
    def close_bmg(self):
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
            item: PrmEntryListItem = self.prmEntryListBox.item(row)
            prm.add_entry(item.entry)

        with path.open("wb") as f:
            f.write(prm.to_bytes())

    @Slot(PrmEntryListItem)
    def show_message(self, item: PrmEntryListItem):
        if item is None or item.text() == "":
            self.prmEntryEditor.setEnabled(False)
            return

        self.prmEntryEditor.set_entry(item.entry)
        self.prmEntryEditor.setEnabled(True)

    @Slot()
    def new_message(self):
        name = self.prmEntryListBox._resolve_name("message")
        item = PrmEntryListItem(
            name,
            PrmEntry(name, 0, 4)
        )
        self.prmEntryListBox.blockSignals(True)
        self.prmEntryListBox.addItem(item)
        self.prmEntryListBox.blockSignals(False)
        self.prmEntryListBox.editItem(item, new=True)

    @Slot()
    def remove_selected_message(self):
        self.prmEntryListBox.takeItem(self.prmEntryListBox.currentRow())

    @Slot()
    def copy_selected_message(self):
        self.prmEntryListBox.duplicate_item(self.prmEntryListBox.currentItem())

    @Slot()
    def update_message_text(self):
        ...

    @Slot(str, int, int)
    def update_entry(self, soundName: str, startFrame: int, endFrame: int):
        ...