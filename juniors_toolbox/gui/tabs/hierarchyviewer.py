import time
from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from queue import LifoQueue
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.tabs.dataeditor import DataEditorWidget
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.templates import ToolboxTemplates
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.interactivestructs import (
    InteractiveTreeWidget, InteractiveTreeWidgetItem)
from juniors_toolbox.gui.widgets.property import (A_ValueProperty,
                                                  ArrayProperty, ByteProperty,
                                                  PropertyFactory,
                                                  StructProperty)
from juniors_toolbox.objects.object import A_SceneObject, GroupObject, MapObject
from juniors_toolbox.objects.value import (A_Member, MemberEnum, QualifiedName,
                                           ValueType)
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs, jdrama
from PySide6.QtCore import (QObject, QPoint, QRunnable, Qt, QThread, QModelIndex,
                            QThreadPool, QTimer, Signal, Slot)
from PySide6.QtGui import (QAction, QColor, QDragEnterEvent, QDragLeaveEvent, QStandardItemModel, QStandardItem,
                           QDragMoveEvent, QDropEvent, QFont, QKeyEvent,
                           QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QFrame, QCompleter,
                               QGridLayout, QLabel, QLineEdit, QListWidget, QListView,
                               QListWidgetItem, QMenu, QPushButton,
                               QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QWidget)


class StringListProperty(StructProperty):
    def construct(self) -> None:
        super().construct()
        self._frameLayout._content_layout.setSpacing(0)
        self._frameLayout._content_layout.setContentsMargins(10, 0, 0, 0)

    def add_property(self, prop: A_ValueProperty):
        self._frameLayout.addWidget(prop)


class NameRefListWidgetItem(QListWidgetItem):
    def __init__(self, text: str, type: int = 0, subKind: str = "Default"):
        super().__init__(text, type)
        self.subKind = subKind


class NameRefSelectionDialog(QDialog):
    def __init__(self, isGroup: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Map Object...")
        self.setFixedSize(400, 500)
        self._isGroup = isGroup

        self.mainLayout = QGridLayout()
        self.nameRefListWidget = QListView()
        self.nameRefListWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.nameRefListWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.nameRefListWidget.clicked.connect(self.nameref_clicked)
        self.nameRefListWidget.doubleClicked.connect(self.nameref_double_clicked)
        self.mainLayout.addWidget(self.nameRefListWidget, 0, 0, 1, 1)

        self.searchLayout = QGridLayout()
        self.searchBar = QLineEdit()
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.searchBar.setCompleter(self.completer)
        self.searchBar.setPlaceholderText(" *Search here*")
        self.searchBar.textChanged.connect(self.check_nameref_exists)
        self.selectButton = QPushButton("Select")
        self.selectButton.setMinimumSize(60, 30)
        self.selectButton.setEnabled(False)
        self.selectButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.setMinimumSize(60, 30)
        self.cancelButton.clicked.connect(self.reject)
        self.searchLayout.addWidget(self.searchBar, 0, 0, 1, 3)
        self.searchLayout.addWidget(self.selectButton, 1, 1, 1, 1)
        self.searchLayout.addWidget(self.cancelButton, 1, 2, 1, 1)
        self.searchLayout.setColumnStretch(0, 1)
        self.searchLayout.setColumnStretch(1, 0)
        self.searchLayout.setColumnStretch(2, 0)
        self.mainLayout.addLayout(self.searchLayout, 1, 0, 1, 1)

        self.setLayout(self.mainLayout)
        self.populate()

    def populate(self):
        model = QStandardItemModel()
        manager = ToolboxTemplates.get_instance()
        for template in manager.iter_templates():
            keycode = jdrama.get_key_code(template.get_name())
            isGroupCode = keycode in A_SceneObject._KNOWN_GROUP_HASHES
            if self._isGroup and not isGroupCode:
                continue
            elif not self._isGroup and isGroupCode:
                continue
            for name, info in template.iter_wizards():
                item = QStandardItem(f"{template.get_name()} [{name}]")
                model.appendRow(item)
        self.nameRefListWidget.setModel(model)
        self.completer.setModel(model)

    def get_nameref(self) -> jdrama.NameRef:
        text = self.searchBar.text()
        lpos = text.find("[")
        return jdrama.NameRef(text[:lpos].strip())

    def get_subkind(self) -> str:
        text = self.searchBar.text()
        lpos = text.find("[")
        rpos = text.find("]")
        return text[lpos+1:rpos]

    @Slot(QModelIndex)
    def nameref_clicked(self, index: QModelIndex):
        self.searchBar.blockSignals(True)
        self.searchBar.setText(index.data(Qt.DisplayRole))
        self.searchBar.selectAll()
        self.searchBar.blockSignals(False)
        self.selectButton.setEnabled(True)

    @Slot(QModelIndex)
    def nameref_double_clicked(self, index: QModelIndex):
        self.searchBar.blockSignals(True)
        self.searchBar.setText(index.data(Qt.DisplayRole))
        self.searchBar.selectAll()
        self.searchBar.blockSignals(False)
        self.selectButton.setEnabled(True)
        self.accept()

    @Slot(str)
    def check_nameref_exists(self, text: str):
        model = self.nameRefListWidget.model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            if text == index.data(Qt.DisplayRole):
                self.selectButton.setEnabled(True)
                return
        self.selectButton.setEnabled(False)


class NameRefHierarchyTreeWidgetItem(InteractiveTreeWidgetItem):
    def __init__(self, obj: A_SceneObject, item: Union[InteractiveTreeWidgetItem, str], type: int = 0):
        super().__init__(item, type)
        self.object = obj
        flags = self.flags()
        if obj.is_group():
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)
        self.setText(0, obj.get_explicit_name())

    def copy(self, *, deep: bool = False) -> "NameRefHierarchyTreeWidgetItem":
        item: "NameRefHierarchyTreeWidgetItem" = super().copy(deep=deep)
        item.object = self.object.copy(deep=deep)
        return item


