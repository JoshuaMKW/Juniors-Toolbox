import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from PySide6.QtCore import QPoint, QSize, Slot, QModelIndex, QAbstractListModel, QAbstractItemModel
from PySide6.QtGui import QResizeEvent, Qt, QFontDatabase

from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QSizePolicy, QStyleFactory, QWidget
from juniors_toolbox import __version__
from juniors_toolbox.gui.settings import ToolboxSettings
from juniors_toolbox.gui.tabs import TabWidgetManager
from juniors_toolbox.gui.tabs.hierarchyviewer import NameRefHierarchyTreeWidgetItem, NameRefHierarchyWidget
from juniors_toolbox.gui.tabs.projectviewer import ProjectViewerWidget
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.tabs.rail import RailViewerWidget
from juniors_toolbox.gui.templates import ToolboxTemplates
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

    def __new__(cls, *args: VariadicArgs, **kwargs: VariadicKwargs) -> "JuniorsToolbox":
        if JuniorsToolbox.__singleton is not None:
            return JuniorsToolbox.__singleton
        return super().__new__(cls, *args, **kwargs)

    def __init__(self):
        if JuniorsToolbox.__singleton is not None:
            return

        super().__init__()

        JuniorsToolbox.__singleton = self

        # Force Windows Taskbar Icon
        if sys.platform in {"win32", "cygwin", "msys"}:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                self.get_window_title())

        self.gui = MainWindow()
        self.manager = ToolboxManager()
        self.templates = ToolboxTemplates()
        TabWidgetManager.init()

        self.__openTabs: Dict[str, A_DockingInterface] = {}
        self.__tabs: Dict[str, A_DockingInterface] = {}

        self.gui.setWindowTitle(self.get_window_title())
        self.update_theme(MainWindow.Theme.LIGHT)

        # Set up tab spawning
        self.gui.tabActionRequested.connect(self.openDockerTab)
        self.gui.themeChanged.connect(self.update_theme)

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

        fontFolder = resource_path("gui/fonts/")
        for fontFile in fontFolder.iterdir():
            if not fontFile.is_file():
                continue
            id = QFontDatabase.addApplicationFont(str(fontFile))

        self.__init_tabs()

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
        self.manager.reset_scene()

    def is_docker_empty(self) -> bool:
        return all(tab.isHidden() for tab in TabWidgetManager.iter_tabs())

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
        if tab is None:
            return
        tab.show()
        self.set_central_status(self.is_docker_empty())

    @Slot(str)
    def closeDockerTab(self, tab: A_DockingInterface):
        tab.hide()
        self.set_central_status(self.is_docker_empty())

    def __init_objects(self):
        nameRefTab = TabWidgetManager.get_tab(NameRefHierarchyWidget)
        nameRefTab.treeWidget.itemCreated.connect(self.__add_nameref)
        nameRefTab.treeWidget.itemDeleted.connect(self.__remove_nameref)

    def __init_rails(self):
        railTab = TabWidgetManager.get_tab(RailViewerWidget)
        railTab.railList.model().rowsInserted.connect(self.__add_rails)
        railTab.railList.model().rowsRemoved.connect(self.__remove_rails)

    def __init_tabs(self):
        areas = [Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea]
        for i, tab in enumerate(TabWidgetManager.iter_tabs()):
            tab.setObjectName(tab.windowTitle())
            tab.setFloating(not self.is_docker_empty())
            tab.setAllowedAreas(Qt.AllDockWidgetAreas)
            tab.topLevelChanged.connect(lambda _: self.set_central_status(self.is_docker_empty()))
            tab.closed.connect(self.closeDockerTab)
            self.gui.addDockWidget(areas[len(self.__openTabs) % 2], tab)
            tab.setParent(self.gui)

        settings = ToolboxSettings.get_instance()
        settings.load()
        self.set_central_status(self.is_docker_empty())
        
        self.__init_objects()
        self.__init_rails()

        return True

    @Slot(QModelIndex, int, int)
    def __add_rails(self, parent: QModelIndex, first: int, last: int):
        scene = self.manager.get_scene()
        if scene is None:
            return

        railTab = TabWidgetManager.get_tab(RailViewerWidget)
        if railTab is None:
            return

        model = railTab.railList.model()
        for i in range(first, last + 1):
            scene.set_rail_by_index(i, model.item(i, 0).data())

    @Slot(QModelIndex, int, int)
    def __remove_rails(self, parent: QModelIndex, first: int, last: int):
        scene = self.manager.get_scene()
        if scene is None:
            return

        railTab = TabWidgetManager.get_tab(RailViewerWidget)
        if railTab is None:
            return

        model = railTab.railList.model()
        for i in range(first, last + 1):
            scene.remove_rail(model.item(i, 0).data(Qt.DisplayRole))

    @Slot(NameRefHierarchyTreeWidgetItem, int)
    def __add_nameref(self, item: NameRefHierarchyTreeWidgetItem, index: int):
        scene = self.manager.get_scene()
        if scene is None:
            return

        ...

    @Slot(NameRefHierarchyTreeWidgetItem, int)
    def __remove_nameref(self, item: NameRefHierarchyTreeWidgetItem, index: int):
        scene = self.manager.get_scene()
        if scene is None:
            return

        obj = item.object
        parent = obj.get_parent()
        if parent is None:
            scene._objects.remove(obj)
        else:
            parent.remove_from_group(obj)

    # @Slot(str)
    # def openDockerTab(self, name: str):
    #     tab = TabWidgetManager.get_tab_n(name)
    #     if name in self.__openTabs or tab is None:
    #         return
    #     deTab = self.__tabs.setdefault(name, tab)
    #     deTab.setObjectName(name)
    #     # deTab.setWidget(tab)
    #     deTab.setFloating(len(self.__openTabs) > 0)
    #     deTab.setAllowedAreas(Qt.AllDockWidgetAreas)
            
    #     areas = [Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea]
    #     self.gui.addDockWidget(areas[len(self.__openTabs) % 2], deTab)

    #     deTab.setParent(self.gui)
    #     deTab.topLevelChanged.connect(
    #         lambda _: self.set_central_status(self.is_docker_empty()))
    #     deTab.closed.connect(self.closeDockerTab)

    #     deTab.show()
    #     self.__openTabs[name] = deTab

    #     self.set_central_status(self.is_docker_empty())
