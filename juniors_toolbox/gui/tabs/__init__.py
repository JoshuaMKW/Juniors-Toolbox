from typing import Dict, Iterable, Optional, TypeVar
from juniors_toolbox.gui.tabs.hierarchyviewer import NameRefHierarchyWidget
from juniors_toolbox.gui.tabs.prmeditor import PrmEditorWidget
from juniors_toolbox.gui.tabs.projectviewer import ProjectViewerWidget
from juniors_toolbox.gui.tabs.renderer import SceneRendererWidget
from juniors_toolbox.gui.tabs.rail import RailViewerWidget
from juniors_toolbox.gui.tabs.bmgeditor import BMGMessageEditor
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface

T = TypeVar("T", bound=A_DockingInterface)

class TabWidgetManager():
    _STR_TO_TYPE = {
        "Project Viewer": ProjectViewerWidget,
        "Scene Hierarchy": NameRefHierarchyWidget,
        "Selected Properties": SelectedPropertiesWidget,
        "Rail List": RailViewerWidget,
        "Rail Editor": None,
        "BMG Editor": BMGMessageEditor,
        "PRM Editor": PrmEditorWidget,
        "Demo Editor": None,
        "Data Viewer": None,
        "Scene Renderer": SceneRendererWidget
    }

    _TAB_WIDGETS: Dict[type, Optional[A_DockingInterface]] = {}

    @staticmethod
    def init():
        for name, tab in TabWidgetManager._STR_TO_TYPE.items():
            if tab is None:
                continue
            TabWidgetManager._TAB_WIDGETS[tab] = tab(name)

        for tab in TabWidgetManager.iter_tabs():
            tab.setVisible(False)

    @staticmethod
    def get_tab(key: type[T]) -> Optional[T]:
        if key in TabWidgetManager._TAB_WIDGETS:
            return TabWidgetManager._TAB_WIDGETS[key]
        return None

    @staticmethod
    def get_tab_n(key: str) -> Optional[A_DockingInterface]:
        _key = TabWidgetManager._STR_TO_TYPE[key]
        if _key in TabWidgetManager._TAB_WIDGETS:
            return TabWidgetManager._TAB_WIDGETS[_key]
        return None

    @staticmethod
    def iter_tabs(open: bool = False) -> Iterable[A_DockingInterface]:
        for tab in TabWidgetManager._TAB_WIDGETS.values():
            if tab is None:
                continue
            if open is False or tab.isVisible():
                yield tab

    @staticmethod
    def is_tab_open(key: type[T]) -> bool:
        tab = TabWidgetManager.get_tab(key)
        return False if tab is None else tab.isVisible()

    @staticmethod
    def is_tab_open_n(key: str) -> bool:
        tab = TabWidgetManager.get_tab_n(key)
        return False if tab is None else tab.isVisible()
