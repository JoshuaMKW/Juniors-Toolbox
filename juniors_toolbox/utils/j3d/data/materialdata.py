from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import List

from juniors_toolbox.utils.types import RGBA8, BasicColors, Vec3f


class MatrixType(IntEnum):
    STANDARD = 0
    BILLBOARD = 1
    BILLBOARDY = 2
    

@dataclass
class Fog:
    class Type(IntEnum):
        NONE = 0
        PERSPECTIVE_LINEAR = auto()
        PERSPECTIVE_EXPONENTIAL = auto()
        PERSPECTIVE_QUADRATIC = auto()
        PERSPECTIVE_INVERSE_EXPONENTIAL = auto()
        PERSPECTIVE_INVERSE_QUADRATIC = auto()
        ORTHOGRAPHIC_LINEAR = auto()
        ORTHOGRAPHIC_EXPONENTIAL = auto()
        ORTHOGRAPHIC_QUADRATIC = auto()
        ORTHOGRAPHIC_INVERSE_EXPONENTIAL = auto()
        ORTHOGRAPHIC_INVERSE_QUADRATIC = auto()

    center: int
    type: Type = Type.NONE
    enabled: bool = False
    startZ: float = 0.0
    endZ: float = 0.0
    nearZ: float = 0.0
    farZ: float = 0.0
    color: RGBA8 = RGBA8(BasicColors.WHITE)
    inverseBinPoseMtx: List[int] = field(default_factory=lambda: [])

@dataclass
class NBTScale:
    enable: bool = False
    scale: Vec3f = Vec3f.zero


