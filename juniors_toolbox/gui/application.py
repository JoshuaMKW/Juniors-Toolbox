import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from PySide6.QtCore import QPoint, QSize, Slot
from PySide6.QtGui import QResizeEvent, Qt, QFontDatabase

from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QSizePolicy, QStyleFactory, QWidget
from juniors_toolbox import __version__
from juniors_toolbox.gui.settings import ToolboxSettings
from juniors_toolbox.gui.tabs import TabWidgetManager
from juniors_toolbox.gui.tabs.hierarchyviewer import NameRefHierarchyWidget
from juniors_toolbox.gui.tabs.projectviewer import ProjectViewerWidget
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.windows.mainwindow import MainWindow
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.filesystem import get_program_folder, resource_path
from juniors_toolbox.gui import ToolboxManager


class JuniorsToolbox(QApplication):
    """
    Junior's Toolbox Application
    """
    __singleton: Optional["JuniorsToolbox"] = None
    __singleton_ready = False

    def __new__(cls, *args: VariadicArgs, **kwargs: VariadicKwargs) -> "JuniorsToolbox":
        if cls.__singleton is None:
            cls.__singleton = super().__new__(cls, *args, **kwargs)
        return cls.__singleton

    def __init__(self):
        if self.__singleton_ready:
            return

        super().__init__()

        self.__singleton_ready = True

        # Force Windows Taskbar Icon
        if sys.platform in {"win32", "cygwin", "msys"}:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                self.get_window_title())

        self.gui = MainWindow()
        self.manager = ToolboxManager()

        self.__scenePath: Optional[Path] = None
        self.__openTabs: Dict[str, A_DockingInterface] = {}
        self.__tabs: Dict[str, A_DockingInterface] = {}

        TabWidgetManager.init()

        # Set up tab syncing
        objectPropertyTab = TabWidgetManager.get_tab(SelectedPropertiesWidget)
        objectHierarchyTab = TabWidgetManager.get_tab(NameRefHierarchyWidget)
        objectHierarchyTab.treeWidget.currentItemChanged.connect(
            lambda cur, prev: objectPropertyTab.populate(cur.object, self.scenePath))

        self.gui.setWindowTitle(self.get_window_title())
        self.update_theme(MainWindow.Theme.LIGHT)
        self.set_central_status(self.is_docker_empty())

        # Set up tab spawning
        self.gui.tabActionRequested.connect(self.openDockerTab)

        # Set up file dialogs
        self.gui.actionNew.triggered.connect(
            lambda _: self.reset()
        )  # throw away checked flag
        self.gui.actionClose.triggered.connect(
            lambda _: self.reset()
        )  # throw away checked flag
        self.gui.actionOpen.triggered.connect(
            lambda _: self.open_scene()
        )  # throw away checked flag
        self.gui.actionSave.triggered.connect(
            lambda _: self.save_scene(self.scenePath)
        )  # throw away checked flag
        self.gui.actionSaveAs.triggered.connect(
            lambda _: self.save_scene()
        )  # throw away checked flag

        # Set up theme toggle
        self.gui.themeChanged.connect(self.update_theme)

        fontFolder = resource_path("gui/fonts/")
        for fontFile in fontFolder.iterdir():
            if not fontFile.is_file():
                continue
            id = QFontDatabase.addApplicationFont(str(fontFile))
            print(QFontDatabase.applicationFontFamilies(id))

    # --- GETTER / SETTER --- #

    @staticmethod
    def get_instance() -> "JuniorsToolbox":
        if JuniorsToolbox.__singleton is None:
            return JuniorsToolbox()
        return JuniorsToolbox.__singleton

    @staticmethod
    def get_instance_window_size() -> QSize:
        return JuniorsToolbox.get_instance().gui.size()

    @staticmethod
    def get_instance_window() -> MainWindow:
        return JuniorsToolbox.get_instance().gui

    @property
    def scene(self) -> Optional[SMSScene]:
        manager = ToolboxManager.get_instance()
        return manager.get_scene()

    @property
    def scenePath(self) -> Optional[Path]:
        return self.manager.get_scene_path()

    @scenePath.setter
    def scenePath(self, path: Path):
        projectViewer = TabWidgetManager.get_tab(ProjectViewerWidget) # type: ignore
        projectViewer.scenePath = path
        self.manager.load_scene(path)
        self.update_elements(self.scene)

    # --- GUI --- #

    @staticmethod
    def get_config_path():
        versionStub = __version__.replace(".", "-")
        return get_program_folder(f"{__name__} v{versionStub}") / "program.cfg"

    @staticmethod
    def get_window_title():
        return f"Junior's Toolbox v{__version__}"

    # --- LOGIC --- #

    def load_scene(self, scene: Path) -> bool:
        """
        Load a scene into the GUI
        """
        self.scenePath = scene
        return self.scene is not None

    def load_program_config(self):
        """
        Load the program config for further use
        """
        if not self.get_config_path().exists():
            self.theme = MainWindow.Theme.LIGHT
            return

        self.manager.load_settings(self.get_config_path())

        settings = self.manager.get_settings()
        isDarkTheme = settings.is_dark_theme()
        isUpdating = settings.is_updates_enabled()

        self.theme = ToolboxSettings.Themes(int(isDarkTheme))

        self.construct_ui_from_config()

    def construct_ui_from_config(self):
        """
        Restructures the UI according to a config
        """
        config = self.settings

    def update_theme(self, theme: "MainWindow.Theme"):
        """
        Update the UI theme to the specified theme
        """
        #from qdarkstyle import load_stylesheet, load
        from juniors_toolbox.gui.qdarktheme import load_stylesheet, load_palette
        if theme == MainWindow.Theme.LIGHT:
            self.theme = MainWindow.Theme.LIGHT
            self.setStyleSheet(load_stylesheet("light"))
        else:
            self.theme = MainWindow.Theme.DARK
            self.setStyleSheet(load_stylesheet("dark"))

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

    def reset(self):
        self.scene = SMSScene()

    def is_docker_empty(self) -> bool:
        return len(self.__openTabs) == 0

    def set_central_status(self, empty: bool):
        if empty:
            center = QLabel()
            center.setText("No tabs open\n(Open tabs using the Window menu)")
            center.setEnabled(False)
            center.setAlignment(Qt.AlignCenter)
        else:
            center = QWidget()
            center.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.gui.setCentralWidget(center)

    # -- SLOTS -- #

    @Slot(Path)
    def open_scene(self, path: Optional[Path] = None) -> bool:
        if path is None:
            dialog = QFileDialog(
                parent=self.gui,
                caption="Open Scene...",
                directory=str(
                    self.scenePath.parent if self.scenePath else Path.home()
                )
            )
            # filter="Gamecube Image (*.iso *.gcm);;All files (*)")

            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setFileMode(QFileDialog.Directory)

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
        self.scenePath = path
        return True

    @Slot(str)
    def openDockerTab(self, name: str):
        tab = TabWidgetManager.get_tab_n(name)
        if name in self.__openTabs or tab is None:
            return
        deTab = self.__tabs.setdefault(name, tab)
        deTab.setObjectName(name)
        # deTab.setWidget(tab)
        deTab.setFloating(len(self.__openTabs) > 0)
        deTab.setAllowedAreas(Qt.AllDockWidgetAreas)
            
        areas = [Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea]
        self.gui.addDockWidget(areas[len(self.__openTabs) % 2], deTab)

        deTab.setParent(self.gui)
        deTab.topLevelChanged.connect(
            lambda _: self.set_central_status(self.is_docker_empty()))
        deTab.closed.connect(self.closeDockerTab)

        deTab.show()
        self.__openTabs[name] = deTab

        self.set_central_status(self.is_docker_empty())

    @Slot(str)
    def closeDockerTab(self, tab: A_DockingInterface):
        if tab.windowTitle() not in self.__openTabs:
            return
        # tab.setWidget(None)
        tab.setParent(None)
        self.gui.removeDockWidget(tab)

        self.__openTabs.pop(tab.windowTitle())
        self.set_central_status(self.is_docker_empty())
