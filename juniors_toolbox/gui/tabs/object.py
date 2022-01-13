from os import walk
from pathlib import Path
from threading import Event
from typing import Any, Dict, List, Tuple, Union
from queue import LifoQueue

from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QKeyEvent, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)
from juniors_toolbox.gui.layouts.entrylayout import EntryLayout
from juniors_toolbox.gui.layouts.framelayout import FrameLayout
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.tools import clear_layout, walk_layout
from juniors_toolbox.gui.widgets.colorbutton import ColorButton
from juniors_toolbox.gui.widgets.explicitlineedit import ExplicitLineEdit
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.objects.template import ObjectAttribute
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
                self.curindex = self.curparent.indexOfChild(self.target.currentItem())
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
        self.setHeaderHidden(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setMinimumSize(300, 80)
        #self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        self.undoStack = QUndoStack(self)
        self.undoStack.setUndoLimit(32)

    def populate(self, data: SMSScene, scenePath: Path):
        def inner_populate(obj: GameObject, parentNode: ObjectHierarchyWidgetItem) -> List[ObjectHierarchyWidgetItem]:
            for g in obj.iter_grouped():
                childNode = ObjectHierarchyWidgetItem(g)
                childNode.setText(0, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode)

        for obj in data.iter_objects():
            node = ObjectHierarchyWidgetItem(obj)
            node.setText(0, obj.get_explicit_name())
            self.addTopLevelItem(node)
            if obj.is_group():
                inner_populate(obj, node)

        self.expandAll()

    def dragEnterEvent(self, event: QDragEnterEvent):
        self.draggedItem = self.currentItem()
        super().dragEnterEvent(event)

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
        if not isinstance(data, GameObject):
            return
            
        self.object = data

        row = 0
        indentWidth = 25
        self._structs: Dict[str, QWidget] = {}
        def inner_struct_populate(parent: QGridLayout, attribute: Tuple[str, Union[int, float, str, bytes, RGBA8, RGB8, RGB32, Vec3f]], nestedDepth: int = 0):
            nonlocal row
            scopeNames = attribute[0].split(".")
            parentScopes = scopeNames[:nestedDepth]
            thisScope = scopeNames[nestedDepth]
            childScopes = scopeNames[nestedDepth+1:]
            prefixQual = "" if len(parentScopes) == 0 else ".".join(parentScopes) + "."
            qualname = f"{prefixQual}{thisScope}"

            if len(childScopes) > 0:
                container = self._structs.setdefault(qualname, QWidget())
                firstPass = container.layout() is None
                if firstPass:
                    container.setLayout(QGridLayout())
                layout = container.layout()
                layout.setContentsMargins(0, 0, 0, 10)
                inner_struct_populate(layout, [attribute[0], attribute[1]], nestedDepth+1)
                if firstPass:
                    child = FrameLayout(title=thisScope)
                    child.addWidget(container)
                    child.setObjectName(qualname)
                    child._main_v_layout.setContentsMargins(0, 0, 0, 0)
                    child._main_v_layout.setAlignment(container, Qt.AlignRight)
                    child._content_layout.setContentsMargins(indentWidth, 0, 0, 0)
                    parent.addWidget(child, row, 0, 1, 1)
                    row += 1
                return
                
            if isinstance(attribute[1], RGBA8):
                layout = QFormLayout()
                label = QLabel(attribute[0].split(".")[-1])
                label.setFixedWidth(100 - (indentWidth * nestedDepth))
                colorbutton = ColorButton("", color=attribute[1])
                colorbutton.setColor(attribute[1])
                colorbutton.setFrameStyle(QFrame.Box)
                colorbutton.setMinimumHeight(20)
                colorbutton.setObjectName(qualname)
                colorbutton.colorChanged.connect(self.updateObjectValue)
                container = EntryLayout(
                    thisScope, 
                    colorbutton, 
                    Vec3f, 
                    [],
                    labelWidth=100 - (indentWidth * nestedDepth),
                    minEntryWidth=180 + (indentWidth * nestedDepth)
                )
                layout.addRow(container)
                parent.addLayout(layout, row, 0, 1, 1)
                row += 1
            elif isinstance(attribute[1], Vec3f):
                layout = QFormLayout()
                widget = QWidget()
                containerLayout = QGridLayout()
                containerLayout.setContentsMargins(0, 0, 0, 0)
                containerLayout.setRowStretch(0, 0)
                containerLayout.setRowStretch(1, 0)
                container = EntryLayout(
                    thisScope, 
                    widget, 
                    Vec3f, 
                    [], 
                    labelWidth=100 - (indentWidth * nestedDepth),
                    minEntryWidth=260# + (indentWidth * nestedDepth)
                )
                container.setObjectName(qualname)
                for i, component in enumerate(attribute[1]):
                    axis = "XYZ"[i]
                    lineEdit = ExplicitLineEdit(f"{attribute[0]}.{axis}", ExplicitLineEdit.FilterKind.FLOAT)
                    lineEdit.setMinimumWidth(20)
                    lineEdit.setText(str(component))
                    lineEdit.setCursorPosition(0)
                    entry = EntryLayout(
                        axis, 
                        lineEdit, 
                        float, 
                        [], 
                        labelWidth=6, 
                        newlining=False, 
                        labelFixed=True
                    )
                    entry.entryModified.connect(self.updateObjectValue)
                    lineEdit.textChangedNamed.connect(container.updateFromChild)
                    containerLayout.addLayout(entry, 0, i, 1, 1)
                    containerLayout.setColumnStretch(i, 0)
                    container.addDirectChild(lineEdit)
                container.entryModified.connect(self.updateObjectValue)
                widget.setLayout(containerLayout)
                layout.addRow(container)
                parent.addLayout(layout, row, 0, 1, 1)
                row += 1
            else:
                layout = QFormLayout()
                layout.setObjectName("EntryForm " + attribute[0])
                lineEdit = ExplicitLineEdit(attribute[0], ExplicitLineEdit.FilterKind.type_to_filter(attribute[1].__class__))
                lineEdit.setText(str(attribute[1]))
                lineEdit.setCursorPosition(0)
                entry = EntryLayout(
                    thisScope,
                    lineEdit,
                    attribute[1].__class__,
                    [lineEdit],
                    labelWidth=100 - (indentWidth * nestedDepth),
                    minEntryWidth=180 + (indentWidth * nestedDepth)
                )
                entry.setObjectName(qualname)
                entry.entryModified.connect(self.updateObjectValue)
                lineEdit.textChangedNamed.connect(entry.updateFromChild)
                layout.addRow(entry)
                parent.addLayout(layout, row, 0, 1, 1)
                row += 1

        for attr in data.iter_values():
            inner_struct_populate(self.gridLayout, attr)

        for i in range(row):
            self.gridLayout.setRowStretch(i, 0)
        self.gridLayout.setRowStretch(row+1, 1)

    def checkVerticalIndents(self):
        for item in walk_layout(self.gridLayout):
            layout = item.layout()
            if layout and isinstance(layout, EntryLayout):
                layout.checkNewLine(self.geometry())

    def updateObjectValue(self, qualname: str, value: object):
        self.object.set_value(qualname, value)

    def keyPressEvent(self, event: QKeyEvent):
        if not (event.modifiers() & Qt.CTRL):
            return

        if event.key() == Qt.Key_Y:
            self.undoStack.redo()
        elif event.key() == Qt.Key_Z:
            self.undoStack.undo()
