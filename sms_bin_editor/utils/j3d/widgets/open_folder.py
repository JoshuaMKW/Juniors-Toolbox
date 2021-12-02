from PyQt5.QtWidgets import QAction,QFileDialog, QCheckBox, QDialog, QApplication
import sys
from PyQt5.QtCore import Qt

class folder_dia(QFileDialog):
    def __init__(self, subdirs, model):  
        super().__init__()
        self.setOptions(QFileDialog.DontUseNativeDialog)
        self.setAcceptMode(QFileDialog.AcceptOpen)
        self.setFileMode(QFileDialog.Directory)
        self.checkbox = QCheckBox("Include Subdirectories")
        self.checkbox.setChecked(subdirs)
        self.open_bmd = QCheckBox("Load .bmd/.bdl")
        self.open_bmd.setChecked(model)
        self.layout().addWidget(self.checkbox)
        
        self.layout().addWidget(self.open_bmd)
        self.resize(1600, 1200)

    def isChecked(self):
        return self.checkbox.isChecked()
        
    def load_model(self):
        return self.open_bmd.isChecked()