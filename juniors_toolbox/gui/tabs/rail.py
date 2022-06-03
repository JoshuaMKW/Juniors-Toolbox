from email.policy import default
from operator import index
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
from juniors_toolbox.rail import Rail, RailNode, RalData
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot, QPoint, Signal, QModelIndex, QPersistentModelIndex, QItemSelection, QItemSelectionModel, QObject, QMimeData, QDataStream, QAbstractListModel, QSize
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel, QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QGridLayout, QListWidget, QSplitter, QWidget, QListWidgetItem, QFormLayout, QVBoxLayout, QMenu, QListView
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs


from PySide6.QtTest import QAbstractItemModelTester


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


class RailItem(QStandardItem):
    _rail: Rail

    def __init__(self, other: Optional[Rail] | Optional["RailItem"] = None):
        if isinstance(other, RailItem):
            super().__init__(other)
            self._rail = other._rail.copy(deep=True)
            return

        super().__init__()

        self._rail = Rail("((null))")
        if other is None:
            return
        
        self._rail = other

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
        return super().read(in_)

    def write(self, out: QDataStream) -> None:
        return super().write(out)

    def data(self, role: int = Qt.UserRole + 1) -> Any:
        if role == 255:
            return super().data(role)

        kind = "Spline Rail" if self._rail.is_spline() else "Rail"
            
        if role == Qt.DisplayRole:
            return self._rail.name

        elif role == Qt.EditRole:
            return self._rail.name

        elif role == Qt.SizeHintRole:
            return QSize(40, self.font().pointSize() * 2)

        elif role == Qt.ToolTipRole:
            return f"{kind} \"{self._rail.name}\"\n{self._rail.get_node_count()} Nodes"

        elif role == Qt.WhatsThisRole:
            return f"{kind} \"{self._rail.name}\"\n{self._rail.get_node_count()} Nodes"

        elif role == Qt.StatusTipRole:
            return f"{self._rail.get_node_count()} Nodes"

        elif role == Qt.UserRole + 1:
            return self._rail

    def setData(self, value: Any, role: int = Qt.UserRole + 1) -> None:
        rail = self._rail

        if role == Qt.DisplayRole:
            rail.name = value

        elif role == Qt.EditRole:
            rail.name = value

        elif role == Qt.UserRole + 1:
            self._rail = value

    def clone(self) -> "RailItem":
        return RailItem(self)


class RailNodeItem(QStandardItem):
    _node: RailNode

    def __init__(self, other: Optional[RailNode] | Optional["RailNodeItem"] = None):
        if isinstance(other, RailItem):
            super().__init__(other)
            self._node = other._node.copy(deep=True)
            return

        super().__init__()

        self._node = RailNode()
        if other is None:
            return
        
        self._node = other

    def isAutoTristate(self) -> bool:
        return False

    def isCheckable(self) -> bool:
        return False

    def isDragEnabled(self) -> bool:
        return True

    def isDropEnabled(self) -> bool:
        return True

    def isEditable(self) -> bool:
        return False

    def isSelectable(self) -> bool:
        return True

    def isUserTristate(self) -> bool:
        return False

    def read(self, in_: QDataStream) -> None:
        return super().read(in_)

    def write(self, out: QDataStream) -> None:
        return super().write(out)

    def data(self, role: int = Qt.UserRole + 1) -> Any:
        if role == 255:
            return super().data(role)

        connections = []
        for x in range(self._node.connectionCount.get_value()):
            connections.append(self._node.connections[x].get_value())

        rail = self._node.get_rail()

        railName = "Rail"
        if rail:
            railName = f"\"{rail.name}\""
            
        if role == Qt.DisplayRole:
            return f"Node {self.row()} - {connections}"

        elif role == Qt.SizeHintRole:
            return QSize(40, self.font().pointSize() * 2)

        elif role == Qt.ToolTipRole:
            return f"{railName} Node {self.row()}\nConnections: {connections}"

        elif role == Qt.WhatsThisRole:
            return f"{railName} Node {self.row()}\nConnections: {connections}"

        elif role == Qt.StatusTipRole:
            return "Node Connected" if self._node.is_connected() else "Node Disconnected"

        elif role == Qt.UserRole + 1:
            return self._node

    def setData(self, value: Any, role: int = Qt.UserRole + 1) -> None:
        if role == Qt.UserRole + 1:
            self._node = value

    def clone(self) -> "RailNodeItem":
        return RailNodeItem(self)


