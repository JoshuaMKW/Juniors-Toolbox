from pathlib import Path
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
from juniors_toolbox.gui.widgets.property import A_ValueProperty, ArrayProperty, IntProperty, ShortProperty, Vector3Property
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragInt
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.rail import Rail, RailKeyFrame, RalData
from juniors_toolbox.scene import SMSScene
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QGridLayout, QListWidget, QSplitter, QWidget, QListWidgetItem, QFormLayout, QVBoxLayout
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
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(False)
        self.setDragDropMode(InteractiveListWidget.DragDropMode.InternalMove)
        # self.setDefaultDropAction(Qt.MoveAction)

    @Slot(RailNodeListWidgetItem)
    def rename_item(self, item: RailNodeListWidgetItem) -> None:
        pass

    @Slot(RailNodeListWidgetItem)
    def duplicate_items(self, items: List[RailNodeListWidgetItem]) -> None:
        super().duplicate_items(items)


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
        railList.itemClicked.connect(self.__populate_data_view)
        self.railList = railList

        self.railListLayout.addWidget(self.railInterface)
        self.railListLayout.addWidget(self.railList)
        self.railWidget.setLayout(self.railListLayout)

        nodeList = RailNodeListWidget()
        nodeList.itemClicked.connect(self.__populate_properties_view)
        nodeList.itemClicked.connect(self.__populate_data_view)
        self.nodeList = nodeList

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.railWidget)
        splitter.addWidget(nodeList)
        self.splitter = splitter

        self.setWidget(splitter)

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
        self.railList.blockSignals(False)
        self.nodeList.blockSignals(False)

    def __populate_nodelist(self, item: RailListWidgetItem) -> None:
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

    @Slot(RailNodeListWidgetItem)
    def __populate_properties_view(self, item: RailNodeListWidgetItem) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or item is None:
            return

        self._railNode = item.node
        self._railItem = item

        position = S16Vector3Property(
            "Position",
            False,
            value=[
                self._railNode.posX.get_value(),
                self._railNode.posY.get_value(),
                self._railNode.posZ.get_value()
            ]
        )
        position.valueChanged.connect(lambda _, v: self.__set_position(v))

        flags = IntProperty(
            "Flags",
            False,
            value=self._railNode.flags.get_value(),
            hexadecimal=True
        )
        flags.valueChanged.connect(lambda _, v: self._railNode.flags.set_value(v))

        valueList: list[A_ValueProperty] = []
        for i in range(4):
            value = ShortProperty(
                f"Value {i}",
                False,
                value=self._railNode.values[i].get_value(),
                signed=True
            )
            valueList.append(value)
        valueList[0].valueChanged.connect(lambda _, v: self._railNode.values[0].set_value(v))
        valueList[1].valueChanged.connect(lambda _, v: self._railNode.values[1].set_value(v))
        valueList[2].valueChanged.connect(lambda _, v: self._railNode.values[2].set_value(v))
        valueList[3].valueChanged.connect(lambda _, v: self._railNode.values[3].set_value(v))

        connectionCount = IntProperty(
            "Connections",
            False,
            self._railNode.connectionCount.get_value(),
            signed=False
        )
        connectionCount.valueChanged.connect(lambda _, v: self._railNode.connectionCount.set_value(v))

        connections = ArrayProperty(
            "Connections",
            False,
            sizeRef=connectionCount
        )

        connectionsList: list[A_ValueProperty] = []
        for i in range(8):
            connection = ShortProperty(
                f"Connection {i}",
                False,
                self._railNode.connections[i].get_value(),
                signed=False
            )
            connectionsList.append(connection)
            connections.add_property(connection)
        connectionsList[0].valueChanged.connect(lambda _, v: self.__update_connection(item, 0, v))
        connectionsList[1].valueChanged.connect(lambda _, v: self.__update_connection(item, 1, v))
        connectionsList[2].valueChanged.connect(lambda _, v: self.__update_connection(item, 2, v))
        connectionsList[3].valueChanged.connect(lambda _, v: self.__update_connection(item, 3, v))
        connectionsList[4].valueChanged.connect(lambda _, v: self.__update_connection(item, 4, v))
        connectionsList[5].valueChanged.connect(lambda _, v: self.__update_connection(item, 5, v))
        connectionsList[6].valueChanged.connect(lambda _, v: self.__update_connection(item, 6, v))
        connectionsList[7].valueChanged.connect(lambda _, v: self.__update_connection(item, 7, v))

        connectionCount.set_maximum_value(8)
        connectionCount.set_minimum_value(0)

        propertiesTab.populate(
            None,
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
        self.railList.duplicate_items(self.railList.currentItem())

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

    def __update_connection(self, item: RailNodeListWidgetItem, index: int, connection: int):
        frame = item.node
        frame.connections[index].set_value(connection)
        frame.set_period_from(index, self.nodeList.item(connection).node)
        self.__populate_data_view(item)


    def __set_position(self, value: list):
        self._railNode.posX.set_value(value[0])
        self._railNode.posY.set_value(value[1])
        self._railNode.posZ.set_value(value[2])