import os
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog, QFileDialog, QSplitter, QListWidget, QListWidgetItem,
                             QScrollArea, QGridLayout, QAction, QApplication, QStatusBar, QLineEdit,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout, QComboBox)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui
from animations.general_animation import get_bones_from_bmd
from animations.general_animation import get_materials_from_bmd
import animations.general_animation as j3d
from widgets.theme_handler import *

class maedit_window(QDialog, themed_window):
    def __init__(self, theme):
        super().__init__()
        self.setup_ui(theme)
        self.set_theme(theme)
        
        
      
        
    def setup_ui(self, theme):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.setWindowTitle("edit all open animations")
        
        self.main_widget = maedit_widget(self, theme)
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
    
    def close_window(self):
        return self.main_widget.get_info()
class maedit_box(QWidget):
    def __init__(self, parent, one_time):
        super().__init__()
        self.setup_ui(parent.theme)
        
        self.parent = parent
        self.one_time = one_time
        
    def setup_ui(self, theme):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.main_widget = maedit_widget(self, theme)
        
        self.horizontalLayout = QVBoxLayout()
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        
        
        self.box_title = QLabel(self)
        self.box_title.setText("Mass Animation Editor")
        self.horizontalLayout.addWidget(self.box_title)
        
        self.setLayout(self.horizontalLayout)
        self.horizontalLayout.addWidget(self.main_widget)
        
        
        self.close_button = QPushButton(self)
        self.close_button.setText("Finish")
        self.close_button.clicked.connect(self.close_window)
        
        self.horizontalLayout.addWidget(self.close_button)       
            
    def close_window(self):
        self.parent.maedit_from_bar( self.get_info(), self.one_time )
    def get_info(self):

        values =  self.main_widget.get_info()
        return values
