import os
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt, QRect, QModelIndex

from PyQt5.QtWidgets import (QWidget, QDialog, QFileDialog, QSplitter, QListWidget, QListWidgetItem,
                             QScrollArea, QGridLayout, QAction, QApplication, QStatusBar, QLineEdit,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout, QComboBox)

from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui
from animations.bck import sound_entry

from widgets.theme_handler import *

class sounds_window(QDialog, themed_window):
    def __init__(self, theme, sound_data):
        super().__init__()
        self.setup_ui(theme, sound_data)
        self.set_theme(theme)
        
    def setup_ui(self, theme, sound_data):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.setWindowTitle("edit sound entries")
        
        self.main_widget = sounds_widget(self, theme, sound_data)
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
        
    def get_on_screen(aelf):
        return self.main_widget.get_on_screen()
class sounds_box(QWidget):
    def __init__(self, parent, one_time, sound_data):
        super().__init__()
        self.setup_ui(parent.theme, sound_data)
        
        self.parent = parent
        self.one_time = one_time
        
    def setup_ui(self, theme, sound_data):
        self.resize(1600, 400)
        self.resize_mw=QAction()
        self.main_widget = sounds_widget(self, theme, sound_data)
        
        self.horizontalLayout = QVBoxLayout()
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        
        
        self.box_title = QLabel(self)
        self.box_title.setText("Sound Editor")
        self.horizontalLayout.addWidget(self.box_title)
        
        self.setLayout(self.horizontalLayout)
        self.horizontalLayout.addWidget(self.main_widget)
        
        
        self.close_button = QPushButton(self)
        self.close_button.setText("Finish")
        self.close_button.clicked.connect(self.close_window)
        
        self.horizontalLayout.addWidget(self.close_button)       
        
    def close_window(self):
        self.parent.sounds_from_bar( self.get_info(), self.one_time )
    def get_info(self):

        values =  self.main_widget.get_info()
        return values
        
    def get_on_screen(self):
        return self.main_widget.get_on_screen()
