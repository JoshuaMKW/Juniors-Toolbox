from pathlib import Path
from tkinter.font import names
from typing import Optional, Union
from async_timeout import Any

from pip import List
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.dataeditor import DataEditorWidget
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.interactivestructs import (
    InteractiveListWidget, InteractiveListWidgetItem)
from juniors_toolbox.gui.widgets.listinterface import ListInterfaceWidget
from juniors_toolbox.gui.widgets.property import A_ValueProperty, ArrayProperty, BoolProperty, CommentProperty, IntProperty, ShortProperty, Vector3Property
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragInt
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.rail import Rail, RailKeyFrame, RalData
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot, QPoint, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QGridLayout, QListWidget, QSplitter, QWidget, QListWidgetItem, QFormLayout, QVBoxLayout, QMenu
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs


class S16Vector3Property(A_ValueProperty):
    def __init__(self, name: str, readOnly: bool, value: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(name, readOnly, value, parent)
        self._resetValue = [0, 0, 0]

    def construct(self):
        propertyName = self.get_name()

        containerLayout = QGridLayout()
        containerLayout.setContentsMargins(0, 2, 0, 2)
        containerLayout.setRowStretch(0, 0)
        containerLayout.setRowStretch(1, 0)

        inputX = SpinBoxDragInt()
        inputY = SpinBoxDragInt()
        inputZ = SpinBoxDragInt()
        self.__xyzInputs: List[SpinBoxDragInt] = [inputX, inputY, inputZ]
        for i in range(3):
            axis = "XYZ"[i]
            spinBox = self.__xyzInputs[i]
            spinBox.setObjectName(f"{propertyName}.{axis}")
            spinBox.setMinimumWidth(80)
            spinBox.setValue(self._value[i] if self._value is not None else 0)
            entry = QFormLayout()
            entry.addRow(axis, spinBox)
            entry.setRowWrapPolicy(QFormLayout.WrapLongRows)
            entry.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            containerLayout.addLayout(entry, 0, i, 1, 1)
            containerLayout.setColumnStretch(i, 0)
        inputX.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 0))
        inputY.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 1))
        inputZ.valueChangedExplicit.connect(
            lambda _, value: self.__update_axis(value, 2))

        containerLayout.setEnabled(not self.is_read_only())

        self.setLayout(containerLayout)
        self.set_minimum_value(-32768)
        self.set_maximum_value(32767)

    @Slot(QWidget, object)
    def set_inputs(self):
        self.blockSignals(True)
        for i, _input in enumerate(self.__xyzInputs):
            _input.setValue(self.get_value()[i])
        self.blockSignals(False)

    def set_minimum_value(self, value: Any) -> None:
        for input in self.__xyzInputs:
            input.setMinimum(value)

    def set_maximum_value(self, value: Any) -> None:
        for input in self.__xyzInputs:
            input.setMaximum(value)

    def get_value(self) -> list:
        return super().get_value()

    def set_value(self, value: list):
        if not isinstance(value, list):
            raise ValueError("Value is not a list type")
        super().set_value(value)

    def _update_input_depth(self) -> None:
        for inputBox in self.__xyzInputs:
            inputBox.setMinimumWidth(
                max(80 - (self.IndentionWidth * self.get_nested_depth()), 0))

    def __update_axis(self, value: int, axis: int = 0):
        self.get_value()[axis] = value
        self.valueChanged.emit(self, self.get_value())


class RailNodeListWidgetItem(QListWidgetItem):
    def __init__(self, item: Union["RailNodeListWidgetItem", str], node: RailKeyFrame) -> None:
        super().__init__(item)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsDragEnabled |
            Qt.ItemIsEnabled
        )
        self.node = node

    def copy(self) -> "RailNodeListWidgetItem":
        item = RailNodeListWidgetItem(self, self.node.copy())
        return item


class RailListWidgetItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["RailListWidgetItem", str], rail: Rail) -> None:
        super().__init__(item)
        self.rail = rail

    def copy(self, *, deep: bool = False) -> "RailListWidgetItem":
        item = RailListWidgetItem(self, self.rail.copy(deep=deep))
        return item


