import os
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog, QFrame,
                             QScrollArea, QGridLayout, QAction, QApplication, QLineEdit,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout, QRadioButton)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui
from widgets.theme_handler import *

class frames_window(QDialog, themed_window):
    def __init__(self, theme):
        super().__init__()
        self.setup_ui(theme )
        self.set_theme(theme)
        

    def setup_ui(self, theme):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.setWindowTitle("edit all open animations")
        
        self.main_widget = frames_widget(self, theme)
        self.horizontalLayout = QVBoxLayout()
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        
        
        self.setLayout(self.horizontalLayout)
        self.horizontalLayout.addWidget(self.main_widget)
        
        
        self.close_button = QPushButton(self)
        self.close_button.setText("Finish")
        self.close_button.clicked.connect(self.close_window)
        
        self.horizontalLayout.addWidget(self.close_button)
            
    def close_window(self):
        self.close()
        
    def get_info(self):
        return self.main_widget.get_info()
class frames_box(QWidget):
    def __init__(self, parent, one_time):
        super().__init__()
        self.setup_ui(parent.theme)
        
        self.parent = parent
        self.one_time = one_time

    def setup_ui(self, theme):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.main_widget = frames_widget(self, theme)
        
        self.horizontalLayout = QVBoxLayout()
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.horizontalLayout)
          
        self.box_title = QLabel(self)
        self.box_title.setText("Add Frames")

        self.horizontalLayout.addWidget(self.box_title)

        
        self.horizontalLayout.addWidget(self.main_widget)

        self.close_button = QPushButton(self)
        self.close_button.setText("Finish")
        self.close_button.clicked.connect(self.close_window)
        
        self.horizontalLayout.addWidget(self.close_button)       

    def close_window(self):
        self.parent.frames_from_bar( self.get_info(), self.one_time )
    def get_info(self):

        values =  self.main_widget.get_info()
        return values

class frames_widget(QWidget, themed_window):
    def __init__(self, parent, theme = "default"):
        super().__init__()

        #stuff that we want to return / have access to
        self.selected = None
        self.filepath = None
        
        self.setup_ui()
        
        self.set_theme(theme)
    def setup_ui(self):
       
        self.horizontalLayout = QVBoxLayout()
        self.centralwidget = self.horizontalLayout
        #self.setCentralWidget(self.horizontalLayout)
        
        self.setLayout(self.centralwidget)
        
        #chooser
        
        self.mode_layout = QWidget(self)
        self.mode_grid = QGridLayout(self.mode_layout)
        self.specific_enter = QRadioButton("Enter Specific Frames")
        self.specific_enter.toggled.connect(self.change_mode)
        self.formula_enter = QRadioButton("Create by Formula")
        self.formula_enter.toggled.connect(self.change_mode)
        

        
        self.mode_grid.addWidget(self.specific_enter, 0, 0)
        self.mode_grid.addWidget(self.formula_enter, 0, 1)
        
        
        
        #manually enter frames
        self.specific_layout = QWidget(self)
        self.specific_box = QVBoxLayout(self.specific_layout)
        
        self.specific_label = QLabel(self.specific_layout)
        self.specific_label.setText("Manually enter frames to add (seperated by commas):")
        
        self.specific_input = QLineEdit(self.specific_layout)
        
        self.specific_box.addWidget(self.specific_label)
        self.specific_box.addWidget(self.specific_input)
        
        #add frames via formula_
        
        self.formula_layout = QWidget(self)
        self.formula_grid = QGridLayout(self.formula_layout)
        
        self.atevery_label = QLabel(self.formula_layout)
        self.atevery_label.setText("Add a frame at every")
        self.atevery_text = QLineEdit(self.formula_layout) 
        self.frames_label = QLabel(self.formula_layout)
        self.frames_label.setText("frame(s),")
        
        self.startingat_label = QLabel(self.formula_layout)
        self.startingat_label.setText("starting at frame")
        self.startingat_text = QLineEdit(self.formula_layout) 
        
        self.endingat_label = QLabel(self.formula_layout)
        self.endingat_label.setText("and ending at frame")
        self.endingat_text = QLineEdit(self.formula_layout)     
        self.inclusive_label = QLabel(self.formula_layout)
        self.inclusive_label.setText("inclusive.")
        
        self.formula_grid.addWidget(self.atevery_label, 0, 0)
        self.formula_grid.addWidget(self.atevery_text, 0, 1)
        self.formula_grid.addWidget(self.frames_label, 0, 2)
        self.formula_grid.addWidget(self.startingat_label, 1, 0)
        self.formula_grid.addWidget(self.startingat_text, 1, 1)
        self.formula_grid.addWidget(self.endingat_label, 2, 0)
        self.formula_grid.addWidget(self.endingat_text, 2, 1)
        self.formula_grid.addWidget(self.inclusive_label, 2, 2)
        
        
        self.formula_layout.setDisabled(True)
        
        self.horizontalLayout.addWidget(self.mode_layout)
        self.horizontalLayout.addWidget(self.specific_layout)
        self.horizontalLayout.addWidget(self.formula_layout)
        #self.horizontalLayout.addWidget(self.close_button)
        
        self.specific_enter.setChecked(True)
    
    def change_mode(self):
        if self.specific_enter.isChecked():
            self.specific_layout.setDisabled(False)
            self.formula_layout.setDisabled(True)
        elif self.formula_enter.isChecked():
            self.specific_layout.setDisabled(True)
            self.formula_layout.setDisabled(False)


    def get_info(self):
        if self.specific_enter.isChecked():
            frames = self.specific_input.text().split(",")
            try:
                frames = [int(s.strip("\n\t ")) for s in frames]
                frames.sort()
                return frames
            except: 
                return None
        elif self.formula_enter.isChecked():
            if not self.atevery_text.text().isnumeric():
                return None
            atevery = int( self.atevery_text.text() )
            if atevery <= 0:
                atevery = 1
            start_frame = 0
            end_frame = "duration"
            if self.startingat_text.text().isnumeric():
                start_frame = int( self.startingat_text.text() )
            if self.endingat_text.text().isnumeric():
                end_frame = int( self.endingat_text.text() )
            
            if end_frame == "duration":
                return (atevery, start_frame, end_frame)
            else:
                return [ *range(start_frame, end_frame + 1, atevery) ]

         

    def close_window(self):
        self.close()