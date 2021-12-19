from os import walk
from typing import Dict, List, Tuple, Union
from PySide2.QtCore import QLine, QObject, QTimer, Qt
from PySide2.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent
from PySide2.QtWidgets import QBoxLayout, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QStyle, QTreeWidget, QTreeWidgetItem, QUndoStack, QVBoxLayout, QWidget
from sms_bin_editor.gui.layouts.entrylayout import EntryLayout

from sms_bin_editor.gui.widgets.colorbutton import ColorButton
from sms_bin_editor.gui.widgets.dynamictab import DynamicTabWidget
from sms_bin_editor.gui.tools import clear_layout, walk_layout
from sms_bin_editor.gui.layouts.framelayout import FrameLayout
from sms_bin_editor.gui.widgets.explicitlineedit import ExplicitLineEdit
from sms_bin_editor.objects.template import ObjectAttribute
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.objects.types import RGBA, Vec3f
from sms_bin_editor.scene import SMSScene


class ObjectHierarchyWidgetItem(QTreeWidgetItem):
    def __init__(self, obj: GameObject, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = obj
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if obj.is_group():
            flags |= Qt.ItemIsDropEnabled
        self.setFlags(flags)


class ObjectHierarchyWidget(QTreeWidget):
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

        self.draggedObject = None

    def populate_objects_from_scene(self, scene: SMSScene):
        def inner_populate(obj: GameObject, parentNode: ObjectHierarchyWidgetItem) -> List[ObjectHierarchyWidgetItem]:
            for g in obj.iter_grouped():
                childNode = ObjectHierarchyWidgetItem(g)
                childNode.setText(0, g.get_explicit_name())
                parentNode.addChild(childNode)
                if g.is_group():
                    inner_populate(g, childNode)

        for obj in scene.iter_objects():
            node = ObjectHierarchyWidgetItem(obj)
            node.setText(0, obj.get_explicit_name())
            self.addTopLevelItem(node)
            if obj.is_group():
                inner_populate(obj, node)

        self.expandAll()

    def dragEnterEvent(self, event: QDragEnterEvent):
        print(event.pos(), event.source())
        draggedObj: ObjectHierarchyWidgetItem = self.itemAt(event.pos())
        self.draggedObject = draggedObj
        self.draggedIndex = draggedObj.parent().indexOfChild(draggedObj)
        print(draggedObj, self.draggedIndex)
        return super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if True:
            super().dropEvent(event)
            return

        if self.indexFromItem(self.draggedObject, 0) != -1:
            swappedObject: ObjectHierarchyWidgetItem = self.itemAt(event.pos())
            destParent = swappedObject.parent()
            srcParent = self.draggedObject.parent()
            swappedIndex = destParent.indexOfChild(swappedObject)
            if swappedIndex == self.draggedObject.parent().indexOfChild(self.draggedObject):
                return
            self.setItemSelected(self.draggedObject, False)
            srcParent.removeChild(self.draggedObject)
            destParent.insertChild(swappedIndex, self.draggedObject)
            self.setItemSelected(self.draggedObject, True)
            event.accept()
            """
            print("item in self")
            swappedObject: ObjectHierarchyWidgetItem = self.itemAt(event.pos())
            destParent = swappedObject.parent()
            swappedIndex = destParent.indexOfChild(swappedObject)
            destParent.removeChild(swappedObject)
            destParent.insertChild(swappedIndex, self.draggedObject)

            srcParent = self.draggedObject.parent()
            swappedIndex = srcParent.indexOfChild(self.draggedObject)
            srcParent.removeChild(self.draggedObject)
            srcParent.insertChild(swappedIndex, swappedObject)
            event.accept()
            """


class ObjectPropertiesWidget(QScrollArea):
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


    def reset(self):
        clear_layout(self.gridLayout)
        self.object = None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    
    def populate_attributes_from_object(self, obj: GameObject):
        self.reset()
        self.object = obj

        row = 0
        indentWidth = 25
        self._structs: Dict[str, QWidget] = {}
        def inner_struct_populate(parent: QGridLayout, attribute: Tuple[str, Union[int, float, str, bytes, list, RGBA]], nestedDepth: int = 0):
            nonlocal row
            scopeNames = attribute[0].split(".")
            parentScopes = scopeNames[:nestedDepth]
            thisScope = scopeNames[nestedDepth]
            childScopes = scopeNames[nestedDepth+1:]
            prefixQual = "" if len(parentScopes) == 0 else ".".join(parentScopes) + "."
            qualname = f"{prefixQual}{thisScope}"
            if len(childScopes) > 0:
                prefix = "" if len(parentScopes) == 0 else ".".join(parentScopes) + "."
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
                
            if isinstance(attribute[1], RGBA):
                layout = QFormLayout()
                label = QLabel(attribute[0].split(".")[-1])
                label.setFixedWidth(100 - (indentWidth * nestedDepth))
                colorbutton = ColorButton("", color=attribute[1])
                colorbutton.setColor(attribute[1])
                colorbutton.setFrameStyle(QFrame.Box)
                colorbutton.setMinimumHeight(20)
                colorbutton.setObjectName(qualname)
                colorbutton.colorChanged.connect(self.updateObjectValue)
                layout.addRow(label, colorbutton)
                parent.addLayout(layout, row, 0, 1, 1)
                row += 1
            elif isinstance(attribute[1], Vec3f):
                layout = QFormLayout()
                widget = QWidget()
                containerLayout = QGridLayout()
                containerLayout.setContentsMargins(0, 0, 0, 0)
                containerLayout.setRowStretch(0, 0)
                containerLayout.setRowStretch(1, 0)
                container = EntryLayout(thisScope, widget, Vec3f, [], labelWidth=100 - (indentWidth * nestedDepth))
                container.setObjectName(qualname)
                for i, component in enumerate(attribute[1]):
                    axis = "XYZ"[i]
                    lineEdit = ExplicitLineEdit(f"{attribute[0]}.{axis}", ExplicitLineEdit.FilterKind.FLOAT)
                    lineEdit.setText(str(component))
                    lineEdit.setCursorPosition(0)
                    entry = EntryLayout(axis, lineEdit, float, [], labelWidth=6, newlining=False)
                    entry.setExpandFactor(0.7)
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
                entry = EntryLayout(thisScope, lineEdit, attribute[1].__class__, [lineEdit], labelWidth=100 - (indentWidth * nestedDepth))
                entry.setObjectName(qualname)
                entry.entryModified.connect(self.updateObjectValue)
                lineEdit.textChangedNamed.connect(entry.updateFromChild)
                layout.addRow(entry)
                parent.addLayout(layout, row, 0, 1, 1)
                row += 1

        for attr in obj.iter_values():
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
        print(value)
        if value.__class__ == RGBA:
            print(value.value)
        self.object.set_value(qualname, value)
        