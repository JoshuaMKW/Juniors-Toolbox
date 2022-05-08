from enum import Enum, IntEnum, auto
from math import pi
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtGui import QCursor

import numpy
from dataclasses import dataclass
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QSizePolicy, QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from pyrr import Vector3, Vector4, Matrix33, Matrix44
from juniors_toolbox.utils.gx.color import ColorF32, Color
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.utils.types import Transform, Vec2f, Vec3f
from juniors_toolbox.objects.object import MapObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.filesystem import resource_path
from juniors_toolbox.utils.j3d.bmd import BMD
from juniors_toolbox.utils.j3d.anim.bck import BCK
from juniors_toolbox.utils.j3d.anim.btk import BTK


class Shader():
    """
    Represents an OpenGL shader with easy access functions
    """

    def __init__(self, vertexShader: str, fragmentShader: str, geometryShader: Optional[str] = None):
        vertex = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vertex, vertexShader)
        glCompileShader(vertex)
        self.__check_compile_errors(vertex, "VERTEX")

        fragment = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fragment, fragmentShader)
        glCompileShader(fragment)
        self.__check_compile_errors(fragment, "FRAGMENT")

        if geometryShader is not None:
            geometry = glCreateShader(GL_GEOMETRY_SHADER)
            glShaderSource(geometry, geometryShader)
            glCompileShader(geometry)
            self.__check_compile_errors(geometry, "GEOMETRY")

        self.__id = glCreateProgram()
        glAttachShader(self.__id, vertex)
        glAttachShader(self.__id, fragment)
        if geometryShader is not None:
            glAttachShader(self.__id, geometry)
        glLinkProgram(self.__id)
        self.__check_compile_errors(self.__id, "PROGRAM")

        glDeleteShader(vertex)
        glDeleteShader(fragment)
        if geometryShader is not None:
            glDeleteShader(geometry)

    @property
    def id(self) -> int:
        return self.__id

    def use(self):
        glUseProgram(self.id)

    def setBool(self, name: str, value: bool):
        glUniform1i(glGetUniformLocation(self.__id, name), value)

    def setInt(self, name: str, value: int):
        glUniform1i(glGetUniformLocation(self.__id, name), value)

    def setFloat(self, name: str, value: float):
        glUniform1f(glGetUniformLocation(self.__id, name), value)

    def setVec2(self, name: str, value: Vec2f):
        glUniform2fv(glGetUniformLocation(
            self.__id, name), 1, value.x, value.y)

    def setVec2f(self, name: str, x: float, y: float):
        glUniform2f(glGetUniformLocation(self.__id, name), x, y)

    def setVec3(self, name: str, value: Vec3f):
        glUniform3fv(glGetUniformLocation(self.__id, name),
                     1, value.x, value.y, value.z)

    def setVec3f(self, name: str, x: float, y: float, z: float):
        glUniform3f(glGetUniformLocation(self.__id, name), x, y, z)

    def setVec4(self, name: str, value: Vector4):
        glUniform4fv(glGetUniformLocation(self.__id, name), 1, value)

    def setVec4f(self, name: str, x: float, y: float, z: float, w: float):
        glUniform4f(glGetUniformLocation(self.__id, name), x, y, z, w)

    def setMat3(self, name: str, mat: Matrix33):
        glUniformMatrix3fv(glGetUniformLocation(
            self.__id, name), 1, GL_FALSE, mat)

    def setMat4(self, name: str, mat: Matrix44):
        glUniformMatrix4fv(glGetUniformLocation(
            self.__id, name), 1, GL_FALSE, mat)

    def __check_compile_errors(self, shader: int, _type: str):
        if _type != "PROGRAM":
            if not glGetShaderiv(shader, GL_COMPILE_STATUS):
                raise RuntimeError(
                    str(glGetShaderInfoLog(shader), encoding="ascii"))
        else:
            if not glGetProgramiv(shader, GL_LINK_STATUS):
                raise RuntimeError(
                    str(glGetProgramInfoLog(shader), encoding="ascii"))


@dataclass
class SpotLight():
    color: ColorF32
    position: Vec3f
    direction: Vec3f
    cosattn: Vec3f
    distattn: Vec3f

    @classmethod
    def from_light_obj(cls, light: MapObject) -> "SpotLight":
        pos: Vec3f = light.get_value("Position")

        splight = cls(
            light.get_value("Color"),
            pos,
            pos.normalized,

        )


class Gizmo(Transform):
    class Mode(IntEnum):
        POSITION = 0
        ROTATION = auto()
        SCALE = auto()

    def __init__(self):
        super().__init__()
        self.__mode = Gizmo.Mode.POSITION

    def get_mode(self) -> Mode:
        return self.__mode

    def set_mode(self, mode: Mode):
        self.__mode = mode

    def render(self):
        ...

    def apply_to_matrix(self, mtx: Matrix44):
        ...


