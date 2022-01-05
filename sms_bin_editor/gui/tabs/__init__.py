from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Union
from PySide2.QtWidgets import QGridLayout, QMainWindow, QWidget
from build.lib.sms_bin_editor.scene import SMSScene
from sms_bin_editor.gui.tabs.renderer import SceneRendererWidget
from sms_bin_editor.gui.tabs.object import ObjectHierarchyWidget, ObjectPropertiesWidget
from sms_bin_editor.gui.tabs.rail import RailListWidget
from sms_bin_editor.gui.tabs.generic import GenericTabWidget
from sms_bin_editor.gui.widgets.synceddock import QDockWidget


class TabWidgetManager():
    _STR_TO_TYPE = {
        "Object Hierarchy": ObjectHierarchyWidget,
        "Object Properties": ObjectPropertiesWidget,
        "Rail List": RailListWidget,
        "Rail Editor": None,
        "BMG Editor": None,
        "PRM Editor": None,
        "Demo Editor": None,
        "Data Viewer": None,
        "Scene Renderer": SceneRendererWidget
    }

    _TAB_WIDGETS: Dict[type, QWidget] = None

    @staticmethod
    def init(parent: QMainWindow = None):
        TabWidgetManager._TAB_WIDGETS = {
            ObjectHierarchyWidget: ObjectHierarchyWidget(parent),
            ObjectPropertiesWidget: ObjectPropertiesWidget(parent),
            RailListWidget: RailListWidget(parent),
            "Rail Editor": None,
            "BMG Editor": None,
            "PRM Editor": None,
            "Demo Editor": None,
            "Data Viewer": None,
            SceneRendererWidget: SceneRendererWidget(parent)
        }
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

    @staticmethod
    def is_tab_nested(key: Union[str, type]) -> bool:
        """
        Return if the tab is nested in a parent space
        """
        tab = TabWidgetManager.get_tab(key)
        if isinstance(tab.parent(), QDockWidget.DetachedTab):
            return False
        return True
    