from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Union
from PySide6.QtWidgets import QGridLayout, QMainWindow, QWidget
from juniors_toolbox.gui.tabs.prmeditor import PrmEditorWidget
from juniors_toolbox.gui.tabs.projectviewer import ProjectViewerWidget
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.gui.tabs.renderer import SceneRendererWidget
from juniors_toolbox.gui.tabs.object import ObjectHierarchyWidget, ObjectPropertiesWidget
from juniors_toolbox.gui.tabs.rail import RailViewerWidget
from juniors_toolbox.gui.tabs.bmgeditor import BMGMessageEditor
from juniors_toolbox.gui.tabs.propertyviewer import SelectedPropertiesWidget
from juniors_toolbox.gui.widgets.synceddock import SyncedDockWidget


class GenericTabWidget():
    def populate(self, data: Any, scenePath: Path): ...

    def __del__(self): ...


class TabWidgetManager():
    _STR_TO_TYPE = {
        "Project Viewer": ProjectViewerWidget,
        "Scene Hierarchy": ObjectHierarchyWidget,
        "Selected Properties": SelectedPropertiesWidget,
        "Rail List": RailViewerWidget,
        "Rail Editor": None,
        "BMG Editor": BMGMessageEditor,
        "PRM Editor": PrmEditorWidget,
        "Demo Editor": None,
        "Data Viewer": None,
        "Scene Renderer": SceneRendererWidget
    }

    _TAB_WIDGETS: Dict[type, QWidget] = {
        _STR_TO_TYPE["Project Viewer"]: _STR_TO_TYPE["Project Viewer"](),
        _STR_TO_TYPE["Scene Hierarchy"]: _STR_TO_TYPE["Scene Hierarchy"](),
        _STR_TO_TYPE["Selected Properties"]: _STR_TO_TYPE["Selected Properties"](),
        _STR_TO_TYPE["Rail List"]: _STR_TO_TYPE["Rail List"](),
        _STR_TO_TYPE["Rail Editor"]: _STR_TO_TYPE["Rail Editor"](),
        _STR_TO_TYPE["BMG Editor"]: _STR_TO_TYPE["BMG Editor"](),
        _STR_TO_TYPE["PRM Editor"]: _STR_TO_TYPE["PRM Editor"](),
        _STR_TO_TYPE["Demo Editor"]: _STR_TO_TYPE["Demo Editor"](),
        _STR_TO_TYPE["Data Viewer"]: _STR_TO_TYPE["Data Viewer"](),
        _STR_TO_TYPE["Scene Renderer"]: _STR_TO_TYPE["Scene Renderer"]()
    }

    @staticmethod
    def init():
        for tab in TabWidgetManager.iter_tabs():
            tab.setVisible(False)

    @staticmethod
    def get_tab(key: Union[str, type]) -> Union[QWidget, GenericTabWidget]:
        if isinstance(key, str):
            key = TabWidgetManager._STR_TO_TYPE[key]
        if key in TabWidgetManager._TAB_WIDGETS:
            return TabWidgetManager._TAB_WIDGETS[key]
        return None

    @staticmethod
    def iter_tabs(open: bool = False) -> Iterable[Union[QWidget, GenericTabWidget]]:
        for tab in TabWidgetManager._TAB_WIDGETS.values():
            if tab is None:
                continue
            if open is False or tab.isVisible():
                yield tab

    @staticmethod
    def is_tab_open(key: Union[str, type]) -> bool:
        tab = TabWidgetManager.get_tab(key)
        return False if tab is None else tab.isVisible()