class NameRefHierarchyTreeWidget(InteractiveTreeWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setEditTriggers(self.NoEditTriggers)
        self.itemClicked.connect(self.populate_data_view)

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        item: Optional[NameRefHierarchyTreeWidgetItem] = self.itemAt(point)
        if item is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        if item.object.is_group():
            newObjectAction = QAction("New Object", self)
            newObjectAction.triggered.connect(
                lambda clicked=None: self.pick_new_object(item)
            )
            newGroupAction = QAction("New Group", self)
            newGroupAction.triggered.connect(
                lambda clicked=None: self.pick_new_group(item)
            )
        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_items(self.selectedItems())
        )
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_items(self.selectedItems())
        )

        if item.object.is_group():
            menu.addAction(newObjectAction)
            menu.addAction(newGroupAction)
            menu.addSeparator()
        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(deleteAction)

        return menu

    def editItem(self, item: QTreeWidgetItem, column: int = 0, new: bool = False) -> None:
        return

    @Slot(list)
    def duplicate_items(self, items: List[NameRefHierarchyTreeWidgetItem]) -> List[NameRefHierarchyTreeWidgetItem]:
        """
        Returns the new item
        """
        newItems = []
        for item in items:
            newItem = item.copy(deep=True)
            parent = item.parent()
            parent.insertChild(parent.indexOfChild(item) + 1, newItem)
            newItems.append(newItem)
        return newItems

    @Slot(NameRefHierarchyTreeWidgetItem)
    def pick_new_object(self, item: NameRefHierarchyTreeWidgetItem):
        dialog = NameRefSelectionDialog(False, self)
        if dialog.exec() == QDialog.Rejected:
            return

        nameref, subkind = dialog.get_nameref(), dialog.get_subkind()

        obj = MapObject(nameref.get_ref(), subkind)
        newItem = NameRefHierarchyTreeWidgetItem(obj, obj.get_explicit_name())

        item.addChild(newItem)
        item.object.add_to_group(obj)

    @Slot(NameRefHierarchyTreeWidgetItem)
    def pick_new_group(self, item: NameRefHierarchyTreeWidgetItem):
        dialog = NameRefSelectionDialog(True, self)
        if dialog.exec() == QDialog.Rejected:
            return

        nameref, subkind = dialog.get_nameref(), dialog.get_subkind()

        obj = GroupObject(nameref.get_ref(), subkind)
        grouped = obj.create_member(
            index=int(hash(nameref) in {15406, 9858}),
            qualifiedName=QualifiedName("Grouped"),
            value=0,
            type=ValueType.U32,
            strict=True,
        )
        if grouped is not None:
            grouped._readOnly = True
        newItem = NameRefHierarchyTreeWidgetItem(obj, obj.get_explicit_name())

        item.addChild(newItem)
        item.object.add_to_group(obj)

    @Slot(NameRefHierarchyTreeWidgetItem)
    def populate_data_view(self, item: NameRefHierarchyTreeWidgetItem):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        dataEditorTab = TabWidgetManager.get_tab(DataEditorWidget)
        if dataEditorTab is None or item is None:
            return
        if item.parent() is None:
            obj = item.child(0).object
        else:
            obj = item.object
        dataEditorTab.populate(None, serializable=obj)

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
            self.prevgblindex = prev.treeWidget.currentIndex()
            self.prevparent = prev.treeWidget.currentItem().parent()
            self.previndex = self.prevparent.indexOfChild(
                prev.treeWidget.currentItem())

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
                self.target.treeWidget.setCurrentItem(self.droppeditem)
                self.curgblindex = self.target.treeWidget.currentIndex()
                self.curparent = self.target.treeWidget.currentItem().parent()
                self.curindex = self.curparent.indexOfChild(
                    self.target.treeWidget.currentItem())
                self.__initialized = True
            else:
                self.prevparent.removeChild(self.droppeditem)
                self.curparent.insertChild(self.curindex, self.droppeditem)
                self.target.treeWidget.setCurrentIndex(self.curgblindex)

        def undo(self):
            item = self.curparent.child(self.curindex)
            item.setExpanded(self.droppedExpanded)
            self.curparent.removeChild(item)
            self.prevparent.insertChild(self.previndex, item)
            self.target.treeWidget.setCurrentIndex(self.prevgblindex)

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

    OBJECT_NODE_NAME = "Objects (scene.bin)"
    TABLE_NODE_NAME = "Tables (tables.bin)"

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(title, parent)

        self.treeWidget = NameRefHierarchyTreeWidget()

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

        self.__selectedObject: Optional[A_SceneObject] = None

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        def inner_populate(obj: A_SceneObject, parentNode: NameRefHierarchyTreeWidgetItem, column: int):
            for g in obj.iter_grouped_children():
                childNode = NameRefHierarchyTreeWidgetItem(
                    g, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode, column)

        self.treeWidget.clear()
        if scene is None:
            return

        headerFont = QFont()
        headerFont.setBold(True)

        objectsNode = QTreeWidgetItem()
        objectsNode.setText(0, self.OBJECT_NODE_NAME)
        objectsNode.setFont(0, headerFont)
        objectsNode.setFlags(Qt.ItemIsSelectable |
                             Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        for obj in scene.iter_objects():
            node = NameRefHierarchyTreeWidgetItem(obj, obj.get_explicit_name())
            # node.setText(0, obj.get_explicit_name())
            node.setBackground(0, QColor(255, 255, 0, 128))
            objectsNode.addChild(node)
            if obj.is_group():
                inner_populate(obj, node, 0)
        self.treeWidget.addTopLevelItem(objectsNode)

        tablesNode = QTreeWidgetItem()
        tablesNode.setText(0, self.TABLE_NODE_NAME)
        tablesNode.setFont(0, headerFont)
        tablesNode.setFlags(Qt.ItemIsSelectable |
                            Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        for table in scene.iter_tables():
            node = NameRefHierarchyTreeWidgetItem(
                table, table.get_explicit_name())
            tablesNode.addChild(node)
            if table.is_group():
                inner_populate(table, node, 0)
        self.treeWidget.addTopLevelItem(tablesNode)

        # self.expandAll()

    @Slot(NameRefHierarchyTreeWidgetItem)
    def __populate_properties_view(self, item: NameRefHierarchyTreeWidgetItem) -> None:
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
            if item.text(0) == self.OBJECT_NODE_NAME:
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
        self.__selectedObject = sceneObj

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
        # TODO: Somehow speed this up, or simply show a waiting dialog?
        if self.__selectedObject is None:
            raise RuntimeError("Object missing for array resize")
        member = self.__selectedObject.get_member(prop.get_qualified_name())
        if member is None:
            raise RuntimeError("Member missing for array resize")
        rowCount = prop.get_property_count()
        if size < rowCount:
            return
        for i in range(rowCount, size):
            arrayMember = member[i]
            prop.add_property(self.__create_property(arrayMember, {}))

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
                    arrayProp.sizeChanged.connect(self.__set_array_instance)
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
        return prop

    def __add_property(self, prop: A_ValueProperty): ...
