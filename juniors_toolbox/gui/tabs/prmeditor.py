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
from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.interactivelist import InteractiveListWidget, InteractiveListWidgetItem
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import ObjectAttribute
from juniors_toolbox.utils.jdrama import NameRef
from juniors_toolbox.utils.prm import PrmEntry, PrmFile
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


class PrmEntryListItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["PrmEntryListItem", str], entry: PrmEntry):
        super().__init__(item)
        self.entry = entry

    def clone(self) -> "PrmEntryListItem":
        entry = PrmEntry(
            self.entry.key,
            self.entry.value,
            self.entry.valueLen
        )
        item = PrmEntryListItem(self, entry)
        return item


class PrmEntryListWidget(InteractiveListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
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
    addRequested: SignalInstance = Signal()
    removeRequested: SignalInstance = Signal()
    copyRequested: SignalInstance = Signal()

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
    newRequested: SignalInstance = Signal()
    openRequested: SignalInstance = Signal()
    closeRequested: SignalInstance = Signal()
    saveRequested: SignalInstance = Signal(bool)

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
    entryUpdateRequested: SignalInstance = Signal(str, object)

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

    def set_entry(self, _entry: PrmEntry):
        qualname = _entry.key
        value = _entry.value
        grid = self.gridLayout

        if isinstance(value, RGBA8):
            layout = QFormLayout()
            label = QLabel(qualname)
            label.setFixedWidth(100)
            colorbutton = ColorButton("", color=value)
            colorbutton.setColor(value)
            colorbutton.setFrameStyle(QFrame.Box)
            colorbutton.setMinimumHeight(20)
            colorbutton.setObjectName(qualname)
            colorbutton.colorChanged.connect(self.updateObjectValue)
            container = EntryLayout(
                qualname,
                colorbutton,
                Vec3f,
                [],
                labelWidth=100,
                minEntryWidth=180
            )
            layout.addRow(container)
            grid.addLayout(layout, 0, 0, 1, 1)
        elif isinstance(value, Vec3f):
            layout = QFormLayout()
            widget = QWidget()
            containerLayout = QGridLayout()
            containerLayout.setContentsMargins(0, 0, 0, 0)
            containerLayout.setRowStretch(0, 0)
            containerLayout.setRowStretch(1, 0)
            container = EntryLayout(
                qualname,
                widget,
                Vec3f,
                [],
                labelWidth=100,
                minEntryWidth=260  # + (indentWidth * nestedDepth)
            )
            container.setObjectName(qualname)
            for i, component in enumerate(value):
                axis = "XYZ"[i]
                lineEdit = ExplicitLineEdit(
                    f"{qualname}.{axis}", ExplicitLineEdit.FilterKind.FLOAT)
                lineEdit.setMinimumWidth(20)
                lineEdit.setText(str(component))
                lineEdit.setCursorPosition(0)
                entry = EntryLayout(
                    axis,
                    lineEdit,
                    float,
                    [],
                    labelWidth=14,
                    newlining=False,
                    labelFixed=True
                )
                entry.entryModified.connect(self.updateObjectValue)
                lineEdit.textChangedNamed.connect(
                    container.updateFromChild)
                containerLayout.addLayout(entry, 0, i, 1, 1)
                containerLayout.setColumnStretch(i, 0)
                container.addDirectChild(lineEdit)
            container.entryModified.connect(self.updateObjectValue)
            widget.setLayout(containerLayout)
            layout.addRow(container)
            grid.addLayout(layout, 0, 0, 1, 1)
        else:
            layout = QFormLayout()
            layout.setObjectName("EntryForm " + qualname)
            lineEdit = ExplicitLineEdit(
                qualname, ExplicitLineEdit.FilterKind.type_to_filter(value.__class__))
            lineEdit.setText(str(value))
            lineEdit.setCursorPosition(0)
            entry = EntryLayout(
                qualname,
                lineEdit,
                value.__class__,
                [lineEdit],
                labelWidth=100,
                minEntryWidth=180
            )
            entry.setObjectName(qualname)
            entry.entryModified.connect(self.updateObjectValue)
            lineEdit.textChangedNamed.connect(entry.updateFromChild)
            layout.addRow(entry)
            grid.addLayout(layout, 0, 0, 1, 1)
    

    def checkVerticalIndents(self):
        for item in walk_layout(self.gridLayout):
            layout = item.layout()
            if layout and isinstance(layout, EntryLayout):
                layout.checkNewLine(self.geometry())

    def updateObjectValue(self, qualname: str, value: object):
        self.entryUpdateRequested.emit(qualname, value)


class PrmEditorWidget(QScrollArea, GenericTabWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(685, 300)

        self.mainLayout = QVBoxLayout()
        self.mainLayout.setContentsMargins(10, 0, 10, 10)

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

        self.mainLayout.addWidget(self.menuBar)
        self.mainLayout.addWidget(self.splitter)

        self.setLayout(self.mainLayout)

        self.entries: List[PrmEntry] = []

        self.__cachedOpenPath: Path = None

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, PrmFile):
            return

        self.prmEntryListBox.clear()

        for i, entry in enumerate(data.iter_entries()):
            if entry.key == "":
                raise ValueError("Empty Key is invalid")
            listItem = PrmEntryListItem(entry.key, entry)
            self.prmEntryListBox.addItem(listItem)

        if self.prmEntryListBox.count() > 0:
            self.prmEntryListBox.setCurrentRow(0)
            self.prmEntryListWidget.setEnabled(True)

    @Slot()
    def new_bmg(self):
        self.populate(
            PrmFile(),
            None
        )
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

        self.populate(prm, None)

    @Slot()
    def close_bmg(self):
        self.prmEntryListBox.clear()
        self.prmEntryEditor.setEnabled(False)

    @Slot(Path, bool)
    def save_bmg(self, path: Optional[Path] = None, saveAs: bool = False):
        if (saveAs or self.__cachedOpenPath is None) and path is None:
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

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self.__cachedOpenPath = path
        else:
            path = self.__cachedOpenPath

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