class RailNodeListWidget(InteractiveListWidget):
    nodeCreated = Signal(RailNodeListWidgetItem)
    nodeUpdated = Signal(RailNodeListWidgetItem)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListWidget.DragDropMode.InternalMove)
        self.model().rowsMoved.connect(self._update_node_names)
        self.itemCreated.connect(self._update_node_names)

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        item: Optional[RailNodeListWidgetItem] = self.itemAt(point)
        if item is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        insertBefore = QAction("Insert Node Before...", self)
        insertBefore.triggered.connect(
            lambda clicked=None: self.create_node(self.row(item))
        )
        insertAfter = QAction("Insert Node After...", self)
        insertAfter.triggered.connect(
            lambda clicked=None: self.create_node(self.row(item) + 1)
        )

        connectToNeighbors = QAction("Connect to Neighbors", self)
        connectToNeighbors.triggered.connect(
            lambda clicked=None: self.connect_to_neighbors(self.selectedItems())
        )
        connectToPrev = QAction("Connect to Prev", self)
        connectToPrev.triggered.connect(
            lambda clicked=None: self.connect_to_prev(self.selectedItems())
        )
        connectToNext = QAction("Connect to Next", self)
        connectToNext.triggered.connect(
            lambda clicked=None: self.connect_to_next(self.selectedItems())
        )
        connectToReferring = QAction("Connect to Referring Nodes", self)
        connectToReferring.triggered.connect(
            lambda clicked=None: self.connect_to_referring(self.selectedItems())
        )

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_items(self.selectedItems())
        )

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_items(self.selectedItems())
        )

        menu.addAction(insertBefore)
        menu.addAction(insertAfter)
        menu.addSeparator()
        menu.addAction(connectToNeighbors)
        menu.addAction(connectToPrev)
        menu.addAction(connectToNext)
        menu.addAction(connectToReferring)
        menu.addSeparator()
        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(deleteAction)

        return menu

    @Slot(RailNodeListWidgetItem)
    def rename_item(self, item: RailNodeListWidgetItem) -> None:
        pass

    @Slot(RailNodeListWidgetItem)
    def duplicate_items(self, items: list[RailNodeListWidgetItem]) -> None:
        super().duplicate_items(items)

    @Slot(list)
    def delete_items(self, items: list[InteractiveListWidgetItem]):
        for item in items:
            row = self.row(item)
            self.itemDeleted.emit(item, row)
            self.takeItem(row)
        
        for row in range(self.count()):
            _item: RailNodeListWidgetItem = self.item(row)
            _item.setText(self._get_node_name(row, _item.node))

    @Slot(int)
    def create_node(self, index: int) -> None:
        node = RailKeyFrame()

        item = RailNodeListWidgetItem("", node)
        oldItem = self.currentItem()

        self.blockSignals(True)
        self.insertItem(index, item)
        for row in range(self.count()):
            _item: RailNodeListWidgetItem = self.item(row)
            _item.setSelected(False)
            _item.setText(self._get_node_name(row, _item.node))
        self.blockSignals(False)

        item.setSelected(True)

        self.nodeCreated.emit(item)
        self.currentItemChanged.emit(item, oldItem)

    @Slot(list)
    def connect_to_neighbors(self, items: list[RailNodeListWidgetItem]):
        if len(items) == 0:
            return

        for item in items:
            thisIndex = self.row(item)
            thisNode = item.node

            if thisIndex == 0:
                prevIndex = self.count() - 1
            else:
                prevIndex = thisIndex - 1

            if thisIndex == self.count() - 1:
                nextIndex = 0
            else:
                nextIndex = thisIndex + 1

            prevItem: RailNodeListWidgetItem = self.item(prevIndex)
            nextItem: RailNodeListWidgetItem = self.item(nextIndex)

            prevNode = prevItem.node
            nextNode = nextItem.node

            thisNode.connectionCount.set_value(2)

            preConnectionCount = prevNode.connectionCount.get_value()
            if preConnectionCount < 1:
                prevNode.connectionCount.set_value(1)
                preConnectionCount = 1

            if nextNode.connectionCount.get_value() < 1:
                nextNode.connectionCount.set_value(1)

            prevNode.connections[preConnectionCount - 1].set_value(thisIndex)
            prevNode.set_period_from(preConnectionCount - 1, thisNode)
            thisNode.connections[0].set_value(prevIndex)
            thisNode.set_period_from(0, prevNode)
            thisNode.connections[1].set_value(nextIndex)
            thisNode.set_period_from(1, nextNode)
            nextNode.connections[0].set_value(thisIndex)
            nextNode.set_period_from(0, thisNode)

            prevItem.setText(self._get_node_name(prevIndex, prevNode))
            item.setText(self._get_node_name(thisIndex, thisNode))
            nextItem.setText(self._get_node_name(nextIndex, nextNode))

        self.nodeUpdated.emit(items[0])

    @Slot(list)
    def connect_to_prev(self, items: list[RailNodeListWidgetItem]):
        if len(items) == 0:
            return
            
        for item in items:
            thisIndex = self.row(item)
            thisNode = item.node

            if thisIndex == 0:
                prevIndex = self.count() - 1
            else:
                prevIndex = thisIndex - 1

            prevItem: RailNodeListWidgetItem = self.item(prevIndex)
            prevNode = prevItem.node

            thisNode.connectionCount.set_value(1)
            preConnectionCount = prevNode.connectionCount.get_value()
            if preConnectionCount < 1:
                prevNode.connectionCount.set_value(1)
                preConnectionCount = 1

            prevNode.connections[preConnectionCount - 1].set_value(thisIndex)
            prevNode.set_period_from(preConnectionCount - 1, thisNode)
            thisNode.connections[0].set_value(prevIndex)
            thisNode.set_period_from(0, prevNode)

            prevItem.setText(self._get_node_name(prevIndex, prevNode))
            item.setText(self._get_node_name(thisIndex, thisNode))

        self.nodeUpdated.emit(items[0])

    @Slot(list)
    def connect_to_next(self, items: list[RailNodeListWidgetItem]):
        if len(items) == 0:
            return
            
        for item in items:
            thisIndex = self.row(item)
            thisNode = item.node

            if thisIndex == self.count() - 1:
                nextIndex = 0
            else:
                nextIndex = thisIndex + 1

            nextItem: RailNodeListWidgetItem = self.item(nextIndex)
            nextNode = nextItem.node

            thisNode.connectionCount.set_value(1)
            if nextNode.connectionCount.get_value() < 1:
                nextNode.connectionCount.set_value(1)

            thisNode.connections[0].set_value(nextIndex)
            thisNode.set_period_from(0, nextNode)
            nextNode.connections[0].set_value(thisIndex)
            nextNode.set_period_from(0, thisNode)

            item.setText(self._get_node_name(thisIndex, thisNode))
            nextItem.setText(self._get_node_name(nextIndex, nextNode))

        self.nodeUpdated.emit(items[0])

    @Slot(list)
    def connect_to_referring(self, items: list[RailNodeListWidgetItem]):
        if len(items) == 0:
            return
            
        for item in items:
            thisIndex = self.row(item)
            thisNode = item.node

            existingConnections = []
            for i in range(thisNode.connectionCount.get_value()):
                existingConnections.append(thisNode.connections[i].get_value())

            connectionIndex = thisNode.connectionCount.get_value()
            for row in range(self.count()):
                if connectionIndex > 7:
                    break

                if row == thisIndex or row in existingConnections:
                    continue

                otherItem: RailNodeListWidgetItem = self.item(row)
                otherNode = otherItem.node
                for i in range(otherNode.connectionCount.get_value()):
                    connection = otherNode.connections[i].get_value()
                    if connection == thisIndex:
                        thisNode.connections[connectionIndex].set_value(row)
                        thisNode.set_period_from(connectionIndex, otherNode)
                        thisNode.connectionCount.set_value(connectionIndex + 1)
                        connectionIndex += 1

            item.setText(self._get_node_name(thisIndex, thisNode))

        self.nodeUpdated.emit(items[0])

    def _get_node_name(self, index: int, node: RailKeyFrame):
        connections = []
        for x in range(node.connectionCount.get_value()):
            connections.append(node.connections[x].get_value())
        name = f"Node {index} - {connections}"
        return name

    @Slot()
    def _update_node_names(self):
        for i in range(self.count()):
            item: RailNodeListWidgetItem = self.item(i)
            name = self._get_node_name(i, item.node)
            item.setText(name)