class SceneCamera():
    class RenderStyle(IntEnum):
        POLY = 1
        WIRE = 1 << 1
        COL = 1 << 2
        TEX = 1 << 3

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

        self.renderWidth = 640.0
        self.renderHeight = self.renderWidth * 0.5625

        self._camMatrix = Matrix44.identity()
        self._skyMatrix = Matrix44.identity()
        self._orthoGraphic = False
        self._orthoZoom = 1.0

        self._renderStyle = SceneCamera.RenderStyle.POLY | SceneCamera.RenderStyle.TEX

    def get_render_style(self) -> RenderStyle:
        return self._renderStyle

    def set_render_style(self, style: RenderStyle):
        self._renderStyle = style

    def is_orthographic(self) -> bool:
        return self._orthoGraphic

    def set_orthographic(self, ortho: bool):
        self._orthoGraphic = ortho

    def get_view_matrix(self) -> Matrix44:
        return Matrix44.look_at(
            self.transform.translation,
            self.transform.translation + self.transform.forward,
            self.transform.up
        )

    def get_projection_matrix(self) -> Matrix44:
        if self._orthoGraphic:
            return Matrix44.orthogonal_projection(
                0,
                self.renderWidth,
                0,
                self.renderHeight,
                self.zNearOrtho,
                self.zFarOrtho
            )
        else:
            return Matrix44.perspective_projection(
                self.fov,
                self.renderWidth / self.renderHeight,
                self.zNear,
                self.zFar
            )

    def get_sky_matrix(self) -> Matrix44:
        return self._skyMatrix

    def apply_render_settings(self):
        ...

    def render_scene(
        self,
        models: Dict[str, BMD],
        lights: Dict[str, SpotLight],
        ambLights: Dict[str, ColorF32]
    ):
        """
        Render a scene given a dictionary of models, lights, andf ambient lights
        """
        return
        for model in models.values():
            model.render(lights, ambLights, self._renderStyle)


class SceneRendererWidget(A_DockingInterface):
    MAP_FILE = "map.bmd"
    SKY_FILE = "sky.bmd"
    SEA_FILE = "sea.bmd"
    SKYTEX_FILE = "sky.bmt"
    SKYANIM_FILE = "sky.btk"
    SEAANIM_FILE = "sea.btk"
    WAVEIMG_FILE = "wave.bti"

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.setObjectName(self.__class__.__name__)

        self.openGLView = QOpenGLWidget()
        self.openGLView.setMinimumSize(640, 480)
        self.setWidget(self.openGLView)
        #self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.reset_shaders()

        self.camera = SceneCamera(
            fov=(70 * pi) / 180,
            zNear=10.0,
            zFar=50000.0
        )

        self.mapAssetsPath: Path = None
        self.mapBMD: BMD = None
        self.skyBMD: BMD = None
        self.seaBMD: BMD = None
        self.objectBMDList: Dict[str, BMD] = {}
        self.lights: Dict[str, SpotLight] = {}
        self.ambLights: Dict[str, ColorF32] = {}

        self.lightingShader = None

        self._selectedBMD = None

    def populate(self, data: SMSScene, scenePath: Path):
        return
        self.mapAssetsPath = scenePath / "map/map"

        self.mapBMD = self.init_bmd(self.MAP_FILE)
        self.skyBMD = self.init_bmd(self.SKY_FILE, self.SKYTEX_FILE)
        with (self.mapAssetsPath / self.SKYANIM_FILE).open("rb") as f:
            self.skyBMD.add_anim(BTK.from_data(f))
        self.seaBMD = self.init_bmd(self.SEA_FILE)
        with (self.mapAssetsPath / self.SEAANIM_FILE).open("rb") as f:
            self.seaBMD.add_anim(BTK.from_data(f))
        self.objectBMDList: Dict[str, BMD] = {
            "Map": self.mapBMD,
            "Sky": self.skyBMD,
            "Sea": self.seaBMD
        }
        self.lights: Dict[str, SpotLight] = {}
        self.ambLights: Dict[str, ColorF32] = {}

        self._selectedBMD = None

        for obj in data.iter_objects(True):
            ...

    @property
    def vertexShader(self) -> str:
        return self._vertexShader

    @vertexShader.setter
    def vertexShader(self, shader: str):
        self._vertexShader = shader

    @property
    def fragmentShader(self) -> str:
        return self._fragmentShader

    @fragmentShader.setter
    def fragmentShader(self, shader: str):
        self._fragmentShader = shader

    def add_light(self, light: MapObject):
        if light.name == "AmbColor":
            color: Color = light.get_value("Color")
            self.ambLights[light.get_explicit_name(
            )] = ColorF32(
                color.red / 255,
                color.green / 255,
                color.blue / 255,
                color.alpha / 255
            )
        elif light.name == "Light":
            self.lights[light.get_explicit_name(
            )] = SpotLight.from_light_obj(light)

    def init_bmd(self, bmdFile: str, bmtFile: Optional[str] = None) -> BMD:
        if bmtFile is not None:
            bmtFile = self.mapAssetsPath / bmtFile
        return BMD.from_path(self.mapAssetsPath / bmdFile, bmtFile)

    def reset_shaders(self):
        self._vertexShader = resource_path(
            "shaders/UnlitTexture.vert").read_text()
        self._fragmentShader = resource_path(
            "shaders/UnlitTexture.frag").read_text()

    def compile_shader_program(self) -> Shader:
        return Shader(self.vertexShader, self.fragmentShader)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT |
                GL_STENCIL_BUFFER_BIT)
        glLoadIdentity()

        # Set the projection matrix
        glLoadMatrixf(self.camera.get_projection_matrix())

        self.lightingShader.use()
        self.lightingShader.setVec3(
            "u_viewPos", self.camera.transform.translation)

        glMatrixMode(GL_MODELVIEW_MATRIX)

        self.camera.render_scene(
            self.objectBMDList,
            self.lights,
            self.ambLights
        )

        relPos = self.mapFromGlobal(QCursor().pos())
        print(relPos)

    def initializeGL(self):
        self.camera.transform.translation = Vec3f(0, 0, 0)
        self.lightingShader = self.compile_shader_program()
        self.lightingShader.use()
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w: int, h: int):
        ...
