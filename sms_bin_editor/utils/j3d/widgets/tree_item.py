from PyQt5.QtWidgets import QAction, QTreeWidget, QTreeWidgetItem, QFileDialog
from PyQt5.QtGui import  QIcon
from PyQt5.QtCore import Qt
import animations.general_animation as j3d
from widgets.yaz0 import compress, compress_slow, compress_fast
from io import BytesIO

class tree_item(QTreeWidgetItem):
    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent,1000)
        self.display_info = []
        self.filepath = ""
        self.compressed = 1
        self.bmd_file = None
        self.sound_data = None
        
        self.changed = False
        
    def set_values(self, display_info, filepath, compressed ):
        self.display_info = display_info
        self.filepath = filepath.replace("|", ".")
        self.compressed = compressed
        
        
        forward_i = filepath.rfind("/") + 1
        backwad_i = filepath.rfind("\\") + 1
        
        self.setText(0, self.filepath[max(forward_i, backwad_i):])
    
    def set_sound(self, sound_data):
        self.sound_data = sound_data
        if sound_data is not None:
            icon = QIcon("icons/sound.png")
            self.setIcon(0, icon)
        else:
            self.setIcon(0, QIcon() )
    
    def save_animation(self, other_filepath = "", compress_dis = 1, save_all = False):
        
        if save_all and not self.changed:
            print("skipping " + self.filepath + " because nothing has changed")
            return
        if other_filepath != "":
            working_filepath = other_filepath
        else:
            working_filepath = self.filepath
            
        if (working_filepath.endswith("a") and not working_filepath.endswith(".bva")  ):
            info = j3d.fix_array( self.display_info)
            self.convert_to_a(info)
        else: 
            info = j3d.fix_array( self.display_info)
            j3d.sort_filepath(working_filepath, info, self.sound_data) 
        
        compress_status = self.compressed
        if compress_dis != 0:
            compress_status = compress_dis
        print(compress_status)
        if compress_status > 1:
            out = BytesIO()
            with open(working_filepath, "rb") as f:
                if compress_status == 2:
                    out = compress_fast(f)
                elif compress_status == 3:
                    out = compress(f)
                elif compress_status == 4:
                    out = compress_slow(f)
            with open(working_filepath, "wb") as f:
                f.write(out.getbuffer())
        self.changed = False
    def convert_to_k(self):
        filepath = self.filepath[:-1] + "k"
        info = j3d.fix_array(self.display_info)  
        if self.filepath.endswith(".bca"):                     
            bck = j3d.sort_filepath(filepath, info)
        elif filepath.endswith(".bla"):             
            blk = j3d.sort_filepath(filepath, info)
        
    def convert_to_a(self, info):
    
        info = j3d.fix_array( info )
  
        if self.filepath.endswith(".bck") or self.filepath.endswith(".bca"):

         
            bca = j3d.convert_to_a(self.filepath, info) #this is a pure bck, no saving
            filepath = self.filepath[:-1] + "a"
            with open(filepath, "wb") as f:           
                bca.write_bca(f)
                f.close()
        elif self.filepath.endswith(".blk") or self.filepath.endswith(".bla"):
        
            
            bla = j3d.convert_to_a(self.filepath, info) #this is a pure bck, no saving
            filepath = self.filepath[:-1] + "a"
            with open(filepath, "wb") as f:           
                bla.write_bla(f)
                f.close()
    
    def export_anim(self):
        info = j3d.fix_array(self.display_info)  
        filepath = self.filepath[0:-4] + ".anim"
        if self.bmd_file is None:
            bmd_file, choosentype = QFileDialog.getOpenFileName( None, "Open File","" , "Model files (*.bmd *.bdl)")
            if bmd_file:
                
                bck = j3d.export_anim(filepath, info, bmd_file)
        else:
            bck = j3d.export_anim(filepath, info, self.bmd_file)
        
    def add_children(self, strings):
        self.takeChildren()
        for name in strings:
            child = QTreeWidgetItem(self)
            child.setText(0, name)
            child.setDisabled(True)