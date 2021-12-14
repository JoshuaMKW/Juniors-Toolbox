from typing import List
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFrame, QListWidget, QTreeWidget, QTreeWidgetItem

from sms_bin_editor.gui.widgets.dynamictab import DynamicTabWidget
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.scene import SMSScene

class RailListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def populate_rails_from_scene(self, scene: SMSScene):
        self.addItems([r.name for r in scene.iter_rails()])