from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, List, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)
from pyparsing import line
from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.property import ValuePropertyWidget
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.gui.widgets.spinboxdrag import SpinBoxDragDouble, SpinBoxDragInt
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import AttributeType, ObjectAttribute
from juniors_toolbox.rail import RailKeyFrame
from juniors_toolbox.utils.types import RGB32, RGB8, RGBA8, Vec3f
from juniors_toolbox.scene import SMSScene


class ObjectHierarchyWidgetItem(QTreeWidgetItem):
    def __init__(self, obj: GameObject, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = obj
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if obj.is_group():
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)


class ObjectHierarchyWidget(QTreeWidget, GenericTabWidget):
    class UndoCommand(QUndoCommand):
        def __init__(self, target: "ObjectHierarchyWidget"):
            super().__init__("Cmd")
            self.prevparent = None
            self.prevgblindex = None
            self.previndex = None
            self.dropevent = None
            self.target = target
            self.droppeditem = target.draggedItem
            self.droppedExpanded = self.droppeditem.isExpanded()

            self.__initialized = False

        def set_prev(self, prev: "ObjectHierarchyWidget"):
            self.prevgblindex = prev.currentIndex()
            self.prevparent = prev.currentItem().parent()
            self.previndex = self.prevparent.indexOfChild(prev.currentItem())

        def set_current(self, cur: "ObjectHierarchyWidget", event: QDropEvent):
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

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setAlternatingRowColors(False)
        self.setRootIsDecorated(True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setHeaderHidden(True)
        self.setMinimumSize(300, 80)

        self.undoStack = QUndoStack(self)
        self.undoStack.setUndoLimit(32)

    def populate(self, data: SMSScene, scenePath: Path):
        def inner_populate(obj: GameObject, parentNode: ObjectHierarchyWidgetItem, column: int) -> List[ObjectHierarchyWidgetItem]:
            for g in obj.iter_grouped():
                childNode = ObjectHierarchyWidgetItem(g)
                childNode.setText(column, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode, column)

        self.clear()

        for obj in data.iter_objects():
            node = ObjectHierarchyWidgetItem(obj)
            node.setText(0, obj.get_explicit_name())
            self.addTopLevelItem(node)
            if obj.is_group():
                inner_populate(obj, node, 0)

        for table in data.iter_tables():
            node = ObjectHierarchyWidgetItem(table)
            node.setText(0, table.get_explicit_name())
            self.addTopLevelItem(node)
            if table.is_group():
                inner_populate(table, node, 0)

        # self.expandAll()

    def startDrag(self, supportedActions: Qt.DropActions):
        self.draggedItem = self.currentItem()
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
        command = ObjectHierarchyWidget.UndoCommand(self)
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


class ObjectPropertiesWidget(QScrollArea, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.object = None
        self.centralWidget = QWidget()
        self.setWidgetResizable(True)
        self.setWidget(self.centralWidget)

        self.gridLayout = QGridLayout()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.centralWidget.setLayout(self.gridLayout)

        self.updateTimer = QTimer(self.centralWidget)
        self.updateTimer.timeout.connect(self.checkVerticalIndents)
        self.updateTimer.start(10)

        self.setMinimumSize(300, 80)

    def reset(self):
        clear_layout(self.gridLayout)
        self.object = None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def populate(self, data: Any, scenePath: Path):
        self.reset()

        INDENT_WIDTH = 25
        ROW = 0
        if isinstance(data, GameObject):
            self.object = data

            self._structs: Dict[str, QWidget] = {}

            def inner_struct_populate(
                parent: QGridLayout,
                attribute: GameObject.Value,
                nestedDepth: int = 0,
                readOnly: bool = False
            ):
                nonlocal ROW
                scopeNames = attribute.name.split(".")
                parentScopes = scopeNames[:nestedDepth]
                thisScope = scopeNames[nestedDepth]
                childScopes = scopeNames[nestedDepth+1:]
                prefixQual = "" if len(
                    parentScopes) == 0 else ".".join(parentScopes) + "."
                qualname = f"{prefixQual}{thisScope}"

                if len(childScopes) > 0:
                    container = self._structs.setdefault(qualname, QWidget())
                    firstPass = container.layout() is None
                    if firstPass:
                        container.setLayout(QGridLayout())
                    layout = container.layout()
                    layout.setContentsMargins(0, 0, 0, 10)
                    inner_struct_populate(
                        layout, attribute, nestedDepth+1)
                    if firstPass:
                        child = FrameLayout(title=thisScope)
                        child.addWidget(container)
                        child.setObjectName(qualname)
                        child._main_v_layout.setContentsMargins(0, 0, 0, 0)
                        child._main_v_layout.setAlignment(
                            container, Qt.AlignRight)
                        child._content_layout.setContentsMargins(
                            INDENT_WIDTH, 0, 0, 0)
                        parent.addWidget(child, ROW, 0, 1, 1)
                        ROW += 1
                    return

                if isinstance(attribute.value, RGBA8):
                    layout = QFormLayout()
                    label = QLabel(attribute.name.split(".")[-1])
                    label.setFixedWidth(100 - (INDENT_WIDTH * nestedDepth))
                    colorbutton = ColorButton("", color=attribute.value)
                    colorbutton.setColor(attribute.value)
                    colorbutton.setFrameStyle(QFrame.Box)
                    colorbutton.setMinimumHeight(20)
                    colorbutton.setObjectName(qualname)
                    colorbutton.colorChanged.connect(self.updateObjectValue)
                    container = EntryLayout(
                        thisScope,
                        colorbutton,
                        RGBA8,
                        [],
                        labelWidth=100 - (INDENT_WIDTH * nestedDepth),
                        minEntryWidth=180 + (INDENT_WIDTH * nestedDepth)
                    )
                    layout.addRow(container)
                    parent.addLayout(layout, ROW, 0, 1, 1)
                    ROW += 1
                elif isinstance(attribute.value, Vec3f):
                    layout = QFormLayout()

                    entryWidget = create_vec3f_entry(
                        attribute,
                        nestedDepth,
                        INDENT_WIDTH,
                        readOnly
                    )
                    entryWidget.entryModified.connect(self.updateObjectValue)

                    layout.addRow(entryWidget)
                    parent.addLayout(layout, ROW, 0, 1, 1)
                    ROW += 1
                else:
                    layout = QFormLayout()
                    entryWidget = create_single_entry(
                        attribute,
                        nestedDepth,
                        INDENT_WIDTH,
                        readOnly
                    )
                    entryWidget.entryModified.connect(self.updateObjectValue)
                    layout.addRow(entryWidget)
                    parent.addLayout(layout, ROW, 0, 1, 1)
                    ROW += 1

            for attr in data.iter_values():
                inner_struct_populate(self.gridLayout, attr,
                                      readOnly=data.is_group() and attr.name == "Grouped")

        elif isinstance(data, RailKeyFrame):
            position = GameObject.Value(
                "Position",
                Vec3f(*data.position),
                AttributeType.VECTOR3
            )
            positionEntry = create_vec3f_entry(position)

            movementContainer = QWidget()
            movementGroup = FrameLayout(title="Movement")
            movementGroup.addWidget(movementContainer)
            movementGroup.setObjectName("Movement")
            movementGroup._main_v_layout.setContentsMargins(0, 0, 0, 0)
            movementGroup._main_v_layout.setAlignment(movementContainer, Qt.AlignRight)
            movementGroup._content_layout.setContentsMargins(
                INDENT_WIDTH, 0, 0, 0
            )
            movementLayout = QGridLayout()
            
            self.gridLayout.addLayout(positionEntry, 0, 0, 1, 1)
            self.gridLayout.addLayout(movementLayout, 0, 1, 1, 1)

            ROW = 2

        for i in range(ROW):
            self.gridLayout.setRowStretch(i, 0)
        self.gridLayout.setRowStretch(ROW+1, 1)

    def checkVerticalIndents(self):
        for item in walk_layout(self.gridLayout):
            layout = item.layout()
            if layout and isinstance(layout, EntryLayout):
                layout.checkNewLine(self.geometry())

    def updateObjectValue(self, qualname: str, value: object):
        self.object.set_value(qualname, value)

    def updateRailFrameValue(self, qualname: str, value: object):
        ...


class SelectedPropertiesWidget(QScrollArea, GenericTabWidget):
    @dataclass
    class Property:
        name: str
        value: object
        changedCB: Callable = lambda value: None

    def __init__(self, *args, **kwargs):
        self.__value_setter = lambda: True


    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, list):
            return
        
    def set_value_callback(self, cb: Callable[[tuple, dict], bool]):
        self.__value_setter = cb
