from math import pi
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QDialog, QOpenGLWidget
from pathlib import Path

import numpy

from sms_bin_editor.objects.types import Transform, Vec3f
from sms_bin_editor.scene import SMSScene

class SceneCamera():
    def __init__(
        self,
        fov: float,
        zNear: float = 0.01,
        zFar: float = 1000.0,
        zNearOrtho: float = -1.0,
        zFarOrtho: float = 100.0
    ):
        self.fov = fov
        self.zNear = zNear
        self.zFar = zFar
        self.zNearOrtho = zNearOrtho
        self.zFarOrtho = zFarOrtho
        self.transform = Transform()
        self.velocity = Vec3f()

        self._projMatrix = numpy.array(
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        )
        self._camMatrix = numpy.array(
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        )
        self._skyMatrix = numpy.array(
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        )
        self._orthoGraphic = False
        self._orthoZoom = 1.0


class SceneRenderer(QDialog):
    MAP_FILE = "map.bmd"
    SKY_FILE = "sky.bmd"
    SEA_FILE = "sea.bmd"
    SKYTEX_FILE = "sky.bmt"

    def __init__(self, mapPath: Path):
        self.mapAssetsPath = mapPath
        self.setObjectName(self.__class__.__name__)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.renderView = QOpenGLWidget(self)
        self.camera = SceneCamera(fov=(70 * pi) / 180)

    def event