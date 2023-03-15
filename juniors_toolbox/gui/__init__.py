from __future__ import annotations

from pathlib import Path
import sys
import time
import traceback
from typing import BinaryIO, Callable, Optional, Type
from juniors_toolbox.gui.settings import ToolboxSettings
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import A_Serializable
from juniors_toolbox.utils.filesystem import resource_path

from PySide6.QtCore import Signal, Slot, QObject, QRunnable, QSettings, QThread


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class RunnableWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Return the result of the processing
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()  # Done


class ThreadWorker(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def process(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.result.emit(result)  # Return the result of the processing
        finally:
            self.finished.emit()  # Done

    def moveToThread(self, thread: QThread) -> None:
        super().moveToThread(thread)
        thread.started.connect(self.process)
        self.finished.connect(thread.quit)
        self.finished.connect(self.deleteLater)


class RunnableSerializer(RunnableWorker):
    def __init__(self, serializable: A_Serializable) -> None:
        super().__init__(serializable.to_bytes)


class RunnableDeserializer(RunnableWorker):
    def __init__(self, serializable: A_Serializable) -> None:
        super().__init__(serializable.from_bytes)


class ThreadSerializer(ThreadWorker):
    def __init__(self, serializable: A_Serializable) -> None:
        super().__init__(serializable.to_bytes)


class ThreadDeserializer(ThreadWorker):
    def __init__(self, serializable: A_Serializable) -> None:
        super().__init__(serializable.from_bytes)


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
        self.sceneLoaded.emit(path)  # type: ignore
        return scene

    def save_scene(self, path: Path) -> bool:
        if self.__scene is None:
            return False
        successful = self.__scene.save_objects(path / "map/scene.bin")
        return successful

    def clear_scene(self) -> None:
        self.__scene = None
        self.__scenePath = None
        self.sceneCleared.emit()  # type: ignore

    def reset_scene(self) -> None:
        self.__scene = SMSScene()
        self.sceneReset.emit(self.__scenePath)  # type: ignore

    def get_settings(self) -> ToolboxSettings:
        return self.__settings

    def load_settings(self, settings: Optional[QSettings] = None) -> bool:
        return self.__settings.load(settings)

    def save_settings(self, path: Path) -> None:
        self.__settings.save()

    def get_template_folder(self) -> Path:
        return resource_path("Templates")
