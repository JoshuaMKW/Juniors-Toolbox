import pickle
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
from PySide2.QtCore import QPoint, Slot
from PySide2.QtGui import Qt

from PySide2.QtWidgets import QApplication, QDockWidget, QMainWindow, QSizePolicy, QWidget
from juniors_toolbox import __version__
from juniors_toolbox.gui.tabs import TabWidgetManager
from juniors_toolbox.gui.tabs.object import ObjectHierarchyWidget, ObjectHierarchyWidgetItem, ObjectPropertiesWidget
from juniors_toolbox.gui.widgets.synceddock import SyncedDockWidget
from juniors_toolbox.gui.windows.mainwindow import MainWindow
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.filesystem import get_program_folder
from juniors_toolbox.gui.settings import SMSBinEditorSettings


class JuniorsToolbox(QApplication):
    """
    Junior's Toolbox Application
    """
    __SINGLE_INSTANCE: "JuniorsToolbox" = None
    __SINGLE_INITIALIZED = False

    def __new__(cls, *args, **kwargs) -> "JuniorsToolbox":
        if cls.__SINGLE_INSTANCE is None:
            cls.__SINGLE_INSTANCE = super().__new__(cls, *args, **kwargs)
        return cls.__SINGLE_INSTANCE

    def __init__(self):
        if self.__SINGLE_INITIALIZED:
            return

        super().__init__()

        # Force Windows Taskbar Icon
        if sys.platform in {"win32", "cygwin", "msys"}:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                self.get_window_title())

        self.gui = MainWindow()
        self.settings: SMSBinEditorSettings = None

        TabWidgetManager.init(self.gui)

        self.gui.setWindowTitle(self.get_window_title())
        # self.gui.setCentralWidget(None)
        self.gui.centralWidget().setMaximumSize(5, 5)
        self.gui.layout().setContentsMargins(0, 0, 0, 0)
        self.update_theme(MainWindow.Themes.LIGHT)

        # Set up tab spawning
        self.gui.tabActionRequested.connect(self.openDockerTab)

        self._tabGroups: Dict[str, QDockWidget] = {}
        self._openTabs: Dict[str, QDockWidget.DetachedTab] = {}

        # Set up tab syncing
        objectPropertyTab = TabWidgetManager.get_tab(ObjectPropertiesWidget)
        objectHierarchyTab = TabWidgetManager.get_tab(ObjectHierarchyWidget)
        objectHierarchyTab.currentItemChanged.connect(
            lambda cur, prev: objectPropertyTab.populate(cur.object, self.scenePath))

        self.__scene = SMSScene()
        self.__scenePath = None

        self.__SINGLE_INITIALIZED = True

    # --- GETTER / SETTER --- #

    def get_instance(self) -> "JuniorsToolbox":
        return self.__SINGLE_INSTANCE

    @property
    def scene(self) -> SMSScene:
        return self.__scene
        # return self.construct_scene_from_elements()

    @scene.setter
    def scene(self, scene: SMSScene):
        self.__scene = scene
        self.update_elements(scene)

    @property
    def scenePath(self) -> Path:
        return self.__scenePath

    @scenePath.setter
    def scenePath(self, path: Path):
        self.__scenePath = path

    # --- GUI --- #

    @staticmethod
    def get_config_path():
        versionStub = __version__.replace(".", "-")
        return get_program_folder(f"{__name__} v{versionStub}") / "program.cfg"

    @staticmethod
    def get_window_title():
        return f"Junior's Toolbox v{__version__}"

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

    def update_elements(self, scene: SMSScene):
        """
        Hard update the elements
        """
        for tab in TabWidgetManager.iter_tabs():
            tab.populate(scene, self.scenePath)

    def construct_scene_from_elements(self) -> SMSScene:
        ...

    def show(self):
        """
        Show the GUI
        """
        self.gui.show()

    def iter_tab_groups(self) -> Iterable[QDockWidget]:
        for value in self._tabGroups.values():
            yield value

    def get_tab_group(self, name: str) -> QDockWidget:
        for group in self.iter_tab_groups():
            if group.objectName() == name:
                return group
        return None

    def embed_tab(self, tab: QDockWidget, pos: QPoint):
        for tabGroup in self.iter_tab_groups():
            ...

    @Slot(str)
    def openDockerTab(self, name: str):
        tab = TabWidgetManager.get_tab(name)
        if name in self._openTabs:
            return
        deTab = SyncedDockWidget(name)
        deTab.setWidget(tab)
        deTab.setFloating(False)
        self.gui.addDockWidget(Qt.LeftDockWidgetArea, deTab)

        deTab.closed.connect(self.closeDockerTab)
        deTab.show()
        self._openTabs[name] = deTab

    @Slot(str)
    def closeDockerTab(self, tab: SyncedDockWidget):
        print(tab.windowTitle())
        if tab.windowTitle() not in self._openTabs:
            return
        self.gui.removeDockWidget(self._openTabs.pop(tab.windowTitle()))

    # --- LOGIC --- #

    def load_scene(self, scene: Path) -> bool:
        """
        Load a scene into the GUI
        """
        self.scene = SMSScene.from_path(scene)
        self.scenePath = scene
        return self.scene is not None
