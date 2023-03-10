from dataclasses import dataclass
from enum import IntEnum
from typing import List

import glm
from juniors_toolbox.utils.types import Vec3f


class MatrixType(IntEnum):
    STANDARD = 0
    BILLBOARD = 1
    BILLBOARDY = 2
    

class JointData():
    @dataclass
    class Display:
        material: int = 0
        shape: int = 0

    def __init__(self, name: str = "root"):
        self.name = name
        self.flag = 1
        self.bbMtxType = MatrixType.STANDARD
        self.scale = Vec3f.one
        self.rotate = Vec3f.zero
        self.translate = Vec3f.zero
        self.parentID = -1
        self.children: list[int] = []
        self.displays: list[JointData.Display] = []
        self.inverseBinPoseMtx = glm.mtx4x4()
