import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog,  QListWidget, QAction, QSizePolicy, QVBoxLayout)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui

class model_select(QDialog):
    def __init__(self, filepaths):
        super().__init__()  
        
        self.seleced = ""
        self.setup_ui(filepaths)
        self.show()
    def setup_ui(self, filepaths):
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.listbox = QListWidget(self)
        self.listbox.doubleClicked.connect(self.set_selected)
        layout.addWidget(self.listbox)
        
        for filepath in filepaths:
            forward_i = filepath.rfind("/") + 1
            backwad_i = filepath.rfind("\\") + 1
            self.listbox.addItem(filepath[max(forward_i, backwad_i):])
        self.listbox.setCurrentRow(0)
        self.resize(800, 400)

        self.setWindowTitle("select model to load to all")
        
        
    def set_selected(self, item):
        self.selected = self.listbox.currentItem().text()
        self.close()
                
        