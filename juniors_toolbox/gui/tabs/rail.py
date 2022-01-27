from pathlib import Path
from typing import Union

from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.widgets.interactivelist import (
    InteractiveListWidget, InteractiveListWidgetItem)
from juniors_toolbox.rail import Rail, RailKeyFrame
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QGridLayout, QListWidget, QSplitter, QWidget, QListWidgetItem


class RailListWidgetItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["RailListWidgetItem", str], rail: Rail):
        super().__init__(item)
        self.rail = rail

    def clone(self) -> "RailListWidgetItem":
        item = RailListWidgetItem(self, self.rail.copy())
        return item


class RailNodeListWidgetItem(QListWidgetItem):
    def __init__(self, item: Union["RailNodeListWidgetItem", str], node: RailKeyFrame):
        super().__init__(item)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsEnabled
        )
        self.node = node

    def clone(self) -> "RailNodeListWidgetItem":
        item = RailNodeListWidgetItem(self, self.node.copy())
        return item


class RailListWidget(InteractiveListWidget):
    @Slot(RailListWidgetItem)
    def rename_item(self, item: RailListWidgetItem):
        name = super().rename_item(item)
        item.rail.name = name

    @Slot(RailListWidgetItem)
    def duplicate_item(self, item: RailListWidgetItem):
        name = super().duplicate_item(item)
        item.rail.name = name


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
        if self.railList.count() > 0:
            self.railList.setCurrentRow(0)
            self.__populate_nodelist(self.railList.currentItem())

    def __populate_nodelist(self, item: RailListWidgetItem):
        if item is None:
            return

        self.nodeList.clear()

        rail = item.rail
        for i, node in enumerate(rail.iter_frames()):
            item = RailNodeListWidgetItem(str(i), node)
            item.setFlags(
                Qt.ItemIsSelectable |
                Qt.ItemIsEnabled
            )
            self.nodeList.addItem(item)