class RailListWidget(InteractiveListWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListWidget.DragDropMode.InternalMove)
        # self.setDefaultDropAction(Qt.MoveAction)

    @Slot(RailListWidgetItem)
    def rename_item(self, item: RailListWidgetItem) -> None:
        name = super().rename_item(item)
        item.rail.name = name

    @Slot(RailListWidgetItem)
    def duplicate_items(self, items: List[RailListWidgetItem]) -> None:
        nitem = super().duplicate_items(items)
        nitem.rail.name = nitem.text()


class RailViewerWidget(A_DockingInterface):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.setMinimumSize(200, 80)

        self.railWidget = QWidget()
        self.railListLayout = QVBoxLayout()

        railInterface = ListInterfaceWidget()
        railInterface.addRequested.connect(self.new_rail)
        railInterface.removeRequested.connect(
            self.remove_selected_rail)
        railInterface.copyRequested.connect(self.copy_selected_rail)
        self.railInterface = railInterface

        railList = RailListWidget()
        railList.setMinimumWidth(100)
        railList.currentItemChanged.connect(self.__populate_nodelist)
        railList.currentItemChanged.connect(
            self.__populate_rail_properties_view)
        railList.currentItemChanged.connect(self.__populate_data_view)
        self.railList = railList

        self.railListLayout.addWidget(self.railInterface)
        self.railListLayout.addWidget(self.railList)
        self.railWidget.setLayout(self.railListLayout)

        self.nodeWidget = QWidget()
        self.nodeListLayout = QVBoxLayout()

        nodeInterface = ListInterfaceWidget()
        nodeInterface.addRequested.connect(self.new_node)
        nodeInterface.removeRequested.connect(
            self.remove_selected_node)
        nodeInterface.copyRequested.connect(self.copy_selected_node)
        self.nodeInterface = nodeInterface

        nodeList = RailNodeListWidget()
        nodeList.currentItemChanged.connect(
            self.__populate_node_properties_view)
        nodeList.currentItemChanged.connect(self.__populate_data_view)
        nodeList.itemDeleted.connect(self.remove_deleted_node)
        nodeList.nodeUpdated.connect(self.__populate_node_properties_view)
        nodeList.nodeUpdated.connect(self.__populate_data_view)
        self.nodeList = nodeList

        self.nodeListLayout.addWidget(self.nodeInterface)
        self.nodeListLayout.addWidget(self.nodeList)
        self.nodeWidget.setLayout(self.nodeListLayout)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.railWidget)
        splitter.addWidget(self.nodeWidget)
        self.splitter = splitter

        self.setWidget(splitter)

        self._rail: Optional[Rail] = None
        self._railItem: Optional[RailListWidgetItem] = None
        self._railNode: Optional[RailKeyFrame] = None
        self._railNodeItem: Optional[RailNodeListWidgetItem] = None

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        self.railList.blockSignals(True)
        self.nodeList.blockSignals(True)
        self.railList.clear()
        self.nodeList.clear()
        if scene is not None:
            for rail in scene.iter_rails():
                item = RailListWidgetItem(rail.name, rail)
                self.railList.addItem(item)
            if self.railList.count() > 0:
                self.railList.setCurrentRow(0)
                citem = self.railList.currentItem()
                if citem is not None:
                    self.__populate_nodelist(citem)
                self._railItem = self.railList.currentItem()
                self._rail = self._railItem.rail
        self.railList.blockSignals(False)
        self.nodeList.blockSignals(False)

    def __populate_nodelist(self, item: RailListWidgetItem) -> None:
        self.nodeList.blockSignals(True)
        self.nodeList.clear()

        rail = item.rail
        for i, node in enumerate(rail.iter_frames()):
            item = RailNodeListWidgetItem(self.nodeList._get_node_name(i, node), node)
            self.nodeList.addItem(item)

        self.nodeList.blockSignals(False)

    @Slot(RailListWidgetItem)
    def __populate_rail_properties_view(self, item: RailListWidgetItem) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or item is None:
            return

        self._rail = item.rail
        self._railItem = item

        nodeCountProperty = CommentProperty(
            "Node Count",
            value=f"  = {len(self._rail._frames)}"
        )

        totalSizeProperty = CommentProperty(
            "Total Size",
            value=f"  = 0x{self._rail.get_size():X}"
        )

        isSplineProperty = BoolProperty(
            "Is Spline",
            readOnly=False,
            value=self._rail.name.startswith("S_")
        )
        isSplineProperty.valueChanged.connect(
            lambda _, v: self.__set_rail_spline(v))

        propertiesTab.populate(
            None,
            title=f"{self._rail.name} Properties",
            properties=[
                nodeCountProperty,
                totalSizeProperty,
                isSplineProperty
            ]
        )

    @Slot(RailNodeListWidgetItem)
    def __populate_node_properties_view(self, item: RailNodeListWidgetItem) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or item is None:
            return

        self._railNode = item.node
        self._railNodeItem = item

        position = S16Vector3Property(
            "Position",
            readOnly=False,
            value=[
                self._railNode.posX.get_value(),
                self._railNode.posY.get_value(),
                self._railNode.posZ.get_value()
            ]
        )
        position.valueChanged.connect(lambda _, v: self.__set_position(v))

        flags = IntProperty(
            "Flags",
            readOnly=False,
            value=self._railNode.flags.get_value(),
            hexadecimal=True
        )
        flags.valueChanged.connect(
            lambda _, v: self._railNode.flags.set_value(v))

        valueList: list[A_ValueProperty] = []
        for i in range(4):
            value = ShortProperty(
                f"Value {i}",
                readOnly=False,
                value=self._railNode.values[i].get_value(),
                signed=True
            )
            valueList.append(value)
        valueList[0].valueChanged.connect(
            lambda _, v: self._railNode.values[0].set_value(v))
        valueList[1].valueChanged.connect(
            lambda _, v: self._railNode.values[1].set_value(v))
        valueList[2].valueChanged.connect(
            lambda _, v: self._railNode.values[2].set_value(v))
        valueList[3].valueChanged.connect(
            lambda _, v: self._railNode.values[3].set_value(v))

        connectionCount = IntProperty(
            "Connections",
            readOnly=False,
            value=self._railNode.connectionCount.get_value(),
            signed=False
        )
        connectionCount.valueChanged.connect(
            lambda _, v: self.__update_connection_count(item, v))

        connections = ArrayProperty(
            "Connections",
            readOnly=False,
            sizeRef=connectionCount
        )

        connectionsList: list[A_ValueProperty] = []
        for i in range(8):
            connection = ShortProperty(
                f"Connection {i}",
                readOnly=False,
                value=self._railNode.connections[i].get_value(),
                signed=False
            )
            connection.set_minimum_value(0)
            connection.set_maximum_value(self.nodeList.count() - 1)
            connectionsList.append(connection)
            connections.add_property(connection)
        connectionsList[0].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 0, v))
        connectionsList[1].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 1, v))
        connectionsList[2].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 2, v))
        connectionsList[3].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 3, v))
        connectionsList[4].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 4, v))
        connectionsList[5].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 5, v))
        connectionsList[6].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 6, v))
        connectionsList[7].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 7, v))

        connectionCount.set_maximum_value(8)
        connectionCount.set_minimum_value(0)

        propertiesTab.populate(
            None,
            title=f"Node {self.nodeList.indexFromItem(item).row()} Properties",
            properties=[
                position,
                flags,
                valueList[0],
                valueList[1],
                valueList[2],
                valueList[3],
                connectionCount,
                connections
            ]
        )

    @Slot()
    def new_rail(self):
        name = self.railList._resolve_name("rail")
        item = RailListWidgetItem(
            name,
            Rail(name)
        )
        self.railList.blockSignals(True)
        self.railList.addItem(item)
        self.railList.blockSignals(False)
        self.railList.editItem(item, new=True)

    @Slot()
    def remove_selected_rail(self):
        self.railList.takeItem(self.railList.currentRow())

    @Slot()
    def copy_selected_rail(self):
        self.railList.duplicate_items([self.railList.currentItem()])

    @Slot()
    def new_node(self, index: int):
        self.nodeList.create_node(index)
        node = self.nodeList.item(index)
        self._rail.insert_frame(index, node)

    @Slot()
    def remove_selected_node(self):
        self.remove_deleted_node(
            self.nodeList.takeItem(self.nodeList.currentRow())
        )

    @Slot(RailNodeListWidgetItem)
    def remove_deleted_node(self, item: RailNodeListWidgetItem):
        self._rail.remove_frame(item.node)

    @Slot()
    def copy_selected_node(self):
        self.nodeList.duplicate_items([self.nodeList.currentItem()])

    @Slot(InteractiveListWidgetItem)
    def __populate_data_view(self, item: RailNodeListWidgetItem | RailListWidgetItem):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        dataEditorTab = TabWidgetManager.get_tab(DataEditorWidget)
        if dataEditorTab is None or item is None:
            return
        obj: A_Serializable
        if isinstance(item, RailNodeListWidgetItem):
            obj = item.node
        else:
            obj = item.rail
        dataEditorTab.populate(None, serializable=obj)

    def __update_connection_count(self, item: RailNodeListWidgetItem, count: int):
        self._railNode.connectionCount.set_value(count)
        item.setText(self.nodeList._get_node_name(
            self.nodeList.indexFromItem(item).row(), item.node))
        self.__populate_data_view(item)

    def __update_connection(self, item: RailNodeListWidgetItem, index: int, connection: int):
        frame = item.node
        frame.connections[index].set_value(connection)
        frame.set_period_from(index, self.nodeList.item(connection).node)
        item.setText(self.nodeList._get_node_name(
            self.nodeList.indexFromItem(item).row(), item.node))
        self.__populate_data_view(item)

    def __set_position(self, value: list):
        self._railNode.posX.set_value(value[0])
        self._railNode.posY.set_value(value[1])
        self._railNode.posZ.set_value(value[2])

    def __set_rail_spline(self,  isSpline: bool):
        name = self._rail.name.lstrip("S_")
        if isSpline:
            name = f"S_{name}"
        self._rail.name = name
        self._railItem.setText(name)
