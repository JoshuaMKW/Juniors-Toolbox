from dataclasses import dataclass
from enum import IntEnum, auto
from math import cos, pi, sin

from numpy import ndarray, array
from juniors_toolbox.utils.types import Vec2f


class IndTexFormat(IntEnum):
    _8BIT = 0
    _5BIT = auto()
    _4BIT = auto()
    _3BIT = auto()


class IndTexBiasSel(IntEnum):
    NONE = 0
    S = auto()
    T = auto()
    ST = auto()
    U = auto()
    SU = auto()
    TU = auto()
    STU = auto()


class IndTexAlphaSel(IntEnum):
    OFF = 0
    S = auto()
    T = auto()
    U = auto()


class IndTexMtxID(IntEnum):
    OFF = 0
    UNK_0 = auto()
    UNK_1 = auto()
    UNK_2 = auto()
    S0 = 5
    S1 = auto()
    S2 = auto()
    T0 = 9
    T1 = auto()
    T2 = auto()

class IndTexWrap(IntEnum):
    OFF = 0
    _256 = auto()
    _128 = auto()
    _64 = auto()
    _32 = auto()
    _16 = auto()
    _0 = auto()


@dataclass
class IndirectTextureScalePair:
    class Selection(IntEnum):
        X_1 = 0
        X_2 = auto()
        X_4 = auto()
        X_8 = auto()
        X_16 = auto()
        X_32 = auto()
        X_64 = auto()
        X_128 = auto()
        X_256 = auto()

    u: Selection = Selection.X_1
    v: Selection = Selection.X_1


@dataclass
class IndirectMatrix:
    scale: Vec2f = Vec2f(0.5, 0.5)
    rotate: float = 0.0
    translate: Vec2f = Vec2f.zero
    quant: int = 1

    def compute(self) -> ndarray:
        """
        Returns a 3x2 matrix as a numpy ndarray
        """
        theta = self.rotate / (180.0 * pi)
        sinR = sin(theta)
        cosR = cos(theta)
        center = 0.0

        mtx = array(
            [[0, 0, 0],
             [0, 0, 0]]
        )

        scaleX = self.scale[0]
        scaleY = self.scale[1]
        transX = self.translate[0]
        transY = self.translate[1]

        mtx[0][0] = scaleX * cosR
        mtx[1][0] = scaleX * -sinR
        mtx[2][0] = transX + center + scaleX*(sinR*center - cosR*center)
        
        mtx[0][1] = scaleY * sinR
        mtx[1][1] = scaleY * cosR
        mtx[2][1] = transY + center + -scaleY*(-sinR*center + cosR*center)

        return mtx


@dataclass
class IndirectSetting:
    texScale: IndirectTextureScalePair
    mtx: IndirectMatrix


@dataclass
class IndOrder:
    refMap: int = 0
    refCoord: int = 0
    