class RailListModel(QStandardItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    def itemPrototype(self) -> RailItem:
        return RailItem()

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.CopyAction

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.UserRole + 1) -> Any:
        if section == 0:
            return "Rails"
        return None

    def itemData(self, index: Union[QModelIndex, QPersistentModelIndex]) -> dict[int, Any]:
        roles = {}
        for i in range(Qt.UserRole + 2):
            variant = self.data(index, i)
            if variant:
                roles[i] = variant
        return roles

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        if data.sender() == self and action != Qt.MoveAction:
            return False
        return super().canDropMimeData(data, action, row, column, parent)

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        return super().dropMimeData(data, action, row, column, parent)

    def mimeTypes(self) -> list[str]:
        return ["application/x-raildatalist"]

    def mimeData(self, indexes: list[int]) -> QMimeData:
        return super().mimeData(indexes)


class RailNodeListModel(QStandardItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._nodes: list[RailNode] = []

    def itemPrototype(self) -> RailNodeItem:
        return RailNodeItem()

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

    def itemData(self, index: Union[QModelIndex, QPersistentModelIndex]) -> dict[int, Any]:
        roles = {}
        for i in range(Qt.UserRole + 2):
            variant = self.data(index, i)
            if variant:
                roles[i] = variant
        return roles

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        # if data.sender() == self and action != Qt.MoveAction:
        #     return False
        return super().canDropMimeData(data, action, row, column, parent)

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        return super().dropMimeData(data, action, row, column, parent)

    def mimeTypes(self) -> list[str]:
        return ["application/x-railnodedatalist"]

    def mimeData(self, indexes: list[int]) -> QMimeData:
        return super().mimeData(indexes)


class RailNodeListWidget(InteractiveListView):
    nodeCreated = Signal(RailNodeItem)
    nodeUpdated = Signal(RailNodeItem)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModel(RailNodeListModel())
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QListView.DragDrop)

        selectionModel = self.selectionModel()
        selectionModel.currentChanged.connect(
            self._populate_properties_view
        )
        selectionModel.currentChanged.connect(
            self._populate_data_view
        )

    def model(self) -> RailNodeListModel:
        return super().model()

    def setModel(self, model: RailNodeListModel) -> None:
        super().setModel(model)

    def set_rail_node(self, row: int, node: RailNode) -> bool:
        model = self.model()
        model.setItem(row, RailNodeItem(node))
        return True

    def get_rail_node(self, row: int) -> RailNode:
        return self.model().item(row).data()

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

    @Slot(RailNodeItem)
    def rename_item(self, item: RailNodeItem) -> None:
        pass

    @Slot(RailNodeItem)
    def duplicate_indexes(self, indexes: list[RailNodeItem]) -> None:
        super().duplicate_indexes(indexes)

    @Slot(list)
    def delete_indexes(self, indexes: list[InteractiveListWidgetItem]):
        super().delete_indexes(indexes)
        self._update_node_names()

    @Slot(list)
    def connect_to_neighbors(self, indexes: list[QModelIndex]):
        for index in indexes:
            node = self.get_rail_node(index.row())
            node.connect_to_neighbors()
            self.update(index)

    @Slot(list)
    def connect_to_prev(self, indexes: list[QModelIndex]):
        for index in indexes:
            node = self.get_rail_node(index.row())
            node.connect_to_prev()
            self.update(index)

    @Slot(list)
    def connect_to_next(self, indexes: list[QModelIndex]):
        for index in indexes:
            node = self.get_rail_node(index.row())
            node.connect_to_next()
            self.update(index)

    @Slot(list)
    def connect_to_referring(self, indexes: list[QModelIndex]):
        for index in indexes:
            node = self.get_rail_node(index.row())
            node.connect_to_referring()
            self.update(index)

    def _get_node_name(self, index: int, node: RailNode):
        connections = []
        for x in range(node.connectionCount.get_value()):
            connections.append(node.connections[x].get_value())
        name = f"Node {index} - {connections}"
        return name

    def _update_node_names(self):
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

    def _set_position(self, index: QModelIndex, value: list):
        node = self.get_rail_node(index.row())
        node.posX.set_value(value[0])
        node.posY.set_value(value[1])
        node.posZ.set_value(value[2])

    def _update_connection_count(self, index: QModelIndex, count: int):
        self.get_rail_node(index.row()).connectionCount.set_value(count)
        self.model().layoutChanged.emit()
        self._populate_data_view(index, QModelIndex())

    def _update_connection(self, index: QModelIndex, slot: int, connection: int):
        row = index.row()
        node = self.get_rail_node(row)
        node.connections[slot].set_value(connection)
        node._set_period_from(slot, self.get_rail_node(connection))
        self.model().layoutChanged.emit()
        self._populate_data_view(index, QModelIndex())
    
    @Slot(QModelIndex, QModelIndex)
    def _populate_properties_view(self, selected: QModelIndex, previous: QModelIndex) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or not selected.isValid():
            return

        railNode = self.get_rail_node(selected.row())

        position = S16Vector3Property(
            "Position",
            readOnly=False,
            value=[
                railNode.posX.get_value(),
                railNode.posY.get_value(),
                railNode.posZ.get_value()
            ]
        )
        position.valueChanged.connect(lambda _, v: self._set_position(selected, v))

        flags = IntProperty(
            "Flags",
            readOnly=False,
            value=railNode.flags.get_value(),
            hexadecimal=True
        )
        flags.valueChanged.connect(
            lambda _, v: railNode.flags.set_value(v))

        valueList: list[A_ValueProperty] = []
        for i in range(4):
            value = ShortProperty(
                f"Value {i}",
                readOnly=False,
                value=railNode.values[i].get_value(),
                signed=True
            )
            valueList.append(value)
        valueList[0].valueChanged.connect(
            lambda _, v: railNode.values[0].set_value(v))
        valueList[1].valueChanged.connect(
            lambda _, v: railNode.values[1].set_value(v))
        valueList[2].valueChanged.connect(
            lambda _, v: railNode.values[2].set_value(v))
        valueList[3].valueChanged.connect(
            lambda _, v: railNode.values[3].set_value(v))

        connectionCount = IntProperty(
            "Connections",
            readOnly=False,
            value=railNode.connectionCount.get_value(),
            signed=False
        )
        connectionCount.valueChanged.connect(
            lambda _, v: self._update_connection_count(selected, v))

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
                value=railNode.connections[i].get_value(),
                signed=False
            )
            connection.set_minimum_value(0)
            connection.set_maximum_value(self.model().rowCount() - 1)
            connectionsList.append(connection)
            connections.add_property(connection)
        connectionsList[0].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 0, v))
        connectionsList[1].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 1, v))
        connectionsList[2].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 2, v))
        connectionsList[3].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 3, v))
        connectionsList[4].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 4, v))
        connectionsList[5].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 5, v))
        connectionsList[6].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 6, v))
        connectionsList[7].valueChanged.connect(
            lambda _, v: self._update_connection(selected, 7, v))

        connectionCount.set_maximum_value(8)
        connectionCount.set_minimum_value(0)

        propertiesTab.populate(
            None,
            title=f"Node {selected.row()} Properties",
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

    @Slot(QModelIndex, QModelIndex)
    def _populate_data_view(self, selected: QModelIndex, previous: QModelIndex):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        dataEditorTab = TabWidgetManager.get_tab(DataEditorWidget)
        if dataEditorTab is None or not selected.isValid():
            return
        obj = self.get_rail_node(selected.row())
        dataEditorTab.populate(None, serializable=obj)


class RailListView(InteractiveListView):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._model = RailListModel()
        self._modelTester = QAbstractItemModelTester(
            self._model,
            QAbstractItemModelTester.FailureReportingMode.Fatal,
            self
        )
        self.setModel(self._model)
        self.setAcceptDrops(True)
        self.setEditTriggers(QListView.DoubleClicked)
        self.setDragDropMode(QListView.DragDrop)
        selectionModel = self.selectionModel()
        selectionModel.currentChanged.connect(
            self._populate_properties_view
        )
        selectionModel.currentChanged.connect(
            self._populate_data_view
        )
        self.setDefaultDropAction(Qt.MoveAction)

    def model(self) -> RailListModel:
        return super().model()

    def setModel(self, model: RailListModel) -> None:
        super().setModel(model)

    def get_rail(self, row: int) -> Rail:
        model = self.model()
        item = model.item(row)
        return item.data()

    def set_rail(self, row: int, rail: Rail):
        model = self.model()
        model.setItem(row, RailItem(rail))
    
    def _set_rail_spline(self, index: QModelIndex, isSpline: bool):
        rail = self.get_rail(index.row())
        name = rail.name.lstrip("S_")
        if isSpline:
            name = f"S_{name}"
        rail.name = name
    
    @Slot(list)
    def duplicate_indexes(self, indexes: list[QModelIndex | QPersistentModelIndex]) -> list[QModelIndex | QPersistentModelIndex]:
        """
        Returns the new item
        """
        if len(indexes) == 0:
            return []
            
        model = self.model()

        newIndexes: list[QModelIndex | QPersistentModelIndex] = []
        persistentIndexes = [QPersistentModelIndex(index) for index in indexes]

        for index in persistentIndexes:
            mimeData = model.mimeData([index])
            newName = self._resolve_name(index.data(Qt.DisplayRole))

            model.dropMimeData(
                mimeData,
                Qt.CopyAction,
                index.row() + 1,
                0,
                QModelIndex()
            )

            newIndex = model.index(
                index.row() + 1,
                0,
                QModelIndex()
            )
            model.setData(newIndex, newName, Qt.DisplayRole)

            newIndexes.append(newIndex)

        return newIndexes
    
    @Slot(QModelIndex, QModelIndex)
    def _populate_properties_view(self, selected: QModelIndex, previous: QModelIndex) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or not selected.isValid():
            return

        rail = self.get_rail(selected.row())

        nodeCountProperty = CommentProperty(
            "Node Count",
            value=f"  = {rail.get_node_count()}"
        )

        totalSizeProperty = CommentProperty(
            "Total Size",
            value=f"  = 0x{rail.get_size():X}"
        )

        isSplineProperty = BoolProperty(
            "Is Spline",
            readOnly=False,
            value=rail.name.startswith("S_")
        )
        isSplineProperty.valueChanged.connect(
            lambda _, v: self._set_rail_spline(selected, v))

        propertiesTab.populate(
            None,
            title=f"{rail.name} Properties",
            properties=[
                nodeCountProperty,
                totalSizeProperty,
                isSplineProperty
            ]
        )
    
    @Slot(QModelIndex, QModelIndex)
    def _populate_data_view(self, selected: QModelIndex, previous: QModelIndex):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        dataEditorTab = TabWidgetManager.get_tab(DataEditorWidget)
        if dataEditorTab is None or not selected.isValid():
            return
        obj = self.get_rail(selected.row())
        dataEditorTab.populate(None, serializable=obj)

    
    @Slot(Qt.DropActions)
    def startDrag(self, actions: Qt.DropActions):
        super().startDrag(actions)


    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mimedata = event.mimeData()
        if not mimedata.hasFormat(self.model().mimeTypes()[0]):
            event.ignore()
            return

        if event.source() == self:
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return
        elif event.source() is None:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        else:
            event.ignore()
            return

    @Slot(QDragMoveEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        mimedata = event.mimeData()
        if not mimedata.hasFormat(self.model().mimeTypes()[0]):
            event.ignore()
            return

        if event.source() == self:
            event.acceptProposedAction()
            return
        elif event.source() is None:
            event.acceptProposedAction()
            return
        else:
            event.ignore()
            return

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        mimedata = event.mimeData()
        if not mimedata.hasFormat(self.model().mimeTypes()[0]):
            event.ignore()
            return

        super().dropEvent(event)
        # self.clearSelection()

        # self.setCurrentItem(self.item(self._first))
        # for row in range(self._first, self._last + 1):
        #     item = self.item(row)
        #     item.setSelected(True)
        #     self.itemCreated.emit(item, row)
        #     self.nodeCreated.emit(item)


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
        railList.selectionModel().currentChanged.connect(self.__populate_nodelist)
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
        nodeList.model().rowsRemoved.connect(self.remove_deleted_node)
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

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        model = self.railList.model()
        model.removeRows(0, model.rowCount())
        model = self.nodeList.model()
        model.removeRows(0, model.rowCount())

        railSelectionModel = self.railList.selectionModel()
        railModel = self.railList.model()
        if scene is not None:
            for i, rail in enumerate(scene.iter_rails()):
                self.railList.set_rail(i, rail)
            if railModel.rowCount() > 0:
                focusIndex = railModel.index(0, 0)
                railSelectionModel.setCurrentIndex(
                    focusIndex,
                    QItemSelectionModel.ClearAndSelect
                )
                if railSelectionModel.hasSelection():
                    self.__populate_nodelist(
                        railSelectionModel.currentIndex(),
                        QItemSelection()
                    )
                self._railIndex = focusIndex
                self._rail = self.railList.get_rail(focusIndex.row())

        model.layoutChanged.emit()

    def __populate_nodelist(self, selected: QModelIndex, deselected: QModelIndex) -> None:
        if not selected.isValid():
            return

        model = self.nodeList.model()
        selectionModel = self.nodeList.selectionModel()

        self.nodeList.blockSignals(True)
        model = self.nodeList.model()
        model.removeRows(0, model.rowCount())

        rail = self.railList.get_rail(selected.row())
        for i, node in enumerate(rail.iter_nodes()):
            self.nodeList.set_rail_node(i, node)

        self.nodeList.blockSignals(False)

    @Slot()
    def new_rail(self):
        model = self.railList.model()
        row = model.rowCount()

        self.railList.blockSignals(True)
        self.railList.set_rail(
            row,
            Rail(self.railList._resolve_name("rail"))
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
        node = RailNode()
        self.nodeList.create_rail_node(index, node)
        if self._rail:
            self._rail.insert_node(index, node)

    @Slot()
    def remove_selected_node(self):
        self.remove_deleted_node(
            self.nodeList.takeItem(self.nodeList.currentRow())
        )

    @Slot(RailNodeItem)
    def remove_deleted_node(self, item: RailNodeItem):
        pass# self._rail.remove_node(item.node)

    @Slot()
    def copy_selected_node(self):
        self.nodeList.duplicate_items([self.nodeList.currentItem()])
