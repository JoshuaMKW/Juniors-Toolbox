from PyQt5.QtWidgets import QAction, QMenu, QTreeWidget, QTreeWidgetItem
from PyQt5.QtCore import Qt
from animation_editor import GenEditor
from widgets.yaz0 import compress
from io import BytesIO
from animations.general_animation import fix_array, sort_filepath
import animations.general_animation as j3d

class animation_bar(QTreeWidget):
    def __init__(self, parent):  
        QTreeWidget.__init__(self, parent = parent)
        self.main_editor = None
        self.setColumnCount(1)
        self.setHeaderLabel("Animations")
        self.setGeometry(0, 50, 200, 850)
        self.resize(800, self.height())
        
        self.curr_item = None
        
        self.parent = parent
        
        self.sound_data_clipboard = None
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.run_context_menu)
    def set_main_editor(self, main_window):
        self.main_editor = main_window
    
    
    def run_context_menu(self, pos):
        if self.topLevelItemCount() < 1:
            return self.parent.sounds_dialogue(one_time = False)
        
        
        
        index = self.currentIndex().row()
        
        #print("context menu triggered")
        
        context_menu = QMenu(self)
        
        def emit_sound_window():
            self.main_editor.sounds_dialogue(one_time = True)
            
        def emit_copy_sound():
            print("copy")
            paste_sound_action.setDisabled(False)
            self.sound_data_clipboard = self.currentItem().sound_data
            
            
        def emit_paste_sound():
            self.currentItem().set_sound( self.sound_data_clipboard )
            
            
            if self.main_editor.sounds_box is not None:
                self.main_editor.sounds_box.main_widget.sound_data = self.sound_data_clipboard
                self.main_editor.sounds_box.main_widget.setup_sound_data()
        
        
        
        if self.main_editor.sound_enabled and self.curr_item.filepath.endswith(".bck"):
            edit_sound_action = QAction("Edit Sound Data", self)
            edit_sound_action.triggered.connect( emit_sound_window )
            context_menu.addAction( edit_sound_action )
                
            copy_sound_action = QAction("Copy Sound Data", self)
            copy_sound_action.triggered.connect( emit_copy_sound )
            context_menu.addAction( copy_sound_action )
            
            paste_sound_action = QAction("Paste Sound Data", self)
            paste_sound_action.triggered.connect( emit_paste_sound )
            context_menu.addAction( paste_sound_action )
            
        
            context_menu.addSeparator()
        
        close_action = QAction("Close Current Animation", self)
        close_all_action = QAction("Close All Animations", self)

        
        #copy_action = QAction("Copy Animation", self)

        
        def emit_close():
            
            print(" emit close ")
            
            self.main_editor.is_remove = True
            
            items = self.selectedItems()         
            min_index = 0
            for item in items:
                self.takeTopLevelItem(index)
               
            self.main_editor.table_display.clearContents()  
            
            if self.topLevelItemCount() > 0: 
               
            
            
                print("load the previous animation to the middle. index: " + str(index) )
                self.curr_item = self.currentItem()
                self.main_editor.load_animation_to_middle(self.currentItem())
            self.main_editor.is_remove = False
            print("done with removing")
        def emit_close_all():
            
            print(" emit close ")
            
            self.main_editor.is_remove = True
            self.clear()

            self.main_editor.table_display.clearContents()  
            
           
            self.main_editor.is_remove = False
            print("done with removing")                    
        def emit_copy():
            items = self.selectedItems()
            
            if ( len(items) > 1):
                return

            current_entry = main_editor.list_of_animations[index]
            copied_entry = all_anim_information.get_copy(current_entry)
            list_of_animations.insert(index + 1, copied_entry)
             
            widget = self.selectedItems()
            widget = widget[0].clone()
            
            self.addTopLevelItem(widget)
            self.setCurrentItem(widget)
         
        
        close_action.triggered.connect(emit_close)
        close_all_action.triggered.connect(emit_close_all)
        #copy_action.triggered.connect(emit_copy)
        
       
        context_menu.addAction(close_action)
        context_menu.addAction(close_all_action)
        
        context_menu.exec(self.mapToGlobal(pos))
        context_menu.destroy()
        del context_menu

