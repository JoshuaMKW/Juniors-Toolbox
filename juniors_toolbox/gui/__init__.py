from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Callable, Optional, Type
from juniors_toolbox.gui.settings import ToolboxSettings
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import A_Serializable
from juniors_toolbox.utils.filesystem import resource_path

from PySide6.QtCore import Signal, QObject, QRunnable, QSettings


class Runnable(QObject, QRunnable):
    finished = Signal(object)
    
    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        ret = self.fn(*self.args, **self.kwargs)
        self.finished.emit(ret)


class Serializer(QObject, QRunnable):
    finished = Signal(bytes)

    def __init__(self, serializable: A_Serializable, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._serializable = serializable
    
    def run(self) -> None:
        data = self._serializable.to_bytes()
        self.finished.emit(data)
        

class Deserializer(QObject, QRunnable):
    finished = Signal(A_Serializable)

    def __init__(self, cls: Type[A_Serializable], data: BinaryIO) -> None:
        super().__init__()
        self._cls = cls
        self._data = data
    
    def run(self) -> None:
        obj = self._cls.from_bytes(self._data)
        self.finished.emit(obj)


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

    def load_settings(self, settings: Optional[QSettings] = None) -> bool:
        return self.__settings.load(settings)
    
    def save_settings(self, path: Path) -> None:
        self.__settings.save()

    def get_template_folder(self) -> Path:
        return resource_path("Templates")