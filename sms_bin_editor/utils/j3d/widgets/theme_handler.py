import os

import PyQt5.QtGui as QtGui
from PyQt5 import QtCore, QtWidgets
from configparser import ConfigParser

class themed_window():
    def __init__(self, theme = "default"):
        self.theme = theme
    
    def set_theme(self, theme):
        self.theme = theme
        if theme != "default":
            self.toggle_dark_theme("./themes/"+theme+".qss")
        else:
            self.toggle_dark_theme("./themes/"+theme+".qss")
            
    def set_ini_theme(self):
        configur = ConfigParser()
        configur.read('settings.ini')
        theme = configur.get('menu options', 'theme')
        theme = theme.lower()
        self.set_theme(theme)
        

    def toggle_dark_theme(self, file = "", window = None): # simple little function to swap stylesheets
        if file == "":
            if window is None:
                self.setStyleSheet("")
            else:
                window.setShortcut("")
        else:
            with open (file) as f:
                lines = f.read()
                lines = lines.strip()
                if window is None:
                    self.setStyleSheet(lines)
                else:
                    window.setStyleSheet(lines)  
        
        
