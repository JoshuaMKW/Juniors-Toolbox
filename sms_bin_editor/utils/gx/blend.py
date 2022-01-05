from enum import IntEnum, auto
from dataclasses import dataclass

class BlendModeType(IntEnum):
    NONE = 0
    BLEND = auto()
    LOGIC = auto()
    SUBTRACT = auto()


class BlendModeFactor(IntEnum):
    ZERO = 0
    ONE = auto()
    SRC_C = auto()
    INV_SRC_C = auto()
    SRC_A = auto()
    INV_SRC_A = auto()
    DST_A = auto()
    INV_DST_A = auto()


class LogicOp(IntEnum):
    CLEAR = 0
    AND = auto()
    REV_AND = auto()
    COPY = auto()
    INV_AND = auto()
    NO_OP = auto()
    XOR = auto()
    OR = auto()
    NOR = auto()
    EQUIV = auto()
    INV = auto()
    REV_OR = auto()
    INV_COPY = auto()
    INV_OR = auto()
    NAND = auto()
    SET = auto()


@dataclass
class BlendMode:
    type: BlendModeType = BlendModeType.NONE
    source: BlendModeFactor = BlendModeFactor.SRC_A
    dest: BlendModeFactor = BlendModeFactor.INV_SRC_A
    logic: LogicOp = LogicOp.COPY
