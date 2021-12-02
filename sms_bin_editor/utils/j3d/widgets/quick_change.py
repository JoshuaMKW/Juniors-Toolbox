import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog, QFileDialog, QSplitter, QAction, QStatusBar, QLineEdit,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QRadioButton)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui

class quick_editor(QDialog):
    def __init__(self):
        super().__init__()
        self.was_canceled = True      
        
        self.setup_ui()
        self.show()
    def setup_ui(self):
        self.resize(800, 400)
        self.resize_mw=QAction()
        self.setWindowTitle("quick editor")
        
        self.horizontal_layout = QHBoxLayout()
        self.centralwidget = self.horizontal_layout
        
        self.setLayout(self.centralwidget)
        
        #operations layout
        self.op_btns = QWidget(self)
        self.op_layout = QVBoxLayout()
        
        self.op_box = QGroupBox("operations")
        
        self.rad_add = QRadioButton("+")
        self.rad_sub = QRadioButton("-")
        self.rad_mul = QRadioButton("*")
        self.rad_div = QRadioButton("/")
        self.rad_avg = QRadioButton("Average")
        
        self.rad_add.clicked.connect(self.requires_value)
        self.rad_sub.clicked.connect(self.requires_value)
        self.rad_mul.clicked.connect(self.requires_value)
        self.rad_div.clicked.connect(self.requires_value)
        self.rad_avg.clicked.connect(self.no_value_req)
        
        self.op_rads = [self.rad_add, self.rad_sub, self.rad_mul, self.rad_div, self.rad_avg]
        
        self.op_layout.addWidget(self.rad_add)
        self.op_layout.addWidget(self.rad_sub)
        self.op_layout.addWidget(self.rad_mul)
        self.op_layout.addWidget(self.rad_div)
        self.op_layout.addWidget(self.rad_avg)
        
        self.op_box.setLayout(self.op_layout)
        
        self.horizontal_layout.addWidget(self.op_box)
        
        #values
        
        self.values_layout = QWidget(self)
        self.value_box = QVBoxLayout(self.values_layout)
        
        self.val_label = QLabel(self.values_layout)
        self.val_label.setText("By: ")
        self.value_box.addWidget(self.val_label)
        
        self.val_input = QLineEdit(self)
        self.value_box.addWidget(self.val_input)
        
        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect( self.done_pressed )
        self.value_box.addWidget(self.done_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect( self.cancel_pressed )
        self.value_box.addWidget(self.cancel_btn)
        
        self.horizontal_layout.addWidget(self.values_layout)
    
    def requires_value(self):
        self.val_input.setDisabled(False)
        
    def no_value_req(self):
        self.val_input.setDisabled(True)
    
    def done_pressed(self):
        self.was_canceled = False 
        self.close()
        
    def cancel_pressed(self):
        self.was_canceled = True
        self.close()

    def get_info(self):
        operation = None
        if not self.was_canceled:
            for i in range( len(self.op_rads) ):
                if self.op_rads[i].isChecked():
                    operation = i
            
            if operation is None:
                return None
            elif operation == 4:
                return (operation, "")
            try:
                check = float(self.val_input.text())
                return (operation, self.val_input.text())
            except:
                return None
                
        