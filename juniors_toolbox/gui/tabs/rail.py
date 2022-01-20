from pathlib import Path
from platform import node
from typing import List, Optional, Union

from PySide6.QtCore import Qt, QPoint, Slot, Signal, SignalInstance
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QListWidget, QSizePolicy, QTreeWidget, QTreeWidgetItem, QWidget, QHBoxLayout, QListWidgetItem, QSplitter, QGridLayout, QMenu, QAbstractItemView
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.rail import Rail, RailKeyFrame
from juniors_toolbox.scene import SMSScene


class RailListWidgetItem(QListWidgetItem):
    def __init__(self, item: Union["RailListWidgetItem", str], rail: Rail):
        super().__init__(item)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsEnabled |
            Qt.ItemIsEditable |
            Qt.ItemIsDragEnabled
        )
        self.rail = rail

    def clone(self) -> "RailListWidgetItem":
        item = RailListWidgetItem(self, self.rail.copy())
        return item


class RailNodeListWidgetItem(QListWidgetItem):
    def __init__(self, item: Union["RailListWidgetItem", str], node: RailKeyFrame):
        super().__init__(item)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsEnabled
        )
        self.node = node

    def clone(self) -> "RailNodeListWidgetItem":
        item = RailNodeListWidgetItem(self, self.node.copy())
        return item


class RailListWidget(QListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        #self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.custom_context_menu)
        self.itemChanged.connect(self.rename_rail)
    
    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint):
        # Infos about the node selected.
        index = self.indexAt(point)

        if not index.isValid():
            return

        item: RailListWidgetItem = self.itemAt(point)

        # We build the menu.
        menu = QMenu(self)

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.takeItem(self.row(item))
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item)
        )
        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_rail(item)
        )

        menu.addAction(deleteAction)
        menu.addAction(renameAction)
        menu.addSeparator()
        menu.addAction(duplicateAction)

        menu.exec(self.mapToGlobal(point))
    
    @Slot(RailListWidgetItem)
    def rename_rail(self, item: RailListWidgetItem):

        newName = self.__resolve_rail_name(item.text(), item)

        self.blockSignals(True)
        item.setText(newName)
        item.rail.name = newName
        self.blockSignals(False)

    @Slot(RailListWidgetItem)
    def duplicate_rail(self, item: RailListWidgetItem):
        newName = self.__resolve_rail_name(item.text())

        self.blockSignals(True)
        newItem = item.clone()
        newItem.setText(newName)
        newItem.rail.name = newName
        self.blockSignals(False)

        self.insertItem(self.row(item)+1, newItem)

    def __resolve_rail_name(self, name: str, filterItem: RailListWidgetItem = None) -> str:
        #for i, char in enumerate(name[::-1]):
        #    if not char.isdecimal():
        #        name = name[:len(name)-i]
        #        break
        
        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.count()):
            if renameContext > 100:
                raise FileExistsError(
                    "Path exists beyond 100 unique iterations!")
            item = self.item(i)
            if item == filterItem:
                continue
            if item.text().startswith(ogName):
                possibleNames.append(item.text())

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > 100:
                raise FileExistsError(
                    "Path exists beyond 100 unique iterations!")
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        return name

class RailViewerWidget(QWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 80)
        
        mainLayout = QGridLayout()

        railList = RailListWidget()
        railList.setMinimumWidth(100)
        railList.currentItemChanged.connect(self.__populate_nodelist)
        self.railList = railList
        
        nodeList = QListWidget()
        self.nodeList = nodeList

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(railList)
        splitter.addWidget(nodeList)
        self.splitter = splitter

        mainLayout.addWidget(splitter)

        self.setLayout(mainLayout)

    def populate(self, data: SMSScene, scenePath: Path):
        self.railList.clear()
        self.nodeList.clear()
        for rail in data.iter_rails():
            item = RailListWidgetItem(rail.name, rail)
            self.railList.addItem(item)

    def __populate_nodelist(self, item: RailListWidgetItem):
        self.nodeList.clear()

        rail = item.rail
        for i, node in enumerate(rail.iter_frames()):
            item = RailNodeListWidgetItem(str(i), node)
            item.setFlags(
                Qt.ItemIsSelectable |
                Qt.ItemIsEnabled
            )
            self.nodeList.addItem(item)
        