
from json import load as json_load, dump as json_dump
from pickle import load as pickle_load, dump as pickle_dump
from enum import Enum, IntEnum
from pathlib import Path
from typing import IO, Callable, Optional

from juniors_toolbox.gui.widgets.synceddock import QDockWidget


class SMSBinEditorSettings():
    """
    Program settings and GUI layout information
    """

    class Themes(IntEnum):
        LIGHT = 0
        DARK = 1

    def __init__(self, settings: Optional[dict] = None):
        if settings is None:
            settings = {}

        self.settings = settings

    def is_dark_theme(self) -> bool:
        return self.settings["Theme"] == self.Themes.DARK

    def set_theme(self, theme: Themes):
        self.settings["Theme"] = theme

    def is_updates_enabled(self) -> bool:
        return self.settings["Update"]

    def set_updates_enabled(self, enabled: bool):
        self.settings["Update"] = enabled

    def is_widget_enabled(self, widget: QDockWidget) -> bool:
        widgetName = widget.objectName()
        if widgetName not in self.settings["Layout"]:
            return False

        widgetLayout = self.settings["Layout"][widgetName]
        return widgetLayout["Enabled"]

    def set_widget_enabled(self, widget: QDockWidget, enabled: bool):
        widgetName = widget.objectName()
        if widgetName not in self.settings["Layout"]:
            return

        widgetLayout = self.settings["Layout"][widgetName]
        widgetLayout["Enabled"] = enabled

    def get_widget_placement(self, widget: QDockWidget) -> dict:
        widgetName = widget.objectName()
        if widgetName not in self.settings["Layout"]:
            return False

        widgetLayout = self.settings["Layout"][widgetName]
        return widgetLayout["Placement"]

    def set_widget_placement(self, widget: QDockWidget):
        ...

    def save(self, config: Path, dump: Callable[[dict, IO], None] = json_dump):
        config.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if dump == json_dump else "wb"
        with config.open(mode) as f:
            dump(self.settings, f)
        return True

    def load(self, config: Path, load: Callable[[dict, IO], None] = json_load) -> bool:
        if not config.is_file():
            return False
        mode = "r" if load == json_load else "rb"
        with config.open(mode) as f:
            self.settings = load(f)
        return True