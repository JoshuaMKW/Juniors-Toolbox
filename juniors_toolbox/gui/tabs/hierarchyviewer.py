from abc import ABC
from dataclasses import dataclass
from multiprocessing.dummy import Value
from os import walk
from pathlib import Path
from threading import Event
from types import LambdaType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack, QDragMoveEvent, QDragLeaveEvent
from PySide6.QtWidgets import (QFormLayout, QFrame, QGridLayout, QComboBox,
                               QLabel, QScrollArea,
                               QTreeWidget, QTreeWidgetItem, QWidget)
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.objects.object import A_SceneObject, BaseObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs


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

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

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

        self.setWidget(self.treeWidget)

        self.undoStack = QUndoStack(self)
        self.undoStack.setUndoLimit(32)

    def populate(self, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        def inner_populate(obj: A_SceneObject, parentNode: NameRefHierarchyWidgetItem, column: int) -> List[NameRefHierarchyWidgetItem]:
            for g in obj.iter_grouped_children():
                childNode = NameRefHierarchyWidgetItem(g)
                childNode.setText(column, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode, column)

        self.clear()

        data: SMSScene = args[0]
        for obj in data.iter_objects():
            node = NameRefHierarchyWidgetItem(obj)
            node.setText(0, obj.get_explicit_name())
            self.treeWidget.addTopLevelItem(node)
            if obj.is_group():
                inner_populate(obj, node, 0)

        for table in data.iter_tables():
            node = NameRefHierarchyWidgetItem(table)
            node.setText(0, table.get_explicit_name())
            self.treeWidget.addTopLevelItem(node)
            if table.is_group():
                inner_populate(table, node, 0)

        # self.expandAll()

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
