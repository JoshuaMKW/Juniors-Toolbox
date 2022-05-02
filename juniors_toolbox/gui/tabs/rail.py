from pathlib import Path
from typing import Optional, Union

from pip import List
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.interactivelist import (
    InteractiveListWidget, InteractiveListWidgetItem)
from juniors_toolbox.objects.object import BaseObject
from juniors_toolbox.rail import Rail, RailKeyFrame, RalData
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QGridLayout, QListWidget, QSplitter, QWidget, QListWidgetItem
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs

from juniors_toolbox.utils.types import Vec3f


class RailNodeListWidgetItem(QListWidgetItem):
    def __init__(self, item: Union["RailNodeListWidgetItem", str], node: RailKeyFrame) -> None:
        super().__init__(item)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsEnabled
        )
        self.node = node

    def clone(self) -> "RailNodeListWidgetItem":
        item = RailNodeListWidgetItem(self, self.node.copy())
        return item


class RailListWidgetItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["RailListWidgetItem", str], rail: Rail) -> None:
        super().__init__(item)
        self.rail = rail

    def clone(self) -> "RailListWidgetItem":
        item = RailListWidgetItem(self, self.rail.copy())
        return item


class RailNodeListWidget(InteractiveListWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListWidget.DragDropMode.InternalMove)
        #self.setDefaultDropAction(Qt.MoveAction)

    @Slot(RailNodeListWidgetItem)
    def rename_item(self, item: RailNodeListWidgetItem) -> None:
        name: str = super().rename_item(item)
        item.node.name = name

    @Slot(RailNodeListWidgetItem)
    def duplicate_items(self, items: List[RailNodeListWidgetItem]) -> None:
        nitem: RailNodeListWidgetItem = super().duplicate_items(items)
        nitem.node.name = nitem.text()


class RailListWidget(InteractiveListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListWidget.DragDropMode.InternalMove)
        #self.setDefaultDropAction(Qt.MoveAction)

    @Slot(RailListWidgetItem)
    def rename_item(self, item: RailListWidgetItem):
        name = super().rename_item(item)
        item.rail.name = name

    @Slot(RailListWidgetItem)
    def duplicate_items(self, items: List[RailListWidgetItem]):
        nitem = super().duplicate_items(items)
        nitem.rail.name = nitem.text()


class RailViewerWidget(A_DockingInterface):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 80)

        mainLayout = QGridLayout()

        railList = RailListWidget()
        railList.setMinimumWidth(100)
        railList.currentItemChanged.connect(self.__populate_nodelist)
        self.railList = railList

        nodeList = RailNodeListWidget()
        nodeList.currentItemChanged.connect(self.__populate_properties_view)
        self.nodeList = nodeList

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(railList)
        splitter.addWidget(nodeList)
        self.splitter = splitter

        mainLayout.addWidget(splitter)

        self.setLayout(mainLayout)

    def populate(self, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        data: RalData = args[0]
        self.railList.blockSignals(True)
        self.nodeList.blockSignals(True)
        self.railList.clear()
        self.nodeList.clear()
        for rail in data.iter_rails():
            item = RailListWidgetItem(rail.name, rail)
            self.railList.addItem(item)
        if self.railList.count() > 0:
            self.railList.setCurrentRow(0)
            self.__populate_nodelist(self.railList.currentItem())
        self.railList.blockSignals(False)
        self.nodeList.blockSignals(False)

    def __populate_nodelist(self, item: RailListWidgetItem):
        if item is None:
            return

        self.nodeList.blockSignals(True)
        self.nodeList.clear()

        rail = item.rail
        for i, node in enumerate(rail.iter_frames()):
            item = RailNodeListWidgetItem(str(i), node)
            item.setFlags(
                Qt.ItemIsSelectable |
                Qt.ItemIsEnabled
            )
            self.nodeList.addItem(item)
        
        self.nodeList.blockSignals(False)
        self.nodeList.setCurrentRow(0)

        # self.nodeList.currentItemChanged.emit()

    def __populate_properties_view(self, item: RailNodeListWidgetItem):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or item is None:
            return
        propertiesTab.setWindowTitle("Fuckin hell")
        propertiesTab.populate(item.node)