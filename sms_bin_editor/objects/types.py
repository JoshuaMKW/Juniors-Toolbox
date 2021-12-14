from typing import Optional, Tuple, Union
from enum import Enum, IntEnum

class BasicColors(IntEnum):
    RED = 0xFF0000FF
    GREEN = 0x00FF00FF
    BLUE = 0x0000FFFF
    BLACK = 0x000000FF
    WHITE = 0xFFFFFFFF
    LIGHT_GREY = 0xBFBFBFBF
    GREY = 0x7F7F7F7F
    DARK_GREY = 0x3F3F3F3F
    TRANSPARENT = 0x00000000

class ColorRGBA():
    """
    Class representing 32bit RGBA
    """
    def __init__(self, value: int):
        self.value = value

    @classmethod
    def from_tuple(cls, rgba: Tuple[int, int, int, Optional[int]]) -> "ColorRGBA":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        color.alpha = rgba[3] if len(rgba) > 3 else 255 
        return color

    @classmethod
    def from_hex(cls, rgba: str) -> "ColorRGBA":
        rgba = rgba.replace("#", "", 1)
        rgba = rgba.replace("0x", "", 1)
        if len(rgba) == 8:
            return cls(int(rgba, 16))
        return cls((int(rgba, 16) << 8) | 0xFF)

    @property
    def red(self) -> int:
        return (self.value >> 24) & 0xFF

    @red.setter
    def red(self, value: int):
        self.value = ((int(value) & 0xFF) << 24) | (self.value & 0x00FFFFFF)
    
    @property
    def green(self) -> int:
        return (self.value >> 16) & 0xFF

    @green.setter
    def green(self, value: int):
        self.value = ((int(value) & 0xFF) << 16) | (self.value & 0xFF00FFFF)

    @property
    def blue(self) -> int:
        return (self.value >> 8) & 0xFF

    @blue.setter
    def blue(self, value: int):
        self.value = ((int(value) & 0xFF) << 8) | (self.value & 0xFFFF00FF)
    
    @property
    def alpha(self) -> int:
        return self.value & 0xFF

    @alpha.setter
    def alpha(self, value: int):
        self.value = (int(value) & 0xFF) | (self.value & 0xFFFFFF00)

    def hex(self) -> str:
        return f"#{self.value:08X}"

    def tuple(self) -> Tuple[int, int, int, int]:
        return self.red, self.green, self.blue, self.alpha

    def inverse(self, preserveAlpha: bool = True) -> "ColorRGBA":
        color = ColorRGBA(0)
        color.red = 255 - self.red
        color.green = 255 - self.green
        color.blue = 255 - self.blue
        if preserveAlpha:
            color.alpha = self.alpha
        else:
            color.alpha = 255 - self.alpha
        return color

    def chooseContrastBW(self) -> "ColorRGBA":
        if self.saturation() > 0.6:
            return ColorRGBA(BasicColors.BLACK)
        else:
            return ColorRGBA(BasicColors.WHITE)

    def saturation(self) -> float:
        return ((self.red + self.green + self.blue) / 3) / 255

    def __eq__(self, other: Union["ColorRGBA", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, ColorRGBA):
            return self.value == other.value
        if isinstance(other, list):
            return self.tuple() == other
        return self.value == other

    def __ne__(self, other: Union["ColorRGBA", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, ColorRGBA):
            return self.value != other.value
        if isinstance(other, list):
            return self.tuple() != other
        return self.value != other

    def __repr__(self) -> str:
        return f"{self.red = }, {self.green = }, {self.blue = }, {self.alpha = }"

    def __str__(self) -> str:
        return self.hex()
