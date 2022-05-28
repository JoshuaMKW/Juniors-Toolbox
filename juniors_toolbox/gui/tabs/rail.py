from email.policy import default
from pathlib import Path
from tkinter.font import names
from typing import Optional, Union
from async_timeout import Any

from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.dataeditor import DataEditorWidget
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.interactivestructs import (
    InteractiveListView, InteractiveListWidget, InteractiveListWidgetItem)
from juniors_toolbox.gui.widgets.listinterface import ListInterfaceWidget
from juniors_toolbox.gui.widgets.property import A_ValueProperty, ArrayProperty, BoolProperty, CommentProperty, IntProperty, ShortProperty, Vector3Property
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragInt
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.rail import Rail, RailKeyFrame, RalData
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot, QPoint, Signal, QModelIndex, QPersistentModelIndex, QItemSelection, QItemSelectionModel, QObject, QMimeData, QDataStream, QAbstractListModel
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
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
        self.__xyzInputs: list[SpinBoxDragInt] = [inputX, inputY, inputZ]
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


class RailListModel(QStandardItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._rails: list[Rail] = []

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self._rails)

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return 1

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.CopyAction

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> Qt.ItemFlags:
        return Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.EditRole) -> Any:
        if section == 0:
            return "Nodes"
        return None

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = Qt.EditRole) -> Any:
        if not index.isValid():
            return None

        rail = self._rails[index.row()]
        if role == Qt.DisplayRole:
            return rail.name

        elif role == Qt.EditRole:
            return rail.name

        elif role == Qt.SizeHintRole:
            return Qt.MinimumSize

        elif role == Qt.ToolTipRole:
            return f"Rail \"{rail.name}\""

        elif role == Qt.WhatsThisRole:
            return f"Rail \"{rail.name}\""

        elif role == Qt.StatusTipRole:
            return f"{len(list(rail.iter_frames()))} nodes"

        elif role == Qt.UserRole:
            return rail

        return None

    def setData(self, index: Union[QModelIndex, QPersistentModelIndex], value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False

        oldRail = self._rails[index.row()]
        if role == Qt.DisplayRole:
            oldRail.name = value

        elif role == Qt.EditRole:
            oldRail.name = value

        elif role == Qt.UserRole:
            self._rails[index.row()] = value
            return True

        return False

    def setItemData(self, index: Union[QModelIndex, QPersistentModelIndex], roles: dict[int, Any]) -> bool:
        if not index.isValid():
            return False

        for role, value in roles.items():
            self.setData(index, value, role)

        return True

    def insertRows(self, row: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        self.beginInsertRows(parent, row, row + count)
        for _indexRow in range(row, row + count + 1):
            self._rails.insert(_indexRow+1, Rail("TODO UNIQUE NAME"))
        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row + count)
        successful = True
        for _indexRow in range(row + count, row-1, -1):
            successful &= self.removeRow(_indexRow, parent)
        self.endRemoveRows()
        return successful

    def removeRow(self, row: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        try:
            self._rails.pop(row)
        except IndexError:
            return False
        finally:
            return True

    def insertColumns(self, column: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def removeColumns(self, column: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def removeColumn(self, column: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if data.sender() == self and action != Qt.MoveAction:
            return False
        return super().canDropMimeData(data, action, row, column, parent)

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        return super().dropMimeData(data, action, row, column, parent)

    def mimeTypes(self) -> list[str]:
        mimeTypes = super().mimeTypes()
        mimeTypes.append("application/x-raildatalist")
        return mimeTypes

    def mimeData(self, indexes: list[int]) -> QMimeData:
        data = super().mimeData(indexes)
        data.setData("application/x-raildatalist", b"")
        return data


class RailNodeListModel(QAbstractListModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._nodes: list[RailKeyFrame] = []

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self._nodes)

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return 1

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.CopyAction

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> Qt.ItemFlags:
        return Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.EditRole) -> Any:
        if section == 0:
            return "Nodes"
        return None

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = Qt.EditRole) -> Any:
        if not index.isValid():
            return None

        node = self._nodes[index.row()]
        if role == Qt.DisplayRole:
            connections = []
            for x in range(node.connectionCount.get_value()):
                connections.append(node.connections[x].get_value())
            name = f"Node {index} - {connections}"
            return name

        elif role == Qt.EditRole:
            connections = []
            for x in range(node.connectionCount.get_value()):
                connections.append(node.connections[x].get_value())
            name = f"Node {index} - {connections}"
            return name

        elif role == Qt.SizeHintRole:
            return Qt.MinimumSize

        elif role == Qt.ToolTipRole:
            connections = []
            for x in range(node.connectionCount.get_value()):
                connections.append(node.connections[x].get_value())
            return f"Rail Node {index.row()}\nConnections: [{connections}]"

        elif role == Qt.WhatsThisRole:
            connections = []
            for x in range(node.connectionCount.get_value()):
                connections.append(node.connections[x].get_value())
            return f"Rail Node {index.row()}\nConnections: [{connections}]"

        elif role == Qt.StatusTipRole:
            return "Node Connected" if node.is_connected() else "Node Disconnected"

        elif role == Qt.UserRole:
            return node

        return None

    def setData(self, index: Union[QModelIndex, QPersistentModelIndex], value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False

        oldNode = self._nodes[index.row()]
        if role == Qt.UserRole:
            self._nodes[index.row()] = value
            return True

        return False

    def setItemData(self, index: Union[QModelIndex, QPersistentModelIndex], roles: dict[int, Any]) -> bool:
        if not index.isValid():
            return False

        for role, value in roles.items():
            self.setData(index, value, role)

        return True

    def insertRows(self, row: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        self.beginInsertRows(parent, row, row + count)
        for _indexRow in range(row, row + count + 1):
            self._nodes.insert(_indexRow+1, RailKeyFrame())
        self.endInsertRows()
        return True

    def removeRows(self, row: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row + count)
        successful = True
        for _indexRow in range(row + count, row-1, -1):
            successful &= self.removeRow(_indexRow, parent)
        self.endRemoveRows()
        return successful

    def removeRow(self, row: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        try:
            self._nodes.pop(row)
        except IndexError:
            return False
        finally:
            return True

    def insertColumns(self, column: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def removeColumns(self, column: int, count: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def removeColumn(self, column: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        return True

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if data.sender() == self and action != Qt.MoveAction:
            return False
        return super().canDropMimeData(data, action, row, column, parent)

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        return super().dropMimeData(data, action, row, column, parent)

    def mimeTypes(self) -> list[str]:
        mimeTypes = super().mimeTypes()
        mimeTypes.append("application/x-railnodedatalist")
        return mimeTypes

    def mimeData(self, indexes: list[int]) -> QMimeData:
        data = super().mimeData(indexes)
        data.setData("application/x-railnodedatalist", b"")
        return data

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        index = self.index()
        index: Optional[InteractiveListWidgetItem] = self.indexAt(point)
        if index is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        model = self.model()
        selectedRows = self.selectedIndexes()
        selectedIndexes: list[QModelIndex] = []
        for i in selectedRows:
            selectedIndexes.append(model.index(i, 0))

        start = selectedIndexes[0]

        if len(selectedIndexes) == 1:
            insertBefore = QAction("Insert Node Before...", self)
            insertBefore.triggered.connect(
                lambda clicked=None: self.create_node(start.row())
            )
            insertAfter = QAction("Insert Node After...", self)
            insertAfter.triggered.connect(
                lambda clicked=None: self.create_node(start.row() + 1)
            )
            menu.addAction(insertBefore)
            menu.addAction(insertAfter)
            menu.addSeparator()

        connectToNeighbors = QAction("Connect to Neighbors", self)
        connectToNeighbors.triggered.connect(
            lambda clicked=None: self.connect_to_neighbors(selectedIndexes)
        )
        connectToPrev = QAction("Connect to Prev", self)
        connectToPrev.triggered.connect(
            lambda clicked=None: self.connect_to_prev(selectedIndexes)
        )
        connectToNext = QAction("Connect to Next", self)
        connectToNext.triggered.connect(
            lambda clicked=None: self.connect_to_next(selectedIndexes)
        )
        connectToReferring = QAction("Connect to Referring Nodes", self)
        connectToReferring.triggered.connect(
            lambda clicked=None: self.connect_to_referring(selectedIndexes)
        )

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_indexes(selectedIndexes)
        )

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_indexes(selectedIndexes)
        )

        menu.addAction(connectToNeighbors)
        menu.addAction(connectToPrev)
        menu.addAction(connectToNext)
        menu.addAction(connectToReferring)
        menu.addSeparator()
        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(deleteAction)

        return menu


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


class RailNodeListWidget(InteractiveListView):
    nodeCreated = Signal(RailNodeListWidgetItem)
    nodeUpdated = Signal(RailNodeListWidgetItem)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModel(RailNodeListModel())
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(InteractiveListView.InternalMove)
        self.setSelectionMode(InteractiveListView.SingleSelection)
        self.indexEdited.connect(self.__update_node_names)

    def create_rail_node(self, row: int, rail: RailKeyFrame) -> bool:
        return super().create_row(row, self._get_node_name(row, rail), rail)

    def get_rail_node(self, row: int) -> RailKeyFrame:
        return self.model().index(row, 0).data(Qt.UserRole)

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        index: Optional[InteractiveListWidgetItem] = self.indexAt(point)
        if index is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        model = self.model()
        selectedRows = self.selectedIndexes()
        selectedIndexes: list[QModelIndex] = []
        for i in selectedRows:
            selectedIndexes.append(model.index(i, 0))

        start = selectedIndexes[0]

        if len(selectedIndexes) == 1:
            insertBefore = QAction("Insert Node Before...", self)
            insertBefore.triggered.connect(
                lambda clicked=None: self.create_node(start.row())
            )
            insertAfter = QAction("Insert Node After...", self)
            insertAfter.triggered.connect(
                lambda clicked=None: self.create_node(start.row() + 1)
            )
            menu.addAction(insertBefore)
            menu.addAction(insertAfter)
            menu.addSeparator()

        connectToNeighbors = QAction("Connect to Neighbors", self)
        connectToNeighbors.triggered.connect(
            lambda clicked=None: self.connect_to_neighbors(selectedIndexes)
        )
        connectToPrev = QAction("Connect to Prev", self)
        connectToPrev.triggered.connect(
            lambda clicked=None: self.connect_to_prev(selectedIndexes)
        )
        connectToNext = QAction("Connect to Next", self)
        connectToNext.triggered.connect(
            lambda clicked=None: self.connect_to_next(selectedIndexes)
        )
        connectToReferring = QAction("Connect to Referring Nodes", self)
        connectToReferring.triggered.connect(
            lambda clicked=None: self.connect_to_referring(selectedIndexes)
        )

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_indexes(selectedIndexes)
        )

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_indexes(selectedIndexes)
        )

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
    def duplicate_indexes(self, indexes: list[RailNodeListWidgetItem]) -> None:
        super().duplicate_indexes(indexes)

    @Slot(list)
    def delete_indexes(self, indexes: list[InteractiveListWidgetItem]):
        super().delete_indexes(indexes)
        self.__update_node_names()

    @Slot(list)
    def connect_to_neighbors(self, indexes: list[QModelIndex]):
        model = self.model()

        for index in indexes:
            thisRow = index.row()
            thisNode = self.get_rail_node(thisRow)

            if thisRow == model.rowCount() - 1:
                nextRow = 0
            else:
                nextRow = thisRow + 1

            if thisRow == 0:
                prevRow = model.rowCount() - 1
            else:
                prevRow = thisRow - 1

            nextIndex = model.index(nextRow, 0)
            nextNode = self.get_rail_node(nextRow)

            prevIndex = model.index(prevRow, 0)
            prevNode = self.get_rail_node(prevRow)

            thisNode.connectionCount.set_value(1)

            preConnectionCount = prevNode.connectionCount.get_value()
            if preConnectionCount < 1:
                prevNode.connectionCount.set_value(1)
                preConnectionCount = 1

            if nextNode.connectionCount.get_value() < 1:
                nextNode.connectionCount.set_value(1)

            prevNode.connections[preConnectionCount - 1].set_value(thisRow)
            prevNode.set_period_from(preConnectionCount - 1, thisNode)
            thisNode.connections[0].set_value(prevRow)
            thisNode.set_period_from(0, prevNode)
            thisNode.connections[1].set_value(nextNode)
            thisNode.set_period_from(1, nextNode)
            nextNode.connections[0].set_value(thisRow)
            nextNode.set_period_from(0, thisNode)

            model.setData(index, self._get_node_name(
                thisRow, thisNode), Qt.DisplayRole)
            model.setData(prevIndex, self._get_node_name(
                thisRow, prevNode), Qt.DisplayRole)
            model.setData(nextIndex, self._get_node_name(
                thisRow, nextNode), Qt.DisplayRole)

            self.nodeUpdated.emit(index)

    @Slot(list)
    def connect_to_prev(self, indexes: list[QModelIndex]):
        model = self.model()

        for index in indexes:
            thisRow = index.row()
            thisNode = self.get_rail_node(thisRow)

            if thisRow == 0:
                prevRow = model.rowCount() - 1
            else:
                prevRow = thisRow - 1

            prevIndex = model.index(prevRow, 0)
            prevNode = self.get_rail_node(prevRow)

            thisNode.connectionCount.set_value(1)
            preConnectionCount = prevNode.connectionCount.get_value()
            if preConnectionCount < 1:
                prevNode.connectionCount.set_value(1)
                preConnectionCount = 1

            prevNode.connections[preConnectionCount - 1].set_value(thisRow)
            prevNode.set_period_from(preConnectionCount - 1, thisNode)
            thisNode.connections[0].set_value(prevRow)
            thisNode.set_period_from(0, prevNode)

            model.setData(index, self._get_node_name(
                thisRow, thisNode), Qt.DisplayRole)
            model.setData(prevIndex, self._get_node_name(
                thisRow, prevNode), Qt.DisplayRole)

            self.nodeUpdated.emit(index)

    @Slot(list)
    def connect_to_next(self, indexes: list[QModelIndex]):
        model = self.model()

        for index in indexes:
            thisRow = index.row()
            thisNode = self.get_rail_node(thisRow)

            if thisRow == model.rowCount() - 1:
                nextRow = 0
            else:
                nextRow = thisRow + 1

            nextIndex = model.index(nextRow, 0)
            nextNode = self.get_rail_node(nextRow)

            thisNode.connectionCount.set_value(1)
            if nextNode.connectionCount.get_value() < 1:
                nextNode.connectionCount.set_value(1)

            thisNode.connections[0].set_value(nextRow)
            thisNode.set_period_from(0, nextNode)
            nextNode.connections[0].set_value(thisRow)
            nextNode.set_period_from(0, thisNode)

            model.setData(index, self._get_node_name(
                thisRow, thisNode), Qt.DisplayRole)
            model.setData(nextIndex, self._get_node_name(
                thisRow, nextNode), Qt.DisplayRole)

            self.nodeUpdated.emit(index)

    @Slot(list)
    def connect_to_referring(self, indexes: list[QModelIndex]):
        model = self.model()

        for index in indexes:
            thisRow = index.row()
            thisNode = self.get_rail_node(thisRow)

            existingConnections = []
            for i in range(thisNode.connectionCount.get_value()):
                existingConnections.append(thisNode.connections[i].get_value())

            connectionIndex = thisNode.connectionCount.get_value()
            for row in range(model.rowCount()):
                if connectionIndex > 7:
                    break

                if row == thisRow or row in existingConnections:
                    continue

                otherIndex = model.index(row, 0)
                otherNode = self.get_rail_node(otherIndex.row())
                for i in range(otherNode.connectionCount.get_value()):
                    connection = otherNode.connections[i].get_value()
                    if connection == thisRow:
                        thisNode.connections[connectionIndex].set_value(row)
                        thisNode.set_period_from(connectionIndex, otherNode)
                        thisNode.connectionCount.set_value(connectionIndex + 1)
                        connectionIndex += 1

            model.setData(index, self._get_node_name(
                index, thisNode), Qt.DisplayRole)

            self.nodeUpdated.emit(index)

    def _get_node_name(self, index: int, node: RailKeyFrame):
        connections = []
        for x in range(node.connectionCount.get_value()):
            connections.append(node.connections[x].get_value())
        name = f"Node {index} - {connections}"
        return name

    def __update_node_names(self):
        model = self.model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            model.setData(
                index,
                self._get_node_name(
                    index,
                    self.get_rail_node(row)
                ),
                Qt.DisplayRole
            )


class RailListView(InteractiveListView):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListView.DragDropMode.InternalMove)
        # self.setDefaultDropAction(Qt.MoveAction)

    def create_rail(self, row: int, rail: Rail) -> bool:
        return super().create_row(row, rail.name, rail)

    def get_rail(self, row: int) -> Rail:
        return self.model().index(row, 0).data(Qt.UserRole)

    @Slot(QModelIndex)
    def rename_index(self, index: QModelIndex) -> None:
        name = super().rename_index(index)
        rail: Rail = index.data(Qt.UserRole)
        rail.name = name

    @Slot(QModelIndex)
    def duplicate_indexes(self, indexes: list[QModelIndex]) -> None:
        nindexes: list[QModelIndex] = super().duplicate_indexes(indexes)
        for nindex in nindexes:
            rail: Rail = nindex.data(Qt.UserRole)
            rail.name = nindex.data(Qt.DisplayRole)


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

        railList = RailListView()
        railList.setMinimumWidth(100)
        railList.currentSelectionChanged.connect(self.__populate_nodelist)
        railList.currentSelectionChanged.connect(
            self.__populate_rail_properties_view)
        railList.currentSelectionChanged.connect(self.__populate_data_view)
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
        nodeList.currentSelectionChanged.connect(
            self.__populate_node_properties_view)
        nodeList.currentSelectionChanged.connect(self.__populate_data_view)
        nodeList.indexDeleted.connect(self.remove_deleted_node)
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

        railSelectionModel = self.railList.selectionModel()
        railModel = self.railList.model()
        if scene is not None:
            for i, rail in enumerate(scene.iter_rails()):
                self.railList.create_rail(i, rail)
            if railModel.rowCount() > 0:
                railSelectionModel.setCurrentIndex(
                    railModel.index(0, 0),
                    QItemSelectionModel.ClearAndSelect
                )
                index = railSelectionModel.currentIndex()
                if railSelectionModel.hasSelection():
                    self.__populate_nodelist(
                        railSelectionModel.selection(),
                        QItemSelection()
                    )
                self._railIndex = index
                self._rail = self.railList.get_rail(index.row())

        self.railList.blockSignals(False)
        self.nodeList.blockSignals(False)

    def __populate_nodelist(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        model = self.nodeList.model()
        selectionModel = self.nodeList.selectionModel()

        self.nodeList.blockSignals(True)
        self.nodeList.clear()

        indexes = selected.indexes()

        index = model.index(indexes[0], 0)
        rail = self.railList.get_rail(index.row())
        for i, node in enumerate(rail.iter_frames()):
            self.nodeList.create_rail_node(i, node)

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
        valuelist[0].valueChanged.connect(
            lambda _, v: self._railNode.values[0].set_value(v))
        valuelist[1].valueChanged.connect(
            lambda _, v: self._railNode.values[1].set_value(v))
        valuelist[2].valueChanged.connect(
            lambda _, v: self._railNode.values[2].set_value(v))
        valuelist[3].valueChanged.connect(
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
        connectionslist[0].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 0, v))
        connectionslist[1].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 1, v))
        connectionslist[2].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 2, v))
        connectionslist[3].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 3, v))
        connectionslist[4].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 4, v))
        connectionslist[5].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 5, v))
        connectionslist[6].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 6, v))
        connectionslist[7].valueChanged.connect(
            lambda _, v: self.__update_connection(item, 7, v))

        connectionCount.set_maximum_value(8)
        connectionCount.set_minimum_value(0)

        propertiesTab.populate(
            None,
            title=f"Node {self.nodeList.indexFromItem(item).row()} Properties",
            properties=[
                position,
                flags,
                valuelist[0],
                valuelist[1],
                valuelist[2],
                valuelist[3],
                connectionCount,
                connections
            ]
        )

    @Slot()
    def new_rail(self):
        model = self.railList.model()
        row = model.rowCount()

        self.railList.blockSignals(True)
        self.railList.create_rail(
            row,
            self.railList._resolve_name("rail")
        )
        self.railList.blockSignals(False)

        self.railList.edit(model.index(row, 0))

    @Slot()
    def remove_selected_rail(self):
        model = self.railList.model()
        selectionModel = self.railList.selectionModel()
        model.removeRow(selectionModel.currentIndex().row())

    @Slot()
    def copy_selected_rail(self):
        model = self.railList.model()
        selectionModel = self.railList.selectionModel()

        indexes: list[QModelIndex] = []
        for row in selectionModel.selectedIndexes():
            indexes.append(model.index(row, 0))

        self.railList.duplicate_indexes(indexes)

    @Slot()
    def new_node(self, index: int):
        node = RailKeyFrame()
        self.nodeList.create_rail_node(index, node)
        if self._rail:
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
