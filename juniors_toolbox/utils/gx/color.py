from typing import Optional, Tuple, Union

from juniors_toolbox.utils.types import RGBA as Color
from juniors_toolbox.utils import clamp01

class ColorS10(Color):
    """
    Class representing 40bit signed RGBA
    """

    @classmethod
    def from_tuple(cls, rgba: Tuple[int, int, int, Optional[int]]) -> "ColorS10":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        color.alpha = rgba[3] if len(rgba) > 3 else 1023
        return color

    @classmethod
    def from_hex(cls, rgba: str) -> "ColorS10":
        rgba = rgba.replace("#", "", 1)
        rgba = rgba.replace("0x", "", 1)
        if len(rgba) == 10:
            return cls(int(rgba, 16))
        return cls((int(rgba, 16) << 10) | 0x3FF)

    @property
    def red(self) -> int:
        return (self.value >> 30) & 0x3FF

    @red.setter
    def red(self, value: int):
        self.value = ((int(value) & 0x3FF) << 30) | (self.value & 0x003FFFFFFF)

    @property
    def green(self) -> int:
        return (self.value >> 20) & 0x3FF

    @green.setter
    def green(self, value: int):
        self.value = ((int(value) & 0x3FF) << 20) | (self.value & 0xFFC00FFFFF)

    @property
    def blue(self) -> int:
        return (self.value >> 10) & 0x3FF

    @blue.setter
    def blue(self, value: int):
        self.value = ((int(value) & 0x3FF) << 10) | (self.value & 0xFFFFF003FF)

    @property
    def alpha(self) -> int:
        return self.value & 0x3FF

    @alpha.setter
    def alpha(self, value: int):
        self.value = (int(value) & 0x3FF) | (self.value & 0xFFFFFFFC00)

    def hex(self) -> str:
        return f"#{self.value:10X}"

    def tuple(self) -> Tuple[int, int, int, int]:
        return self.red, self.green, self.blue, self.alpha

    def inverse(self, preserveAlpha: bool = True) -> "ColorS10":
        color = ColorS10(0)
        color.red = 1023 - self.red
        color.green = 1023 - self.green
        color.blue = 1023 - self.blue
        if preserveAlpha:
            color.alpha = self.alpha
        else:
            color.alpha = 1023 - self.alpha
        return color

    def chooseContrastBW(self) -> "ColorS10":
        if self.saturation() > (0.6 * (self.alpha / 1023)):
            return ColorS10(0x00000000FF)
        else:
            return ColorS10(0xFFFFFFFFFF)

    def saturation(self) -> float:
        return ((self.red + self.green + self.blue) / 3) / 1023


class ColorF32():
    """
    Class representing 128bit floating point RGBA
    """

    def __init__(self, red: float, green: float, blue: float, alpha: float):
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
    
    @classmethod
    def from_tuple(cls, rgba: Tuple[float, float, float, Optional[float]]) -> "ColorF32":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        color.alpha = rgba[3] if len(rgba) > 3 else 1.0
        return color

    @property
    def red(self) -> int:
        return self.red

    @red.setter
    def red(self, value: float):
        self.red = float(clamp01(value))

    @property
    def green(self) -> int:
        return self.green

    @green.setter
    def green(self, value: float):
        self.green = float(clamp01(value))

    @property
    def blue(self) -> int:
        return self.blue

    @blue.setter
    def blue(self, value: float):
        self.blue = float(clamp01(value))

    @property
    def alpha(self) -> int:
        return self.alpha

    @alpha.setter
    def alpha(self, value: float):
        self.alpha = float(clamp01(value))

    def to_color32(self) -> Color:
        return Color.from_tuple(
            self.red * 255,
            self.green * 255,
            self.blue * 255,
            self.alpha * 255
        )

    def to_color40(self) -> ColorS10:
        return ColorS10.from_tuple(
            self.red * 1023,
            self.green * 1023,
            self.blue * 1023,
            self.alpha * 1023
        )

    def tuple(self) -> Tuple[int, int, int, int]:
        return self.red, self.green, self.blue, self.alpha

    def inverse(self, preserveAlpha: bool = True) -> "ColorF32":
        color = ColorF32(0)
        color.red = 1.0 - self.red
        color.green = 1.0 - self.green
        color.blue = 1.0 - self.blue
        if preserveAlpha:
            color.alpha = self.alpha
        else:
            color.alpha = 1.0 - self.alpha
        return color

    def chooseContrastBW(self) -> "ColorF32":
        if self.saturation() > (0.6 * self.alpha):
            return ColorF32(0.0, 0.0, 0.0, 1.0)
        else:
            return ColorF32(1.0, 1.0, 1.0, 1.0)

    def saturation(self) -> float:
        return (self.red + self.green + self.blue) / 3

    def __getitem__(self, index: int) -> int:
        if index not in range(4):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-3])")
        return self.tuple()[index]

    def __setitem__(self, index: int, value: int) -> int:
        if index not in range(4):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-3])")
        if index == 0:
            self.red = value
        elif index == 1:
            self.green = value
        elif index == 2:
            self.blue = value
        else:
            self.alpha = value

    def __eq__(self, other: Union["ColorF32", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, ColorF32):
            return self.value == other.value
        if isinstance(other, list):
            return self.tuple() == other
        return self.value == other

    def __ne__(self, other: Union["ColorF32", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, ColorF32):
            return self.value != other.value
        if isinstance(other, list):
            return self.tuple() != other
        return self.value != other

    def __repr__(self) -> str:
        red = self.red
        green = self.green
        blue = self.blue
        alpha = self.alpha
        return f"{self.__class__.__name__}({red=}, {green=}, {blue=}, {alpha=})"

    def __str__(self) -> str:
        return self.__repr__()
