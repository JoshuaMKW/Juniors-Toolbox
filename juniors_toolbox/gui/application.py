import pickle
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from PySide2.QtCore import QPoint, QSize, Slot
from PySide2.QtGui import QResizeEvent, Qt

from PySide2.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow, QSizePolicy, QStyleFactory, QWidget
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
    __singleton: "JuniorsToolbox" = None
    __singleton_ready = False

    def __new__(cls, *args, **kwargs) -> "JuniorsToolbox":
        if cls.__singleton is None:
            cls.__singleton = super().__new__(cls, *args, **kwargs)
        return cls.__singleton

    def __init__(self):
        if self.__singleton_ready:
            return

        super().__init__()
        TabWidgetManager.init()

        self.__singleton_ready = True

        # Force Windows Taskbar Icon
        if sys.platform in {"win32", "cygwin", "msys"}:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                self.get_window_title())

        self.gui = MainWindow()
        self.settings: SMSBinEditorSettings = None

        self.__scene = SMSScene()
        self.__scenePath = None
        self.__openTabs: Dict[str, SyncedDockWidget] = {}

        # Set up tab syncing
        objectPropertyTab = TabWidgetManager.get_tab(ObjectPropertiesWidget)
        objectHierarchyTab = TabWidgetManager.get_tab(ObjectHierarchyWidget)
        objectHierarchyTab.currentItemChanged.connect(
            lambda cur, prev: objectPropertyTab.populate(cur.object, self.scenePath))

        self.gui.setWindowTitle(self.get_window_title())
        self.update_theme(MainWindow.Themes.LIGHT)
        self.set_central_status(self.is_docker_empty())

        # Set up tab spawning
        self.gui.tabActionRequested.connect(self.openDockerTab)
        self.gui.resized.connect(self.force_minimum_size)

    # --- GETTER / SETTER --- #

    def get_instance(self) -> "JuniorsToolbox":
        return self.__singleton

    @property
    def scene(self) -> SMSScene:
        return self.__scene

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

    @Slot(str)
    def openDockerTab(self, name: str):
        tab = TabWidgetManager.get_tab(name)
        if name in self.__openTabs:
            return
        deTab = SyncedDockWidget(name)
        deTab.setObjectName(name)
        deTab.setWidget(tab)
        deTab.setFloating(len(self.__openTabs) > 0)
        deTab.setAllowedAreas(Qt.AllDockWidgetAreas)
        deTab.resized.connect(self.force_minimum_size)
        deTab.topLevelChanged.connect(lambda _: self.set_central_status(self.is_docker_empty()))
        areas = [Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea]
        self.gui.addDockWidget(areas[len(self.__openTabs) % 2], deTab)

        deTab.closed.connect(self.closeDockerTab)
        deTab.show()
        self.__openTabs[name] = deTab
        
        self.set_central_status(self.is_docker_empty())


    @Slot(str)
    def closeDockerTab(self, tab: SyncedDockWidget):
        if tab.windowTitle() not in self.__openTabs:
            return
        tab = self.__openTabs.pop(tab.windowTitle())
        tab.setWidget(None)
        self.gui.removeDockWidget(tab)
        self.set_central_status(self.is_docker_empty())

    def is_docker_empty(self) -> bool:
        return len(self.__openTabs) == 0
        #print([w.isFloating() for w in self.__openTabs.values()])
        #print([w.isWindowType() for w in self.__openTabs.values()])
        return all([w.isFloating() for w in self.__openTabs.values()])

    def get_min_hw(self) -> QSize:
        htabs = {}
        wtabs = {}

        tabs = self.__openTabs.values()
        if len(tabs) == 0:
            return self.gui.minimumSize()

        for i, tab in enumerate(tabs):
            htabs[tab] = []
            wtabs[tab] = []
            for innertab in tabs:
                if innertab.objectName() == tab.objectName():
                    continue
                if innertab.isFloating():
                    continue
                #print(f"{tab.objectName()} -> {innertab.objectName()}", tab.y_contains(innertab.pos().y(), innertab.size().height()), tab.x_contains(innertab.pos().x(), innertab.size().width()), ":")
                if tab.y_contains(innertab.pos().y(), innertab.size().height()):
                    if innertab.pos().x() <= tab.pos().x():
                        continue
                    wtabs[tab].append(innertab)
                elif tab.x_contains(innertab.pos().x(), innertab.size().width()):
                    if innertab.pos().y() <= tab.pos().y():
                        continue
                    htabs[tab].append(innertab)

        def recursive_sum_w(connections: dict, node: SyncedDockWidget) -> QSize:
            _width = node.minimumSize().width()
            if len(connections[node]) == 0:
                return _width
            #print([recursive_sum_w(connections, tab) for tab in connections[node]])
            _width += max([recursive_sum_w(connections, tab) for tab in connections[node]])
            return _width + 16

        def recursive_sum_h(connections: dict, node: SyncedDockWidget) -> QSize:
            _height = node.minimumSize().height()
            if len(connections[node]) == 0:
                return _height
            #print([recursive_sum_h(connections, tab) for tab in connections[node]])
            _height += max([recursive_sum_h(connections, tab) for tab in connections[node]])
            return _height + 16
                

        width = max([recursive_sum_w(wtabs, tab) for tab in wtabs]) if len(wtabs) > 0 else self.gui.minimumSize().width() + self.gui.centralWidget().minimumSize().width()
        height = max([recursive_sum_h(htabs, tab) for tab in htabs]) if len(htabs) > 0 else self.gui.minimumSize().height() + self.gui.centralWidget().minimumSize().height()
        return QSize(width, height)
    
    @Slot(QResizeEvent)
    def force_minimum_size(self, event: QResizeEvent):
        size = self.get_min_hw()
        self.gui.setMinimumSize(size)
        if event.size().height() > size.height():
            size.setHeight(event.size().height())
        if event.size().width() > size.width():
            size.setWidth(event.size().width())

    def set_central_status(self, empty: bool):
        if empty:
            center = QLabel()
            center.setText("No tabs open\n(Open tabs using the Window menu)")
            center.setEnabled(False)
            center.setAlignment(Qt.AlignCenter)
        else:
            center = QWidget()
            center.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
            #center.setFixedSize(8, 8)
        self.gui.setCentralWidget(center)
        

    # --- LOGIC --- #

    def load_scene(self, scene: Path) -> bool:
        """
        Load a scene into the GUI
        """
        self.scene = SMSScene.from_path(scene)
        self.scenePath = scene
        return self.scene is not None
