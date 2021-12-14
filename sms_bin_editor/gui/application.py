import pickle
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from PySide2.QtWidgets import QApplication
from sms_bin_editor import __version__
from sms_bin_editor.gui.widgets.object import ObjectHierarchyWidgetItem
from sms_bin_editor.gui.windows.mainwindow import MainWindow
from sms_bin_editor.scene import SMSScene
from sms_bin_editor.utils.filesystem import get_program_folder
from sms_bin_editor.gui.settings import SMSBinEditorSettings


class SMSBinEditor(QApplication):
    """
    Bin Editor application
    """
    __SINGLE_INSTANCE: "SMSBinEditor" = None
    __SINGLE_INITIALIZED = False
    
    def __new__(cls, *args, **kwargs) -> "SMSBinEditor":
        if cls.__SINGLE_INSTANCE is None:
            cls.__SINGLE_INSTANCE = super().__new__(cls, *args, **kwargs)
        return cls.__SINGLE_INSTANCE

    def __init__(self):
        if self.__SINGLE_INITIALIZED:
            return

        super().__init__()

        self.gui = MainWindow()
        self._scene: SMSScene = None
        self.settings: SMSBinEditorSettings = None

        self.gui.setWindowTitle(self.get_window_title())
        self.update_theme(MainWindow.Themes.LIGHT)

        self.gui.objectHierarchyView.currentItemChanged.connect(
            lambda cur, prev: self.set_object_properties_tab(cur, prev))

        self.__SINGLE_INITIALIZED = True

    # --- GETTER / SETTER --- #

    def get_instance(self) -> "SMSBinEditor":
        return self.__SINGLE_INSTANCE

    @property
    def scene(self) -> SMSScene:
        return self._scene

    @scene.setter
    def scene(self, scene: SMSScene):
        self._scene = scene
        self.update_elements()

    # --- GUI --- #

    @staticmethod
    def get_config_path():
        versionStub = __version__.replace(".", "-")
        return get_program_folder(f"{__name__} v{versionStub}") / "program.cfg"

    @staticmethod
    def get_window_title():
        return f"{__class__.__name__} v{__version__}"

    @staticmethod
    def open_path_in_explorer(path: Path):
        if sys.platform == "win32":
            subprocess.Popen(
                f"explorer /select,\"{path.resolve()}\"", shell=True)
        elif sys.platform == "linux":
            subprocess.Popen(["xdg-open", path.resolve()])
        elif sys.platform == "darwin":
            subprocess.Popen(['open', '--', path.resolve()])

    def load_program_config(self):
        """
        Load the program config for further use
        """
        self.settings = SMSBinEditorSettings()

        if not self.get_config_path().exists():
            self.theme = MainWindow.Themes.LIGHT
            return

        self.settings.load(self.get_config_path())

        isDarkTheme = self.settings.is_dark_theme()
        isUpdating = self.settings.is_updates_enabled()

        self.theme = SMSBinEditorSettings.Themes(int(isDarkTheme))

        self.construct_ui_from_config()

    def construct_ui_from_config(self):
        """
        Restructures the UI according to a config
        """
        config = self.settings

    def update_theme(self, theme: "MainWindow.Themes"):
        """
        Update the UI theme to the specified theme
        """
        from qdarkstyle import load_stylesheet
        if theme == MainWindow.Themes.LIGHT:
            self.theme = MainWindow.Themes.LIGHT
            self.setStyleSheet("")
        else:
            self.theme = MainWindow.Themes.DARK
            self.setStyleSheet(load_stylesheet())

    def update_elements(self):
        """
        Hard update the elements
        """
        self.gui.objectHierarchyView.populate_objects_from_scene(self._scene)
        self.gui.railListView.populate_rails_from_scene(self._scene)

    def set_object_properties_tab(self, current: ObjectHierarchyWidgetItem, previous: ObjectHierarchyWidgetItem):
        focusedObj = current.object
        self.gui.objectPropertyView.populate_attributes_from_object(focusedObj)

    def show(self):
        """
        Show the GUI
        """
        self.gui.show()

    # --- LOGIC --- #

    def load_scene(self, scene: Path) -> bool:
        """
        Load a scene into the GUI
        """
        self.scene = SMSScene.from_path(scene)
        return self.scene is not None
