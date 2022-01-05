from enum import IntEnum, auto
from dataclasses import dataclass

from sms_bin_editor.utils.gx.color import Color


class ColorSource(IntEnum):
    REGISTER = 0
    VERTEX = auto()


class LightID(IntEnum):
    NONE = 0
    LIGHT0 = 1 << 0
    LIGHT1 = 1 << 1
    LIGHT2 = 1 << 2
    LIGHT3 = 1 << 3
    LIGHT4 = 1 << 4
    LIGHT5 = 1 << 5
    LIGHT6 = 1 << 6
    LIGHT7 = 1 << 7


class DiffuseFunction(IntEnum):
    NONE = 0
    SIGN = auto()
    CLAMP = auto()


class AttenuationFunction(IntEnum):
    SPECULAR = 0
    SPOTLIGHT = auto()
    NONE = auto()
    # Necessary for J3D compatibility at the moment.
    # Really we're looking at SpecDisabled/SpotDisabled there (2 adjacent bits in
    # HW field)
    NONE2 = auto()


@dataclass
class ChannelControl:
    enabled: bool = False
    ambient: ColorSource = ColorSource.REGISTER
    material: ColorSource = ColorSource.REGISTER
    lightMask: LightID = LightID.NONE
    diffuseFn: DiffuseFunction = DiffuseFunction.NONE
    attenuationFn: AttenuationFunction = AttenuationFunction.NONE


@dataclass
class ChannelData:
    matColor: Color = Color(255, 255, 255, 255)
    ambColor: Color = Color(0, 0, 0, 255)
