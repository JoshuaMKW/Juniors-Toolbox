from __future__ import annotations

from pathlib import Path
from typing import Optional
from juniors_toolbox.gui.settings import ToolboxSettings
from juniors_toolbox.scene import SMSScene

from PySide6.QtCore import Signal, QObject

class ToolboxManager(QObject):
    __singleton: Optional["ToolboxManager"] = None

    sceneLoaded = Signal(Path)
    sceneReset = Signal(Path)
    sceneCleared = Signal()
    
    def __new__(cls: type["ToolboxManager"]) -> "ToolboxManager":
        if ToolboxManager.__singleton is not None:
            return ToolboxManager.__singleton
        return super(ToolboxManager, cls).__new__(cls)

    def __init__(self) -> None:
        if ToolboxManager.__singleton is not None:
            return
            
        super().__init__()

        self.__scene: SMSScene | None = None
        self.__scenePath: Optional[Path] = None
        self.__settings: ToolboxSettings = ToolboxSettings()

        ToolboxManager.__singleton = self

    @staticmethod
    def get_instance() -> "ToolboxManager":
        if ToolboxManager.__singleton is None:
            return ToolboxManager()
        return ToolboxManager.__singleton

    def get_scene(self) -> Optional[SMSScene]:
        return self.__scene

    def get_scene_path(self) -> Optional[Path]:
        return self.__scenePath
        
    def load_scene(self, path: Path) -> Optional[SMSScene]:
        scene = SMSScene.from_path(path)
        self.__scene = scene
        self.__scenePath = path
        self.sceneLoaded.emit(path) # type: ignore
        return scene

    def clear_scene(self) -> None:
        self.__scene = None
        self.__scenePath = None
        self.sceneCleared.emit() # type: ignore

    def reset_scene(self) -> None:
        self.__scene = SMSScene()
        self.sceneReset.emit(self.__scenePath) # type: ignore
    
    def get_settings(self) -> ToolboxSettings:
        return self.__settings

    def load_settings(self, path: Path) -> bool:
        return self.__settings.load(path)
    
    def save_settings(self, path: Path) -> None:
        self.__settings.save(path)