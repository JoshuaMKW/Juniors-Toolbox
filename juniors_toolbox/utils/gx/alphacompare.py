from enum import IntEnum, auto
from dataclasses import dataclass
from juniors_toolbox.utils.gx import Comparison

class AlphaOp(IntEnum):
    AND = 0
    OR = auto()
    XOR = auto()
    XNOR = auto()

@dataclass
class AlphaComparison:
    compLeft = Comparison.ALWAYS
    refLeft = 0
    op = AlphaOp.AND
    compRight = Comparison.ALWAYS
    refRight = 0