
from json import load as json_load, dump as json_dump
from pickle import load as pickle_load, dump as pickle_dump
from enum import Enum, IntEnum
from pathlib import Path
from typing import IO, Callable, Optional

from PySide6.QtCore import QSettings, QObject, QByteArray


class ToolboxSettings(QObject):
    """
    Program settings and GUI layout information
    """
    __singleton: Optional["ToolboxSettings"] = None

    class Themes(IntEnum):
        LIGHT = 0
        DARK = 1

    def __new__(cls: type["ToolboxSettings"]) -> "ToolboxSettings":
        if ToolboxSettings.__singleton is not None:
            return ToolboxSettings.__singleton
        return super(ToolboxSettings, cls).__new__(cls)

    def __init__(self, settings: Optional[QSettings] = None, parent: Optional[QObject] = None) -> None:
        if ToolboxSettings.__singleton is not None:
            return
            
        super().__init__(parent)
        self.load(settings)

        ToolboxSettings.__singleton = self

    @staticmethod
    def get_instance() -> "ToolboxSettings":
        if ToolboxSettings.__singleton is None:
            return ToolboxSettings()
        return ToolboxSettings.__singleton

    def is_dark_theme(self) -> bool:
        return self.settings.value("Settings/Theme", self.Themes.LIGHT) == self.Themes.DARK

    def set_theme(self, theme: Themes) -> None:
        self.settings.setValue("Settings/Theme", theme)

    def is_updates_enabled(self) -> bool:
        return bool(self.settings.value("Settings/Update", True))

    def set_updates_enabled(self, enabled: bool) -> None:
        self.settings.setValue("Settings/Update", enabled)

    def save(self) -> bool:
        from juniors_toolbox.gui.application import JuniorsToolbox
        window = JuniorsToolbox.get_instance_window()

        if window.actionDarkTheme.isChecked():
            self.set_theme(self.Themes.DARK)
        else:
            self.set_theme(self.Themes.LIGHT)
        self.settings.setValue("GUI/Geometry", window.saveGeometry())
        self.settings.setValue("GUI/State", window.saveState())
        return True

    def load(self, settings: Optional[QSettings] = None) -> bool:
        from juniors_toolbox.gui.application import JuniorsToolbox
        from juniors_toolbox.gui.tabs import TabWidgetManager
        window = JuniorsToolbox.get_instance_window()

        if settings is None:
            settings = QSettings("JoshuaMK", "Junior's Toolbox")
        self.settings = settings

        geometry = self.settings.value("GUI/Geometry", QByteArray(b""))
        state = self.settings.value("GUI/State", QByteArray(b""))
        window.restoreGeometry(geometry)
        window.restoreState(state)
        
        # Update tab checkboxes
        for action in window.tabWidgetActions.values():
            tab = TabWidgetManager.get_tab_n(action.text())
            if tab is None:
                continue
            if not tab.isHidden():
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)

        window.actionDarkTheme.blockSignals(True)
        window.actionDarkTheme.setChecked(self.is_dark_theme())
        window.actionDarkTheme.blockSignals(False)
        window.signal_theme(self.is_dark_theme())

        return True

    def reset(self):
        self.settings.clear()

    def clear_settings(self):
        self.settings.remove("Settings")