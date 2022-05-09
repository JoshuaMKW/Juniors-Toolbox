from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent, QColor, QFont
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)
from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.property import A_ValueProperty, PropertyFactory, StructProperty
from juniors_toolbox.objects.object import A_SceneObject, MapObject
from juniors_toolbox.objects.value import A_Member, ValueType
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs


class StringListProperty(StructProperty):
    def add_property(self, prop: A_ValueProperty):
        self._frameLayout.addWidget(prop)


class NameRefHierarchyWidgetItem(QTreeWidgetItem):
    def __init__(self, obj: A_SceneObject, *args: VariadicArgs, **kwargs: VariadicKwargs):
        super().__init__(*args, **kwargs)
        self.object = obj
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if obj.is_group():
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)


class NameRefHierarchyWidget(A_DockingInterface):
    class UndoCommand(QUndoCommand):
        def __init__(self, target: "NameRefHierarchyWidget"):
            super().__init__("Cmd")
            self.prevparent = None
            self.prevgblindex = None
            self.previndex = None
            self.dropevent = None
            self.target = target
            self.droppeditem = target.draggedItem
            self.droppedExpanded = self.droppeditem.isExpanded()

            self.__initialized = False

        def set_prev(self, prev: "NameRefHierarchyWidget"):
            self.prevgblindex = prev.currentIndex()
            self.prevparent = prev.currentItem().parent()
            self.previndex = self.prevparent.indexOfChild(prev.currentItem())

        def set_current(self, cur: "NameRefHierarchyWidget", event: QDropEvent):
            self.dropevent = QDropEvent(
                event.pos(),
                event.possibleActions(),
                event.mimeData(),
                event.mouseButtons(),
                event.keyboardModifiers(),
                event.type()
            )

        def redo(self):
            if not self.__initialized:
                QTreeWidget.dropEvent(self.target, self.dropevent)
                self.target.setCurrentItem(self.droppeditem)
                self.curgblindex = self.target.currentIndex()
                self.curparent = self.target.currentItem().parent()
                self.curindex = self.curparent.indexOfChild(
                    self.target.currentItem())
                self.__initialized = True
            else:
                self.prevparent.removeChild(self.droppeditem)
                self.curparent.insertChild(self.curindex, self.droppeditem)
                self.target.setCurrentIndex(self.curgblindex)

        def undo(self):
            item = self.curparent.child(self.curindex)
            item.setExpanded(self.droppedExpanded)
            self.curparent.removeChild(item)
            self.prevparent.insertChild(self.previndex, item)
            self.target.setCurrentIndex(self.prevgblindex)

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(title, parent)

        self.treeWidget = QTreeWidget()

        self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget.setAlternatingRowColors(False)
        self.treeWidget.setRootIsDecorated(True)
        self.treeWidget.setAcceptDrops(True)
        self.treeWidget.setDragEnabled(True)
        self.treeWidget.setDragDropMode(QTreeWidget.InternalMove)
        self.treeWidget.setDefaultDropAction(Qt.MoveAction)
        self.treeWidget.setHeaderHidden(True)
        self.treeWidget.setMinimumSize(300, 80)
        self.treeWidget.currentItemChanged.connect(
            self.__populate_properties_view)

        self.setWidget(self.treeWidget)

        self.undoStack = QUndoStack(self)
        self.undoStack.setUndoLimit(32)

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        def inner_populate(obj: A_SceneObject, parentNode: NameRefHierarchyWidgetItem, column: int):
            for g in obj.iter_grouped_children():
                childNode = NameRefHierarchyWidgetItem(g)
                childNode.setText(column, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode, column)

        self.treeWidget.clear()
        if scene is None:
            return

        headerFont = QFont()
        headerFont.setBold(True)

        objectsNode = QTreeWidgetItem()
        objectsNode.setText(0, "Objects")
        objectsNode.setFont(0, headerFont)
        objectsNode.setFlags(Qt.ItemIsSelectable |
                             Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        for obj in scene.iter_objects():
            node = NameRefHierarchyWidgetItem(obj)
            node.setText(0, obj.get_explicit_name())
            node.setBackground(0, QColor(255, 255, 0, 128))
            objectsNode.addChild(node)
            if obj.is_group():
                inner_populate(obj, node, 0)
        self.treeWidget.addTopLevelItem(objectsNode)

        tablesNode = QTreeWidgetItem()
        tablesNode.setText(0, "Tables")
        tablesNode.setFont(0, headerFont)
        tablesNode.setFlags(Qt.ItemIsSelectable |
                            Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        for table in scene.iter_tables():
            node = NameRefHierarchyWidgetItem(table)
            node.setText(0, table.get_explicit_name())
            tablesNode.addChild(node)
            if table.is_group():
                inner_populate(table, node, 0)
        self.treeWidget.addTopLevelItem(tablesNode)

        # self.expandAll()

    @Slot(NameRefHierarchyWidgetItem)
    def __populate_properties_view(self, item: NameRefHierarchyWidgetItem) -> None:
        from juniors_toolbox.gui.tabs import TabWidgetManager
        propertiesTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        if propertiesTab is None or item is None:
            return

        manager = ToolboxManager.get_instance()
        scene = manager.get_scene()
        if scene is None:
            propertiesTab.reset()
            return

        if item.parent() is None:
            metadataProperties = []
            scene.save_objects(Path("sussybaka.bin"))
            if item.text(0) == "Objects":
                title = "Object Hierarchy Properties"
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Object Count",
                        valueType=ValueType.COMMENT,
                        value=str(scene.get_object_count()),
                        readOnly=True
                    )
                )
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Object Data Size",
                        valueType=ValueType.COMMENT,
                        value=f"0x{sum([obj.get_data_size() for obj in scene.iter_objects()]):X}",
                        readOnly=True
                    )
                )
                uniqueObjList = StringListProperty(
                    name="Unique Objects",
                    readOnly=False
                )
                for uniqueRef in scene.get_unique_object_refs():
                    uniqueObjList.add_property(
                        PropertyFactory.create_property(
                            name=uniqueRef,
                            valueType=ValueType.COMMENT,
                            value=uniqueRef,
                            readOnly=True
                        )
                    )
                metadataProperties.append(uniqueObjList)
            else:
                title = "Table Hierarchy Properties"
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Table Count",
                        valueType=ValueType.COMMENT,
                        value=str(scene.get_table_count()),
                        readOnly=True
                    )
                )
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Table Data Size",
                        valueType=ValueType.COMMENT,
                        value=f"0x{sum([obj.get_data_size() for obj in scene.iter_tables()]):X}",
                        readOnly=True
                    )
                )
            propertiesTab.populate(
                scene, properties=metadataProperties, title=title)

        sceneObj = item.object
        title = f"{sceneObj.get_explicit_name()} Properties"

        def _inner_populate(member: A_Member) -> A_ValueProperty:
            prop = PropertyFactory.create_property(
                name=member.get_formatted_name(),
                valueType=member.get_type(),
                value=member.get_value(),
                readOnly=member.is_read_only()
            )
            prop.valueChanged.connect(lambda _p, _v: member.set_value(_v))
            if member.is_struct():
                for child in member.get_children():
                    if child.is_from_array():
                        pass
                    prop.add_property(_inner_populate(child))
            return prop

        properties = []
        for member in sceneObj.get_members():
            properties.append(_inner_populate(member))

        manager = ToolboxManager.get_instance()
        propertiesTab.populate(scene, properties=properties, title=title)

    def startDrag(self, supportedActions: Qt.DropActions):
        self.draggedItem = self.treeWidget.currentItem()
        super().startDrag(supportedActions)

    def dragEnterEvent(self, event: QDragEnterEvent):
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        item = self.itemAt(event.pos())
        if self.draggedItem is None or item is None:
            event.ignore()
            return

        for i in range(self.topLevelItemCount()):
            tItem = self.topLevelItem(i)
            if self.draggedItem == tItem:
                event.ignore()
                return

        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        command = NameRefHierarchyWidget.UndoCommand(self)
        command.set_prev(self)
        command.set_current(self, event)
        self.undoStack.push(command)

    def keyPressEvent(self, event: QKeyEvent):
        if not (event.modifiers() & Qt.CTRL):
            return

        if event.key() == Qt.Key_Y:
            self.undoStack.redo()
        elif event.key() == Qt.Key_Z:
            self.undoStack.undo()
