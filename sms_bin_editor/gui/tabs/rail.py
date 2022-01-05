from pathlib import Path
from typing import List

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFrame, QListWidget, QTreeWidget, QTreeWidgetItem
from sms_bin_editor.gui.tabs.generic import GenericTabWidget
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.scene import SMSScene


class RailListWidget(QListWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def populate(self, data: SMSScene, scenePath: Path):
        self.addItems([r.name for r in data.iter_rails()])
