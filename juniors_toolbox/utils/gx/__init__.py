###
# This module is referenced from RiiStudio and BinEditor, huge thanks to those involved
###

from enum import IntEnum, auto
from dataclasses import dataclass

class Comparison(IntEnum):
    NEVER = 0
    LESS = auto()
    EQUAL = auto()
    LEQUAL = auto()
    GREATER = auto()
    NEQUAL = auto()
    GEQUAL = auto()
    ALWAYS = auto()

class CullMode(IntEnum):
    NONE = 0
    FRONT = auto()
    BACK = auto()
    ALL = auto()


class DisplaySurface(IntEnum):
    BOTH = 0
    BACK = auto()
    FRONT = auto()
    NONE = auto()


def cullmode_to_display_surface(mode: CullMode) -> DisplaySurface:
    return DisplaySurface(mode.value)


@dataclass
class IndirectStage:
    scale = 0
    order = 0


class LowLevelGxMaterial():
    def __init__(self):
        ...