class sounds_widget(QWidget, themed_window):
    def __init__(self, parent, theme, sound_data):
        super().__init__()
 
        self.parent = parent
        self.sound_data = sound_data
        
        #stuff that we want to return / have access to
        self.selected = None
        self.filepath = None
        
        self.change_nothing = True
        
        self.setup_ui()
        self.setup_sound_data()
        self.sound_bar.itemSelectionChanged.connect(self.edit_right_side) 
        self.change_nothing = False
        self.set_theme(theme)
    def setup_ui(self):
        #will set up the basic layout with no information
        
        self.horizontalLayout = QHBoxLayout()
        self.centralwidget = self.horizontalLayout
        #self.setCentralWidget(self.horizontalLayout)
        
        self.setLayout(self.centralwidget)
        
        #choose the animation type
        self.type_layout = QWidget(self)
        self.type_box = QVBoxLayout(self.type_layout)
        
        self.select_label = QLabel(self.type_layout)
        self.select_label.setText("Select Entry to Edit")
        self.sound_bar = sound_entry_selector(self.type_layout)
        self.sound_bar.clear()
        
        
        self.add_entry = QPushButton(self.type_layout)
        self.add_entry.setText("Add New Sound Entry")
        self.add_entry.clicked.connect(self.add_blank_entry)
        
        self.delete_entry = QPushButton(self.type_layout)
        self.delete_entry.setText("Remove Current Sound Entry")
        self.delete_entry.clicked.connect(self.delete_curr_entry)
        
        
        self.type_box.addWidget(self.select_label)
        self.type_box.addWidget(self.sound_bar)
        self.type_box.addWidget(self.add_entry)
        self.type_box.addWidget(self.delete_entry)
        
        #other needed info
        self.other_info_layout = QWidget(self)
        self.other_info_layout.setGeometry(0, 0, 250, 250)
    
        self.other_info_box = self.create_right_side()
  
        #add stuff to horizontal layout
        self.horizontalLayout.addWidget(self.type_layout)
        self.horizontalLayout.addWidget(self.other_info_layout)
        
    def setup_sound_data(self):
        self.change_nothing = True
        self.sound_bar.clear()
        
        if self.sound_data is not None:
            self.other_info_layout.setDisabled(False)
            for i in range( len(self.sound_data) ):
                current_sound_entry = single_sound_entry(self.sound_bar, self.sound_data[i])
                current_sound_entry.setText("Sound Entry " + str(i) )
                #self.sound_bar.addItem( current_sound_entry )
                self.sound_bar.setCurrentItem(current_sound_entry)
                self.sound_bar.curr_item = current_sound_entry
            if len(self.sound_data) > 0:
                self.set_right_side()
        else:
            self.sound_id_field.setText( "" )
            self.start_time_field.setText( "" )
            self.end_time_field.setText( "" )
            self.flags_field.setText( "" )
            self.loop_count_field.setText( "" )
            self.volume_field.setText( "" )
            self.coarse_pitch_field.setText( "" )
            self.fine_pitch_field.setText( "")
            self.pan_field.setText("" )
            self.unk_byte_field.setText( "" )
            self.other_info_layout.setDisabled(True)
        self.change_nothing = False
    def create_right_side(self):
        #will fill in the stuff on the right side - basically all the annoying fields and labels
        operations_box = QGridLayout(self.other_info_layout)
        widget_parent = self.other_info_layout
        
        label = QLabel(widget_parent)
        label.setText("Select File")
        operations_box.addWidget(label, 0, 0)
        
        button = QPushButton("Import from .bck")
        button.clicked.connect(self.open_file_dialog)
        operations_box.addWidget(button , 0, 1)
        
        #-------------------------------------------
        
        label_soundid = QLabel(widget_parent)
        label_soundid.setText("Sound ID:")
        operations_box.addWidget(label_soundid, 1, 0)
        
        self.sound_id_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.sound_id_field, 1, 1)
        
        #-------------------------------------------
        
        label_start_time = QLabel(widget_parent)
        label_start_time.setText("Start Frame:")
        operations_box.addWidget(label_start_time, 2, 0) 
        
        self.start_time_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.start_time_field, 2, 1)
        
        label_end_time = QLabel(widget_parent)
        label_end_time.setText("End Frame:")
        operations_box.addWidget(label_end_time, 3, 0) 
        
        self.end_time_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.end_time_field, 3, 1)  
        
        label_flags = QLabel(widget_parent)
        label_flags.setText("Loop Flags:")
        operations_box.addWidget(label_flags, 4, 0) 
        
        self.flags_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.flags_field, 4, 1)

        label_loop_count = QLabel(widget_parent)
        label_loop_count.setText("Loop Count:")
        operations_box.addWidget(label_loop_count, 5, 0) 
        
        self.loop_count_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.loop_count_field, 5, 1)
        
        #----------------------------------
        
        label_volume = QLabel(widget_parent)
        label_volume.setText("Volume:")
        operations_box.addWidget(label_volume, 6, 0) 
        
        self.volume_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.volume_field, 6, 1)
        
        label_coarse_pitch = QLabel(widget_parent)
        label_coarse_pitch.setText("Coarse Pitch:")
        operations_box.addWidget(label_coarse_pitch, 7, 0) 
        
        self.coarse_pitch_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.coarse_pitch_field, 7, 1)

        label_fine_pitch = QLabel(widget_parent)
        label_fine_pitch.setText("Fine Pitch:")
        operations_box.addWidget(label_fine_pitch, 8, 0) 
        
        self.fine_pitch_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.fine_pitch_field, 8, 1)
       
        label_pan = QLabel(widget_parent)
        label_pan.setText("Pan:")
        operations_box.addWidget(label_pan, 9, 0) 
        
        self.pan_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.pan_field, 9, 1)
        
        #--------------------------------
        
        label_unk_byte = QLabel(widget_parent)
        label_unk_byte.setText("Speed / Interval Value:")
        operations_box.addWidget(label_unk_byte, 10, 0) 
        
        self.unk_byte_field = QLineEdit(widget_parent)
        operations_box.addWidget( self.unk_byte_field, 10, 1) 
            
        return operations_box
    
    def edit_right_side(self):
        #handles when the current selected sound entry is changed
        if self.change_nothing == False:
            if self.sound_bar.count() > 0:
                new_sound_data_entry = self.get_on_screen()
                print( new_sound_data_entry )
                self.sound_bar.curr_item.sound_data_entry = new_sound_data_entry
                self.sound_bar.curr_item = self.sound_bar.currentItem()
                self.set_right_side()
        self.change_nothing = False
    

    def get_on_screen(self):
        if self.change_nothing == False and self.sound_id_field.text() != "":
            sound_id = float(self.sound_id_field.text())
            start_time = float(self.start_time_field.text())
            end_time = float( self.end_time_field.text() )
            coarse_pitch = float(self.coarse_pitch_field.text() )
            flags = int(self.flags_field.text())
            volume = int(self.volume_field.text() )
            fine_pitch = int(self.fine_pitch_field.text() )
            loop_count = int(self.loop_count_field.text() )
            pan = int(self.pan_field.text() )
            unk_byte = int(self.unk_byte_field.text() )
            new_sound_entry = sound_entry(sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte)
            return new_sound_entry

    def set_right_side(self):
        #will set the values on the right side in all cases - will use the currentitem of the listwidget
        sound_data_entry = self.sound_bar.currentItem().sound_data_entry
        self.sound_id_field.setText( str(sound_data_entry.sound_id) )
        self.start_time_field.setText( str(int(sound_data_entry.start_time)) )
        self.end_time_field.setText( str(int(sound_data_entry.end_time)) )
        self.flags_field.setText( str(sound_data_entry.flags) )
        self.loop_count_field.setText( str(sound_data_entry.loop_count) )
        self.volume_field.setText( str(sound_data_entry.volume) )
        self.coarse_pitch_field.setText( str(sound_data_entry.coarse_pitch) )
        self.fine_pitch_field.setText( str(sound_data_entry.fine_pitch) )
        self.pan_field.setText( str(sound_data_entry.pan) )
        self.unk_byte_field.setText( str(sound_data_entry.unk_byte) )
        
    def add_blank_entry(self):
        self.change_nothing = True
        self.other_info_layout.setDisabled(False)
        new_entry = single_sound_entry(self.sound_bar)
        
        new_entry.setText("Sound Entry " + str(self.sound_bar.count() - 1) )
        
        self.sound_bar.curr_item = new_entry
        self.sound_bar.setCurrentItem(new_entry)
        self.change_nothing = False
        self.set_right_side()
        
    def delete_curr_entry(self): 
               
        self.sound_bar.takeItem(self.sound_bar.currentRow())
        
        if self.sound_bar.count() > 0: 

            self.sound_bar.curr_item = self.sound_bar.currentItem()
            self.set_right_side()
        else:
            self.other_info_layout.setDisabled(True)

    def get_soundids_combobox(self, widget_parent):
        #will fill in the combo box with the sound ids - gotta get back to xayr
        combo_box = QComboBox(widget_parent)
        return combo_box
        

    def get_info(self):
        if self.sound_bar.count() == 0:
            return None
        new_sound_data_entry = self.get_on_screen()
        self.sound_bar.curr_item.sound_data_entry = new_sound_data_entry
        
        new_sound_data = []
        for i in range(0, self.sound_bar.count() ):
            new_sound_data.append( self.sound_bar.item(i).sound_data_entry )
            
            
        return new_sound_data


         
    def open_file_dialog(self):
        filepath, choosentype = QFileDialog.getOpenFileName(self.other_info_layout, "Choose File Path", "", "bck files (*.bck)")
        if filepath:
            #self.filename_text.setText(filepath)
            self.filepath = filepath
            self.sound_data = sound_entry.read_sound_data(filepath)
            self.setup_sound_data()

class sound_entry_selector( QListWidget):
    def __init__(self, parent):
        QListWidget.__init__(self, parent = parent)
        self.curr_item = None
    

class single_sound_entry( QListWidgetItem ):
    def __init__(self, parent, sound_data_entry = None):
        QListWidgetItem.__init__(self, parent = parent)
        if sound_data_entry is not None:
            self.sound_data_entry = sound_data_entry
        else:
            self.sound_data_entry = sound_entry.blank_entry()
        print(self.sound_data_entry)
    def from_fields(self, sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte):
        self.sound_data_entry = sound_entry(sound_id, start_time, end_time, coarse_pitch, flags, volume, fine_pitch, loop_count, pan, unk_byte)
        
def read_sound_id_file (filepath): 
    sound_labels = []
    all_file_lines = []
    with open(filepath, "r") as f:
        all_files_lines = f.readlines()
    for line in all_file_lines:
        line = line.rstrip(",")
        line = line.split(" = ")
        
       