from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QListWidget, QSizePolicy, QTreeWidget, QTreeWidgetItem
from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.scene import SMSScene


class RailListWidget(QListWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 80)
        #self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

    def populate(self, data: SMSScene, scenePath: Path):
        self.addItems([r.name for r in data.iter_rails()])
