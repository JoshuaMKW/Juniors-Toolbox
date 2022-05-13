from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
import time
from types import LambdaType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer, Slot, Signal, QThread, QObject, QThreadPool, QRunnable
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent, QColor, QFont
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)
from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.property import A_ValueProperty, ArrayProperty, ByteProperty, PropertyFactory, StructProperty
from juniors_toolbox.objects.object import A_SceneObject, MapObject
from juniors_toolbox.objects.value import A_Member, MemberEnum, QualifiedName, ValueType
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs


class StringListProperty(StructProperty):
    def construct(self) -> None:
        super().construct()
        self._frameLayout._content_layout.setSpacing(0)
        self._frameLayout._content_layout.setContentsMargins(10, 0, 0, 0)

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

    class _PropertyCreator(QRunnable):
        def __init__(self, member: A_Member, parentLayout: QGridLayout, row: int, propertyMap: dict[QualifiedName, A_ValueProperty]) -> None:
            super().__init__()
            self._member = member
            self._propertyMap = propertyMap
            self._parentLayout = parentLayout
            self._row = row

        def run(self) -> None:
            prop = self.__create_property(self._member, self._propertyMap)
            self._parentLayout.addWidget(prop, self._row, 0, 1, 1)

        def __create_property(self, member: A_Member, propertiesMap: dict[QualifiedName, A_ValueProperty]) -> A_ValueProperty:
            enumInfo = {}
            if isinstance(member, MemberEnum):
                enumInfo = member.get_enum_info()

            prop = PropertyFactory.create_property(
                name=member.get_formatted_name(),
                valueType=member.get_type(),
                value=member.get_value(),
                readOnly=member.is_read_only(),
                enumInfo=enumInfo
            )
            prop.valueChanged.connect(lambda _p, _v: member.set_value(_v))
            if member.is_struct():
                for child in member.get_children(includeArrays=False):
                    arrayRef: int | A_Member
                    arrayProp: Optional[ArrayProperty] = None
                    if isinstance(child._arraySize, A_Member):
                        arrayRef = propertiesMap[child._arraySize.get_qualified_name(
                        )]
                        arrayProp = ArrayProperty(
                            name=child.get_formatted_name(),
                            readOnly=False,
                            sizeRef=arrayRef
                        )
                        arrayProp.sizeChanged.connect(
                            lambda prop, size: self.__set_array_instance(child, prop, size))
                        prop.add_property(arrayProp)
                    else:
                        arrayRef = child._arraySize

                    for i in range(child.get_array_size()):
                        _arrayChild = child[i]
                        _childProp = self.__create_property(
                            _arrayChild, propertiesMap)
                        if arrayProp is not None:
                            arrayProp.add_property(_childProp)
                        else:
                            prop.add_property(_childProp)
                        propertiesMap[_childProp.get_qualified_name()
                                      ] = _childProp
            return prop

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

        self.__object: Optional[A_SceneObject] = None

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
            if item.text(0) == "Objects":
                title = "Object Hierarchy Properties"
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Object Count",
                        valueType=ValueType.COMMENT,
                        value=f"=  {scene.get_object_count()}",
                        readOnly=True
                    )
                )
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Object Data Size",
                        valueType=ValueType.COMMENT,
                        value=f"=  0x{sum([obj.get_data_size() for obj in scene.iter_objects()]):X}",
                        readOnly=True
                    )
                )
                uniqueObjList = StringListProperty(
                    name="Unique Objects",
                    readOnly=False
                )
                for uniqueRef in scene.get_unique_object_refs(alphanumeric=True):
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
                        value=f"=  {scene.get_table_count()}",
                        readOnly=True
                    )
                )
                uniqueTableList = StringListProperty(
                    name="Unique Objects",
                    readOnly=False
                )
                metadataProperties.append(
                    PropertyFactory.create_property(
                        name="Table Data Size",
                        valueType=ValueType.COMMENT,
                        value=f"=  0x{sum([obj.get_data_size() for obj in scene.iter_tables()]):X}",
                        readOnly=True
                    )
                )
                for uniqueRef in scene.get_unique_table_refs(alphanumeric=True):
                    uniqueTableList.add_property(
                        PropertyFactory.create_property(
                            name=uniqueRef,
                            valueType=ValueType.COMMENT,
                            value=uniqueRef,
                            readOnly=True
                        )
                    )
                metadataProperties.append(uniqueTableList)
            propertiesTab.populate(
                scene, properties=metadataProperties, title=title)
            return

        sceneObj = item.object
        self.__object = sceneObj

        title = f"{sceneObj.get_explicit_name()} Properties"

        properties: List[A_ValueProperty] = []
        propertiesMap: dict[QualifiedName, A_ValueProperty] = {}
        for member in sceneObj.get_members(includeArrays=False):
            arrayRef: int | A_Member
            arrayProp: Optional[ArrayProperty] = None
            if isinstance(member._arraySize, A_Member):
                arrayRef = propertiesMap[member._arraySize.get_qualified_name(
                )]
                arrayProp = ArrayProperty(
                    name=member.get_formatted_name(),
                    readOnly=False,
                    sizeRef=arrayRef
                )
                arrayProp.sizeChanged.connect(self.__set_array_instance)
                properties.append(arrayProp)
            elif not member.is_defined_array():
                arraySizeProp = ByteProperty(
                    member.get_concrete_name() + "Count",
                    readOnly=False,
                    value=len(member._arrayInstances),
                    signed=False
                )
                properties.append(arraySizeProp)
                arrayProp = ArrayProperty(
                    name=member.get_formatted_name(),
                    readOnly=False,
                    sizeRef=arraySizeProp
                )
                arrayProp.sizeChanged.connect(
                    lambda prop, size: self.__set_array_instance(prop, size))
                properties.append(arrayProp)
            else:
                arrayRef = member._arraySize

            arraySize = member.get_array_size() if member.is_defined_array() else len(
                member._arrayInstances)
            for i in range(arraySize):
                child = member[i]
                childProp = self.__create_property(child, propertiesMap)
                if arrayProp is not None:
                    arrayProp.add_property(childProp)
                else:
                    properties.append(childProp)
                propertiesMap[childProp.get_qualified_name()] = childProp

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

    def __set_array_instance(self, prop: ArrayProperty, size: int):
        otime = time.time()
        if self.__object is None:
            raise RuntimeError("Object missing for array resize")
        member = self.__object.get_member(prop.get_qualified_name())
        if member is None:
            raise RuntimeError("Member missing for array resize")
        rowCount = prop.get_property_count()
        if size < rowCount:
            return
        for i in range(rowCount, size):
            arrayMember = member[i]
            prop.add_property(self.__create_property(arrayMember, {}))
        print(time.time() - otime)

    def __create_property(self, member: A_Member, propertiesMap: dict[QualifiedName, A_ValueProperty]) -> A_ValueProperty:
        enumInfo = {}
        otime = time.time()
        if isinstance(member, MemberEnum):
            enumInfo = member.get_enum_info()

        prop = PropertyFactory.create_property(
            name=member.get_formatted_name(),
            valueType=member.get_type(),
            value=member.get_value(),
            readOnly=member.is_read_only(),
            enumInfo=enumInfo
        )
        prop.valueChanged.connect(lambda _p, _v: member.set_value(_v))
        if member.is_struct():
            for child in member.get_children(includeArrays=False):
                arrayRef: int | A_Member
                arrayProp: Optional[ArrayProperty] = None
                if isinstance(child._arraySize, A_Member):
                    arrayRef = propertiesMap[child._arraySize.get_qualified_name(
                    )]
                    arrayProp = ArrayProperty(
                        name=child.get_formatted_name(),
                        readOnly=False,
                        sizeRef=arrayRef
                    )
                    arrayProp.sizeChanged.connect(
                        lambda prop, size: self.__set_array_instance(prop, size))
                    prop.add_property(arrayProp)
                elif not child.is_defined_array():
                    arraySizeProp = ByteProperty(
                        child.get_concrete_name() + "Count",
                        readOnly=False,
                        signed=False,
                    )
                    prop.add_property(arraySizeProp)
                    arrayProp = ArrayProperty(
                        name=child.get_formatted_name(),
                        readOnly=False,
                        sizeRef=arraySizeProp
                    )
                    arrayProp.sizeChanged.connect(
                        lambda prop, size: self.__set_array_instance(prop, size))
                    prop.add_property(arrayProp)
                else:
                    arrayRef = child._arraySize

                for i in range(child.get_array_size()):
                    _arrayChild = child[i]
                    _childProp = self.__create_property(
                        _arrayChild, propertiesMap)
                    if arrayProp is not None:
                        arrayProp.add_property(_childProp)
                    else:
                        prop.add_property(_childProp)
                    propertiesMap[_childProp.get_qualified_name()] = _childProp
        print(prop.__class__.__name__, time.time() - otime)
        return prop

    def __add_property(self, prop: A_ValueProperty): ...
