import math
from typing import Optional, Tuple, Union
from enum import Enum, IntEnum

from math import acos, degrees, sqrt
from sms_bin_editor.utils import clamp, clamp01, classproperty, sign


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


class RGBA():
    """
    Class representing 32bit RGBA
    """
    def __init__(self, value: Union[int, "RGBA"]):
        self.value = int(value)

    @classmethod
    def from_tuple(cls, rgba: Tuple[int, int, int, Optional[int]]) -> "RGBA":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        color.alpha = rgba[3] if len(rgba) > 3 else 255
        return color

    @classmethod
    def from_hex(cls, rgba: str) -> "RGBA":
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

    def inverse(self, preserveAlpha: bool = True) -> "RGBA":
        color = RGBA(0)
        color.red = 255 - self.red
        color.green = 255 - self.green
        color.blue = 255 - self.blue
        if preserveAlpha:
            color.alpha = self.alpha
        else:
            color.alpha = 255 - self.alpha
        return color

    def chooseContrastBW(self) -> "RGBA":
        if self.saturation() > (0.6 * (self.alpha / 255)):
            return RGBA(BasicColors.BLACK)
        else:
            return RGBA(BasicColors.WHITE)

    def saturation(self) -> float:
        return ((self.red + self.green + self.blue) / 3) / 255

    def __getitem__(self, index: int) -> int:
        if index not in range(4):
            raise IndexError(f"Index into {self.__class__.__name__} is out of range ([0-2])")
        return self.tuple()[index]

    def __setitem__(self, index: int, value: int) -> int:
        if index not in range(4):
            raise IndexError(f"Index into {self.__class__.__name__} is out of range ([0-2])")
        if index == 0:
            self.red = value
        elif index == 1:
            self.green = value
        elif index == 2:
            self.blue = value
        else:
            self.alpha = value

    def __eq__(self, other: Union["RGBA", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, RGBA):
            return self.value == other.value
        if isinstance(other, list):
            return self.tuple() == other
        return self.value == other

    def __ne__(self, other: Union["RGBA", int, Tuple[int, int, int, int]]) -> bool:
        if isinstance(other, RGBA):
            return self.value != other.value
        if isinstance(other, list):
            return self.tuple() != other
        return self.value != other

    def __repr__(self) -> str:
        return f"{self.red = }, {self.green = }, {self.blue = }, {self.alpha = }"

    def __str__(self) -> str:
        return self.hex()

    def __int__(self) -> int:
        return self.value


class Vec3f(list):
    """
    Class representing a Vector of 3 floats useful for geometric math
    """
    Epsilon = 0.00001
    EpsilonNormalSqrt = 1e-15

    def __init__(self, x: float = 0, y: float = 0, z: float = 0):
        self.append(float(x))
        self.append(float(y))
        self.append(float(z))
        self.__iteridx = 0

    @classproperty
    def zero(cls) -> "Vec3f":
        """
        A null Vector3f
        """
        return cls(0, 0, 0)
        
    @classproperty
    def one(cls) -> "Vec3f":
        """
        A Vector3f of one
        """
        return cls(1, 1, 1)

    @classproperty
    def left(cls) -> "Vec3f":
        """
        A Vector3f pointed left
        """
        return cls(-1, 0, 0)  

    @classproperty
    def right(cls) -> "Vec3f":
        """
        A Vector3f pointed right
        """
        return cls(1, 0, 0)

    @classproperty
    def up(cls) -> "Vec3f":
        """
        A Vector3f pointed up
        """
        return cls(0, 1, 0)
    
    @classproperty
    def down(cls) -> "Vec3f":
        """
        A Vector3f pointed down
        """
        return cls(0, -1, 0)

    @classproperty
    def forward(cls) -> "Vec3f":
        """
        A Vector3f pointed forward
        """
        return cls(0, 0, 1)

    @classproperty
    def back(cls) -> "Vec3f":
        """
        A Vector3f pointed back
        """
        return cls(0, 0, -1)

    @staticmethod
    def lerp(a: "Vec3f", b: "Vec3f", t: float, clamp: bool = True) -> "Vec3f":
        """
        Lerp between `a` and `b` using `t`
        """
        if clamp:
            t = clamp01(t)

        return Vec3f(
            a.x + (b.x - a.x) * t,
            a.y + (b.y - a.y) * t,
            a.z + (b.z - a.z) * t
        )

    @property
    def x(self) -> float:
        return self[0]

    @x.setter
    def x(self, x: float):
        self[0] = x

    @property
    def y(self) -> float:
        return self[1]

    @y.setter
    def y(self, y: float):
        self[1] = y

    @property
    def z(self) -> float:
        return self[2]

    @z.setter
    def z(self, z: float):
        self[2] = z

    @property
    def sqrMagnitude(self) -> float:
        return self.dot(self)

    @property
    def magnitude(self) -> float:
        return sqrt(self.dot(self))

    @property
    def normalized(self) -> "Vec3f":
        magnitude = self.magnitude
        if magnitude > self.Epsilon:
            return self / magnitude
        return Vec3f.zero

    def set(self, x: float, y: float, z: float):
        """
        Set all the components of this Vector3f
        """
        self[0] = x
        self[1] = y
        self[2] = z

    def scale(self, scale: Union[float, "Vec3f"]):
        """
        Scale all the components of this Vector3f by `scale`

        If `scale` is a float, scale all components uniformly with `scale`\n
        If `scale` is a Vector3f, scale the corrisponding components against `scale`
        """
        if isinstance(scale, float):
            self.x *= scale
            self.y *= scale
            self.z *= scale
        else:
            self.x *= scale.x
            self.y *= scale.y
            self.z *= scale.z

    def dot(self, other: "Vec3f") -> float:
        """
        Returns the dot product of this Vector3f and `other`
        """
        return self.x*other.x + self.y*other.y + self.z*other.z

    def cross(self, other: "Vec3f") -> "Vec3f":
        """
        Returns the cross product of this Vector3f and `other`
        """
        return Vec3f(
            self.y*other.z - self.z*other.y,
            self.z*other.x - self.x*other.z,
            self.x*other.y - self.y*other.x
        )

    def reflect(self, normal: "Vec3f") -> "Vec3f":
        """
        Reflects this Vector3f off the plane defined by `normal`
        """
        factor = -2.0 * normal.dot(self)
        return Vec3f(
            factor*normal.x + self.x,
            factor*normal.y + self.y,
            factor*normal.z + self.z
        )

    def normalize(self):
        """
        Normalizes this Vector3f to a magnitude of 1
        """
        magnitude = self.magnitude
        if magnitude > self.Epsilon:
            self = self / magnitude
        self = Vec3f.zero

    def project(self, normal: "Vec3f") -> "Vec3f":
        """
        Returns this Vector3f projected onto another vector
        """
        import sys
        sqrMag = normal.sqrMagnitude
        if sqrMag < sys.float_info.epsilon:
            return Vec3f.zero
        dot = self.dot(normal)
        return Vec3f(
            normal.x*dot / sqrMag,
            normal.y*dot / sqrMag,
            normal.z*dot / sqrMag
        )

    def project_on_plane(self, normal: "Vec3f") -> "Vec3f":
        """
        Returns this Vector3f projected onto a normal orthogonal to the plane
        """
        import sys
        sqrMag = normal.sqrMagnitude
        if sqrMag < sys.float_info.epsilon:
            return Vec3f.zero
        dot = self.dot(normal)
        return Vec3f(
            self.x - (normal.x*dot / sqrMag),
            self.y - (normal.y*dot / sqrMag),
            self.z - (normal.z*dot / sqrMag)
        )

    def angle(self, to: "Vec3f") -> float:
        """
        Returns the smallest angle in degrees between this Vector3f and `to`
        """
        denominator = sqrt(self.sqrMagnitude * to.sqrMagnitude)
        if denominator < self.EpsilonNormalSqrt:
            return 0.0

        dot = clamp(self.dot(to) / denominator, -1.0, 1.0)
        return degrees(acos(dot))

    def signed_angle(self, to: "Vec3f", axis: "Vec3f") -> float:
        """
        The smaller of the two possible angles between the two vectors is returned,
        therefore the result will never be greater than 180 degrees or smaller than -180 degrees.
        If you imagine the from and to vectors as lines on a piece of paper,
        both originating from the same point, then the `axis` vector would point up out of the paper.
        The measured angle between the two vectors would be positive in a clockwise direction and negative in an anti-clockwise direction.
        """
        cross = self.cross(to)
        return self.angle(to) * sign(axis.dot(cross))

    def distance(self, other: "Vec3f") -> float:
        """
        Returns the distance between this Vector3f and `other`
        """
        diff = self - other
        return diff.magnitude

    def min(self, other: "Vec3f") -> "Vec3f":
        """
        Returns a vector made from the smallest components of this Vector3f and `other`
        """
        return Vec3f(
            min(self.x, other.x),
            min(self.y, other.y),
            min(self.z, other.z)
        )

    def max(self, other: "Vec3f") -> "Vec3f":
        """
        Returns a vector made from the largest components of this Vector3f and `other`
        """
        return Vec3f(
            max(self.x, other.x),
            max(self.y, other.y),
            max(self.z, other.z)
        )

    def __add__(self, other: "Vec3f") -> "Vec3f":
        return Vec3f(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z
        )

    def __sub__(self, other: "Vec3f") -> "Vec3f":
        return Vec3f(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z
        )

    def __mul__(self, other: Union[float, "Vec3f"]) -> "Vec3f":
        if isinstance(other, float):
            return Vec3f(
                self.x * other,
                self.y * other,
                self.z * other
            )
        return Vec3f(
            self.x * other.x,
            self.y * other.y,
            self.z * other.z
        )

    def __div__(self, other: Union[float, "Vec3f"]) -> "Vec3f":
        if isinstance(other, float):
            return Vec3f(
                self.x / other,
                self.y / other,
                self.z / other
            )
        return Vec3f(
            self.x / other.x,
            self.y / other.y,
            self.z / other.z
        )

    def __next__(self) -> float:
        if self.__iteridx > 2:
            self.__iteridx = 0
            raise StopIteration
        self.__iteridx += 1
        return self[self.__iteridx-1]

    def __getitem__(self, index: int) -> float:
        if index not in range(3):
            raise IndexError(f"Index into {self.__class__.__name__} is out of range ([0-2])")
        return super().__getitem__(index)

    def __setitem__(self, index: int, value: float):
        if index not in range(3):
            raise IndexError(f"Index into {self.__class__.__name__} is out of range ([0-2])")
        super().__setitem__(index, value)

    def __len__(self) -> float:
        return self.magnitude

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.x=}, {self.y=}, {self.z=})"
