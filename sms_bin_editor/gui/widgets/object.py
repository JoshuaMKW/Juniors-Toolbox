from typing import List, Tuple, Union
from PySide2.QtCore import QLine, QObject, Qt
from PySide2.QtGui import QColor, QCursor
from PySide2.QtWidgets import QBoxLayout, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from sms_bin_editor.gui.widgets.colorbutton import ColorButton
from sms_bin_editor.gui.widgets.dynamictab import DynamicTabWidget
from sms_bin_editor.gui.tools import clear_layout
from sms_bin_editor.objects.template import ObjectAttribute
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.objects.types import ColorRGBA
from sms_bin_editor.scene import SMSScene


class ObjectHierarchyWidgetItem(QTreeWidgetItem):
    def __init__(self, obj: GameObject, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = obj


class ObjectHierarchyWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setAlternatingRowColors(False)
        self.setRootIsDecorated(True)
        self.setHeaderHidden(True)

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


class ObjectPropertiesWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.centralWidget = QWidget()
        self.setWidgetResizable(True)
        self.setWidget(self.centralWidget)

        self.gridLayout = QGridLayout()
        self.centralWidget.setLayout(self.gridLayout)

    def reset(self):
        clear_layout(self.gridLayout)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    
    def populate_attributes_from_object(self, obj: GameObject):
        self.reset()

        row = -1
        def inner_struct_populate(parent: QGridLayout, attribute: Tuple[str, Union[int, float, str, bytes, list, ColorRGBA]]):
            nonlocal row
            row += 1
            print(attribute)
            if isinstance(attribute[1], ColorRGBA):
                layout = QFormLayout()
                colorbutton = ColorButton("", self, color=attribute[1])
                colorbutton.setColor(attribute[1])
                colorbutton.setFrameStyle(QFrame.Box)
                colorbutton.setMinimumHeight(20)
                layout.addRow(QLabel(attribute[0].split(".")[-1], self), colorbutton)
                parent.setRowStretch(row, 1)
                parent.setColumnStretch(0, 1)
                parent.addLayout(layout, row, 0, 1, 1)
            elif isinstance(attribute[1], list):
                print("sys")
                child = QGroupBox(attribute[0].split(".")[-1], self)
                layout = QGridLayout()
                child.setLayout(layout)
                for membername in attribute[1]:
                    inner_struct_populate(layout, obj.get_value(f"{attribute[0]}.{membername}"))
                parent.addWidget(child, row, 0, 1, 1)
            else:
                layout = QFormLayout()
                lineEdit = QLineEdit()
                lineEdit.setText(str(attribute[1]))
                layout.addRow(QLabel(attribute[0].split(".")[-1], self), lineEdit)
                #layout.setSpacing(20)
                parent.setRowStretch(row, 1)
                parent.setColumnStretch(0, 1)
                parent.addLayout(layout, row, 0, 1, 1)

        for attr in obj.iter_values():
            print(attr)
            inner_struct_populate(self.gridLayout, attr)
            
        verticalSpacer = QSpacerItem(20, 40)
        self.gridLayout.addItem(verticalSpacer, row+1, 0, 1, 1)