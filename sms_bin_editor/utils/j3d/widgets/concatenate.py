import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog, QFileDialog, QSplitter, QAction, QStatusBar, QLineEdit,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QRadioButton)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui

class concatente_editor(QDialog):
    def __init__(self):
        super().__init__()
        self.was_canceled = True
        self.setup_ui()
        self.show()
    def setup_ui(self):
        self.resize(800, 400)
        self.resize_mw=QAction()
        self.setWindowTitle("combine files")
        
        