class maedit_widget(QWidget, themed_window):
    def __init__(self, parent, theme = "default"):
        super().__init__()
 
        self.parent = parent
        
        self.file_types_names = [".bck", ".bca", ".btk", ".brk", ".btp", ".bpk", ".bla", ".blk", ".bva" ];
        
        #stuff that we want to return / have access to
        self.selected = None
        self.filepath = None
        
        self.values = []
        
        self.setup_ui()
        self.set_theme(theme)
    def setup_ui(self):

        
        self.horizontalLayout = QHBoxLayout()
        self.centralwidget = self.horizontalLayout
        #self.setCentralWidget(self.horizontalLayout)
        
        self.setLayout(self.centralwidget)
        
        #choose the animation type
        self.type_layout = QWidget(self)
        self.type_box = QVBoxLayout(self.type_layout)
        
        self.select_label = QLabel(self.type_layout)
        self.select_label.setText("Select Animation Type to Edit")
        self.file_types = QListWidget(self.type_layout)
        self.file_types.clear()
        for type in self.file_types_names:
            self.file_types.addItem(type)
        self.file_types.setCurrentRow(0)
        self.file_types.clicked.connect(self.edit_right_side)
        
        self.type_box.addWidget(self.select_label)
        self.type_box.addWidget(self.file_types)
        
        #other needed info
        self.other_info_layout = QWidget(self)
        self.other_info_layout.setGeometry(0, 0, 250, 250)
    
        self.other_info_box = self.get_right_side()
  
        #add stuff to horizontal layout
        self.horizontalLayout.addWidget(self.type_layout)
        self.horizontalLayout.addWidget(self.other_info_layout)
    
    def edit_right_side(self):
        self.horizontalLayout.removeWidget(self.other_info_layout)
        self.other_info_layout = QWidget(self)
        self.other_info_box = self.get_right_side()
        self.horizontalLayout.addWidget(self.other_info_layout)
        if self.filepath:
            for i in range( self.bmd_thing_select.count() ):
                self.bmd_thing_select.remove(i)
            
            if self.selected in [".bck", ".bca"]:
                self.bmd_thing_select.addItems( j3d.get_bones_from_bmd(self.filepath) )
            elif self.selected in [".btk", ".btp", ".bpk", ".brk"]:
                self.bmd_thing_select.addItems( j3d.get_materials_from_bmd(self.filepath) )
            elif self.selected in [".blk", ".bla", ".bva"]:
                self.bmd_thing_select.addItems( j3d.get_meshes_from_bmd(self.filepath) )
    
    def create_combo_box(self, widget_parent):
        combo_box = QComboBox(widget_parent)
        combo_box.addItems( ["+", "-", "*", "/", "Average / Set To"] )
        return combo_box
        
    def get_right_side(self):
        operations_box = QGridLayout(self.other_info_layout)
        widget_parent = self.other_info_layout
        self.selected = self.file_types.currentItem().text()

        label = QLabel(widget_parent)
        label.setText("Select File")
        operations_box.addWidget(label, 0, 0)
        
        button = QPushButton("Select .bmd / .bdl")
        button.clicked.connect(self.open_file_dialog)
        operations_box.addWidget(button , 0, 1)
        
        self.bmd_thing_select = QComboBox(widget_parent)
        operations_box.addWidget(self.bmd_thing_select, 0, 2)
        
        if self.selected in [".bck", ".bca"]:
            srt = ["Scale ", "Rotation ", "Translation "];
            axis = ["X:", "Y:", "Z:"]
            for i in range(len( srt )):
                for j in range(len( axis)):
                    label = QLabel(widget_parent)
                    label.setText(srt[i] + axis[j])
                    operations_box.addWidget( label ,3 * i + j + 1, 0 )
                    operations_box.addWidget( self.create_combo_box(widget_parent),  3* i + j+ 1,  1)
                    operations_box.addWidget( QLineEdit(widget_parent), 3 * i + j+ 1,  2)

        elif self.selected in [".brk", ".bpk"]:
            #color animation
            comp = ["Red:", "Green:", "Blue:", "Alpha:"];
            for i in range(len( comp )):
                label = QLabel(widget_parent)
                label.setText(comp[i])
                operations_box.addWidget( label ,i+ 1, 0 )
                operations_box.addWidget( self.create_combo_box(widget_parent),  i + 1,  1)
                operations_box.addWidget( QLineEdit(widget_parent), i+ 1,  2)
        
        elif self.selected == ".btk":
            #texture swapping animation
            
            srt = ["Scale ", "Rotation ", "Translation "];
            axis = ["U:", "V:", "W:"]
            for i in range(len( srt )):
                for j in range(len( axis)):
                    label = QLabel(widget_parent)
                    label.setText(srt[i] + axis[j])
                    operations_box.addWidget( label ,3 * i + j+ 1, 0 )
                    operations_box.addWidget( self.create_combo_box(widget_parent),  3* i + j+ 1,  1)
                    operations_box.addWidget( QLineEdit(widget_parent), 3 * i + j+ 1,  2)
        
        elif self.selected in [".blk", ".bla"]:
            #cluster animation
            label = QLabel(widget_parent)
            label.setText("Weight")
            operations_box.addWidget( label , 1, 0 )
            operations_box.addWidget( self.create_combo_box(widget_parent),  1,  1)
            operations_box.addWidget( QLineEdit(widget_parent), 1,  2)
            #button.setDisabled(True)
       
        elif self.selected == ".btp":
            #texture swapping animation
            label = QLabel(widget_parent)
            label.setText("Texture Index")
            operations_box.addWidget( label , 1, 0 )
            operations_box.addWidget( self.create_combo_box(widget_parent),  1,  1)
            operations_box.addWidget( QLineEdit(widget_parent), 1,  2)
        elif self.selected == ".bva":
            #visibility animation
            label = QLabel(widget_parent)
            label.setText("Visibility")
            operations_box.addWidget( label , 1, 0 )
            
            combo_box = QComboBox(widget_parent)
            combo_box.addItems( ["Swap", "Set To"] )
            operations_box.addWidget( combo_box,  1,  1)
            
            operations_box.addWidget( QLineEdit(widget_parent), 1,  2)
            #button.setDisabled(True)
            
        return operations_box

    

    def get_info(self):
        if self.selected is None:
            return None
        if self.filepath is None:
            return None
        values = []
        for i in range(1, self.other_info_box.rowCount() ):
            comp = []
            
            combo_box = self.other_info_box.itemAtPosition(i, 0).widget()
            comp.append( combo_box.text() )
            
            combo_box = self.other_info_box.itemAtPosition(i, 1).widget()
            comp.append( combo_box.currentIndex() )
            
            line_edit = self.other_info_box.itemAtPosition(i, 2).widget()
            comp.append( line_edit.text() )
            
            values.append(comp)
        if self.filepath.endswith(".bva"):
            # we KNOW that values only has one entry
            combo_box = self.other_info_box.itemAtPosition(i, 1).widget()
            if self.combo_box.currentIndex() == 0: #if swap
                values[0][2] = ""
            
        #print(self.selected, self.bmd_thing_select.currentText(), values)
        return ( [[self.selected, self.bmd_thing_select.currentText(), values]] )

         
    def open_file_dialog(self):
        filepath, choosentype = QFileDialog.getOpenFileName(self.other_info_layout, "Choose File Path", "", "j3d model files (*.bmd *.bdl)")
        if filepath:
            #self.filename_text.setText(filepath)
            self.filepath = filepath
            
            for i in range( self.bmd_thing_select.count() ):
                self.bmd_thing_select.remove(i)
            if self.selected in [".bck", ".bca"]:
                self.bmd_thing_select.addItems( j3d.get_bones_from_bmd(filepath) )
            elif self.selected in [".btk", ".btp", ".bpk", ".brk"]:
                self.bmd_thing_select.addItems( j3d.get_materials_from_bmd(filepath) )
            elif self.selected in [".blk", ".bla", ".bva"]:
                self.bmd_thing_select.addItems( j3d.get_meshes_from_bmd(filepath) )