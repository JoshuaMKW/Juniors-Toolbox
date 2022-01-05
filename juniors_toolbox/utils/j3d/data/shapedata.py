from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import List, Tuple

from juniors_toolbox.utils.types import  Vec3f

class ShapeData():
    class Mode(IntEnum):
        NORMAL = 0
        BILLBOARD_XY = auto()
        BILLBOARD_Y = auto()
        SKINNED = auto()
        MAX = auto()

    def __init__(self, id: int, mode: Mode = Mode.NORMAL, boundRadius: float = 100000.0):
        self.id = id
        self.mode = mode
        self.boundRadius = boundRadius
        
    @property
    def boundingBox(self) -> Tuple[Vec3f, Vec3f]:
        return Vec3f.one * -self.boundRadius, Vec3f.one * self.boundRadius