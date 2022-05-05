from abc import ABC, abstractmethod
import math
from typing import Optional, Tuple, Union
from enum import Enum, IntEnum

from math import acos, asin, atan2, cos, degrees, pi, radians, sin, sqrt
from numpy import array

from pyrr.objects import quaternion
from juniors_toolbox.utils import clamp, clamp01, classproperty, sign
from pyrr import Vector3, Vector4, Matrix33, Matrix44
from pyrr import Quaternion as _PyrrQuaternion


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


class DigitalColor(ABC):
    """
    Abstract base class representing color
    """

    def __init__(self, value: int):
        self._value = int(value)

    def raw(self) -> int:
        return self._value

    @classmethod
    @abstractmethod
    def from_tuple(cls, rgba: tuple) -> "DigitalColor": ...

    @classmethod
    @abstractmethod
    def from_hex(cls, rgba: str) -> "DigitalColor": ...

    @property
    @abstractmethod
    def red(self) -> int: ...

    @red.setter
    @abstractmethod
    def red(self, value: int): ...

    @property
    @abstractmethod
    def green(self) -> int: ...

    @green.setter
    @abstractmethod
    def green(self, value: int): ...

    @property
    @abstractmethod
    def blue(self) -> int: ...

    @blue.setter
    @abstractmethod
    def blue(self, value: int): ...

    @property
    @abstractmethod
    def alpha(self) -> int: ...

    @alpha.setter
    @abstractmethod
    def alpha(self, value: int): ...

    @abstractmethod
    def hex(self) -> str: ...

    @abstractmethod
    def tuple(self) -> tuple: ...

    @abstractmethod
    def inverse(self, preserveAlpha: bool = True) -> "DigitalColor": ...

    @abstractmethod
    def chooseContrastBW(self) -> "DigitalColor": ...

    @abstractmethod
    def saturation(self) -> float: ...

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

    def __eq__(self, other: Union["DigitalColor", int, tuple]) -> bool:
        if isinstance(other, DigitalColor):
            return self.hex() == other.hex()
        if isinstance(other, list):
            return self.tuple() == other
        return self.hex() == other

    def __ne__(self, other: Union["DigitalColor", int, tuple]) -> bool:
        if isinstance(other, DigitalColor):
            return self.hex() != other.hex()
        if isinstance(other, list):
            return self.tuple() != other
        return self.hex() != other

    def __repr__(self) -> str:
        red = self.red
        green = self.green
        blue = self.blue
        alpha = self.alpha
        return f"{self.__class__.__name__}({red=}, {green=}, {blue=}, {alpha=})"

    def __str__(self) -> str:
        return self.hex()

    def __int__(self) -> int:
        return self.raw()


class RGBA8(DigitalColor):
    """
    Class representing 8bit RGBA
    """
    @classmethod
    def from_tuple(cls, rgba: tuple) -> "RGBA8":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        color.alpha = rgba[3] if len(rgba) > 3 else 255
        return color

    @classmethod
    def from_hex(cls, rgba: str) -> "RGBA8":
        rgba = rgba.replace("#", "", 1)
        rgba = rgba.replace("0x", "", 1)
        if len(rgba) == 8:
            return cls(int(rgba, 16))
        return cls((int(rgba, 16) << 8) | 0xFF)

    @property
    def red(self) -> int:
        return (self._value >> 24) & 0xFF

    @red.setter
    def red(self, value: int):
        self._value = ((int(value) & 0xFF) << 24) | (self._value & 0x00FFFFFF)

    @property
    def green(self) -> int:
        return (self._value >> 16) & 0xFF

    @green.setter
    def green(self, value: int):
        self._value = ((int(value) & 0xFF) << 16) | (self._value & 0xFF00FFFF)

    @property
    def blue(self) -> int:
        return (self._value >> 8) & 0xFF

    @blue.setter
    def blue(self, value: int):
        self._value = ((int(value) & 0xFF) << 8) | (self._value & 0xFFFF00FF)

    @property
    def alpha(self) -> int:
        return self._value & 0xFF

    @alpha.setter
    def alpha(self, value: int):
        self._value = (int(value) & 0xFF) | (self._value & 0xFFFFFF00)

    def hex(self) -> str:
        return f"#{self._value:08X}"

    def tuple(self) -> Tuple[int, int, int, int]:
        return self.red, self.green, self.blue, self.alpha

    def inverse(self, preserveAlpha: bool = True) -> "RGBA8":
        color = RGBA8(0)
        color.red = 255 - self.red
        color.green = 255 - self.green
        color.blue = 255 - self.blue
        if preserveAlpha:
            color.alpha = self.alpha
        else:
            color.alpha = 255 - self.alpha
        return color

    def chooseContrastBW(self) -> "RGBA8":
        if self.saturation() > (0.6 * (self.alpha / 255)):
            return RGBA8(BasicColors.BLACK)
        else:
            return RGBA8(BasicColors.WHITE)

    def saturation(self) -> float:
        return ((self.red + self.green + self.blue) / 3) / 255

    def __repr__(self) -> str:
        red = self.red
        green = self.green
        blue = self.blue
        alpha = self.alpha
        return f"{self.__class__.__name__}({red=}, {green=}, {blue=}, {alpha=})"


class RGB8(DigitalColor):
    """
    Class representing 8bit RGB
    """
    @classmethod
    def from_tuple(cls, rgba: tuple) -> "RGB8":
        color = cls(0)
        color.red = rgba[0]
        color.green = rgba[1]
        color.blue = rgba[2]
        return color

    @classmethod
    def from_hex(cls, rgb: str) -> "RGB8":
        rgb = rgb.replace("#", "", 1)
        rgb = rgb.replace("0x", "", 1)
        return cls(int(rgb, 16))

    @property
    def red(self) -> int:
        return (self._value >> 16) & 0xFF

    @red.setter
    def red(self, value: int):
        self._value = ((int(value) & 0xFF) << 16) | (self._value & 0x00FFFF)

    @property
    def green(self) -> int:
        return (self._value >> 8) & 0xFF

    @green.setter
    def green(self, value: int):
        self._value = ((int(value) & 0xFF) << 8) | (self._value & 0xFF00FF)

    @property
    def blue(self) -> int:
        return self._value & 0xFF

    @blue.setter
    def blue(self, value: int):
        self._value = (int(value) & 0xFF) | (self._value & 0xFFFF00)

    @property
    def alpha(self) -> int:
        return None

    @alpha.setter
    def alpha(self, value: int):
        pass

    def hex(self) -> str:
        return f"#{self._value:06X}"

    def tuple(self) -> tuple:
        return self.red, self.green, self.blue

    def inverse(self) -> "RGB8":
        color = RGB8(0)
        color.red = 255 - self.red
        color.green = 255 - self.green
        color.blue = 255 - self.blue
        return color

    def chooseContrastBW(self) -> "RGB8":
        if self.saturation() > 0.6:
            return RGB8(BasicColors.BLACK)
        else:
            return RGB8(BasicColors.WHITE)

    def saturation(self) -> float:
        return ((self.red + self.green + self.blue) / 3) / 255

    def __repr__(self) -> str:
        red = self.red
        green = self.green
        blue = self.blue
        return f"{self.__class__.__name__}({red=}, {green=}, {blue=})"


class RGB32(RGB8):
    """
    Clamps to 256, but represented by int sized data
    """

    @property
    def red(self) -> int:
        return (self._value >> 64) & 0xFF

    @red.setter
    def red(self, value: int):
        self._value = ((int(value) & 0xFF) << 64) | (
            self._value & 0x00000000FFFFFFFFFFFFFFFF)

    @property
    def green(self) -> int:
        return (self._value >> 32) & 0xFF

    @green.setter
    def green(self, value: int):
        self._value = ((int(value) & 0xFF) << 32) | (
            self._value & 0xFFFFFFFF00000000FFFFFFFF)

    @property
    def blue(self) -> int:
        return self._value & 0xFF

    @blue.setter
    def blue(self, value: int):
        self._value = (int(value) & 0xFF) | (
            self._value & 0xFFFFFFFFFFFFFFFF00000000)

    @property
    def alpha(self) -> int:
        return None

    @alpha.setter
    def alpha(self, value: int):
        pass


class RGBA32(RGBA8):
    """
    Clamps to 256, but represented by int sized data
    """

    @property
    def red(self) -> int:
        return (self._value >> 64) & 0xFF

    @red.setter
    def red(self, value: int):
        self._value = ((int(value) & 0xFF) << 96) | (
            self._value & 0x00000000FFFFFFFFFFFFFFFFFFFFFFFF)

    @property
    def green(self) -> int:
        return (self._value >> 32) & 0xFF

    @green.setter
    def green(self, value: int):
        self._value = ((int(value) & 0xFF) << 64) | (
            self._value & 0xFFFFFFFF00000000FFFFFFFFFFFFFFFF)

    @property
    def blue(self) -> int:
        return self._value & 0xFF

    @blue.setter
    def blue(self, value: int):
        self._value = ((int(value) & 0xFF) << 32) | (
            self._value & 0xFFFFFFFFFFFFFFFF00000000FFFFFFFF)

    @property
    def alpha(self) -> int:
        return None

    @alpha.setter
    def alpha(self, value: int):
        self._value = (int(value) & 0xFF) | (
            self._value & 0xFFFFFFFFFFFFFFFFFFFFFFFF00000000)


class Vec2f(list):
    """
    Class representing a Vector of 3 floats useful for geometric math
    """
    Epsilon = 0.00001
    EpsilonNormalSqrt = 1e-15

    def __init__(self, x: float = 0, y: float = 0):
        self.append(float(x))
        self.append(float(y))
        self.__iteridx = 0

    @classproperty
    def zero(cls) -> "Vec2f":
        """
        A null Vector3f
        """
        return cls(0, 0)

    @classproperty
    def one(cls) -> "Vec2f":
        """
        A Vector3f of one
        """
        return cls(1, 1)

    @classproperty
    def left(cls) -> "Vec2f":
        """
        A Vector3f pointed left
        """
        return cls(-1, 0)

    @classproperty
    def right(cls) -> "Vec2f":
        """
        A Vector3f pointed right
        """
        return cls(1, 0)

    @classproperty
    def up(cls) -> "Vec2f":
        """
        A Vector3f pointed up
        """
        return cls(0, 1)

    @classproperty
    def down(cls) -> "Vec2f":
        """
        A Vector3f pointed down
        """
        return cls(0, -1)

    @staticmethod
    def lerp(a: "Vec2f", b: "Vec2f", t: float, clamp: bool = True) -> "Vec2f":
        """
        Lerp between `a` and `b` using `t`
        """
        if clamp:
            t = clamp01(t)

        return Vec2f(
            a.x + (b.x - a.x) * t,
            a.y + (b.y - a.y) * t
        )

    @property
    def x(self) -> float:
        return self.x

    @x.setter
    def x(self, x: float):
        self.x = float(x)

    @property
    def y(self) -> float:
        return self.y

    @y.setter
    def y(self, y: float):
        self.y = float(y)

    @property
    def sqrMagnitude(self) -> float:
        return self.dot(self)

    @property
    def magnitude(self) -> float:
        return sqrt(self.dot(self))

    @property
    def normalized(self) -> "Vec2f":
        magnitude = self.magnitude
        if magnitude > self.Epsilon:
            return self / magnitude
        return Vec2f.zero

    @property
    def components(self) -> Tuple[float, float]:
        return self.x, self.y

    def set(self, x: float, y: float):
        """
        Set all the components of this Vector2f
        """
        self.x = float(x)
        self.y = float(y)

    def scale(self, scale: Union[float, "Vec2f"]):
        """
        Scale all the components of this Vector2f by `scale`

        If `scale` is a float, scale all components uniformly with `scale`\n
        If `scale` is a Vector2f, scale the corrisponding components against `scale`
        """
        if isinstance(scale, float):
            self.x *= scale
            self.y *= scale
        else:
            self.x *= scale.x
            self.y *= scale.y

    def dot(self, other: "Vec2f") -> float:
        """
        Returns the dot product of this Vector2f and `other`
        """
        return self.x*other.x + self.y*other.y

    def reflect(self, normal: "Vec2f") -> "Vec2f":
        """
        Reflects this Vector2f off the plane defined by `normal`
        """
        factor = -2.0 * normal.dot(self)
        return Vec2f(
            factor*normal.x + self.x,
            factor*normal.y + self.y
        )

    def normalize(self):
        """
        Normalizes this Vector2f to a magnitude of 1
        """
        normalized = self.normalized
        self.x = normalized.x
        self.y = normalized.y

    def angle(self, to: "Vec2f") -> float:
        """
        Returns the smallest angle in degrees between this Vector2f and `to`
        """
        denominator = sqrt(self.sqrMagnitude * to.sqrMagnitude)
        if denominator < self.EpsilonNormalSqrt:
            return 0.0

        dot = clamp(self.dot(to) / denominator, -1.0, 1.0)
        return degrees(acos(dot))

    def distance(self, other: "Vec2f") -> float:
        """
        Returns the distance between this Vector2f and `other`
        """
        diff = self - other
        return diff.magnitude

    def min(self, other: "Vec2f") -> "Vec2f":
        """
        Returns a vector made from the smallest components of this Vector2f and `other`
        """
        return Vec2f(
            min(self.x, other.x),
            min(self.y, other.y),
        )

    def max(self, other: "Vec2f") -> "Vec2f":
        """
        Returns a vector made from the largest components of this Vector2f and `other`
        """
        return Vec2f(
            max(self.x, other.x),
            max(self.y, other.y),
        )

    def __add__(self, other: "Vec2f") -> "Vec2f":
        return Vec2f(
            self.x + other.x,
            self.y + other.y,
        )

    def __sub__(self, other: "Vec2f") -> "Vec2f":
        return Vec2f(
            self.x - other.x,
            self.y - other.y,
        )

    def __mul__(self, other: Union[float, "Vec2f"]) -> "Vec2f":
        if isinstance(other, Vec2f):
            return Vec2f(
                self.x * other.x,
                self.y * other.y
            )
        return Vec2f(
            self.x * other,
            self.y * other
        )

    def __truediv__(self, other: Union[float, "Vec2f"]) -> "Vec2f":
        if isinstance(other, Vec2f):
            return Vec2f(
                self.x / other.x,
                self.y / other.y
            )
        return Vec2f(
            self.x / other,
            self.y / other
        )

    def __next__(self) -> float:
        if self.__iteridx > 1:
            self.__iteridx = 0
            raise StopIteration
        self.__iteridx += 1
        return self[self.__iteridx-1]

    def __getitem__(self, index: int) -> float:
        if index not in range(2):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-1])")
        return super().__getitem__(index)

    def __setitem__(self, index: int, value: float):
        if index not in range(2):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-1])")
        super().__setitem__(index, value)

    def __len__(self) -> float:
        return self.magnitude

    def __str__(self) -> str:
        x = self.x
        y = self.y
        return f"{self.__class__.__name__}({x=}, {y=})"


class Vec3f(Vector3):
    """
    Class representing a Vector of 3 floats useful for geometric math
    """
    Epsilon = 0.00001
    EpsilonNormalSqrt = 1e-15

    def __new__(cls, x: float = 0, y: float = 0, z: float = 0):
        return super().__new__(cls, value=[float(x), float(y), float(z)], dtype=float)

    def __init__(self, x: float = 0, y: float = 0, z: float = 0):
        self.__iteridx = 0

    @classproperty
    def zero(cls) -> "Vec3f":
        """
        A null Vecto3f
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

    # @property
    # def x(self) -> float:
    #     return self.x

    # @x.setter
    # def x(self, x: float):
    #     self.x = float(x)

    # @property
    # def y(self) -> float:
    #     return self.y

    # @y.setter
    # def y(self, y: float):
    #     self.y = float(y)

    # @property
    # def z(self) -> float:
    #     return self.z

    # @z.setter
    # def z(self, z: float):
    #     self.z = float(z)

    @property
    def sqrMagnitude(self) -> float:
        return super().squared_length

    @property
    def magnitude(self) -> float:
        return self.length

    @property
    def normalized(self) -> "Vec3f":
        return super().normalized

    @property
    def components(self) -> Tuple[float, float, float]:
        return self.x, self.y, self.z

    def set(self, x: float, y: float, z: float):
        """
        Set all the components of this Vector3f
        """
        self.xyz = [float(x), float(y), float(z)]

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
        return super().dot(other)

    def cross(self, other: "Vec3f") -> "Vec3f":
        """
        Returns the cross product of this Vector3f and `other`
        """
        return super().cross(other)

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
        super().normalize()

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

    def __iter__(self):
        self.__iteridx = 0
        return super().__iter__()

    def __next__(self) -> float:
        if self.__iteridx > 2:
            raise StopIteration
        self.__iteridx += 1
        return self[self.__iteridx-1]

    def __len__(self) -> float:
        return self.magnitude

    def __str__(self) -> str:
        x = self.x
        y = self.y
        z = self.z
        return f"{self.__class__.__name__}({x=}, {y=}, {z=})"


class Quaternion(_PyrrQuaternion):
    """
    Class representing a quaternion rotation
    """
    Epsilon = 0.000001

    def __init__(
        self,
        xyzw: tuple[float, float, float, float] = (0, 0, 0, 1)
    ):
        self.x = float(xyzw[0])
        self.y = float(xyzw[1])
        self.z = float(xyzw[2])
        self.w = float(xyzw[3])

    @classproperty
    def identity(cls) -> "Quaternion":
        return cls(0, 0, 0, 1)

    @property
    def xyz(self) -> Vec3f:
        return Vec3f(self.x, self.y, self.z)

    @xyz.setter
    def xyz(self, xyz: Vec3f):
        self.x = xyz.x
        self.y = xyz.y
        self.z = xyz.z

    @property
    def magnitude(self) -> float:
        return sqrt(self.dot(self))

    @property
    def sqrMagnitude(self) -> float:
        return self.dot(self)

    @property
    def normalized(self) -> "Quaternion":
        quat = Quaternion([self.x, self.y, self.z, self.w])
        scale = 1.0 / self.magnitude
        quat.xyz *= scale
        quat.w *= scale
        return quat

    @property
    def inversed(self) -> "Quaternion":
        quat = Quaternion([self.x, self.y, self.z, self.w])
        sqrLen = self.sqrMagnitude
        if (sqrLen != 0.0):
            i = 1.0 / sqrLen
            quat.xyz *= -i
            quat.w *= i
        return quat

    @staticmethod
    def normalize_angle(angle: float) -> float:
        factor = angle // 360
        return angle - 360 * factor

    @staticmethod
    def normalize_angles(angles: Vec3f):
        angles.x = Quaternion.normalize_angle(angles.x)
        angles.y = Quaternion.normalize_angle(angles.y)
        angles.z = Quaternion.normalize_angle(angles.z)
        return angles

    @staticmethod
    def lerp(a: "Quaternion", b: "Quaternion", t: float, clamp: bool = True) -> "Quaternion":
        """
        Lerp between `a` and `b` using `t`
        """
        if clamp:
            t = clamp01(t)

        return Quaternion.slerp(a, b, t, False)

    @staticmethod
    def slerp(a: "Quaternion", b: "Quaternion", t: float, clamp: bool = True) -> "Quaternion":
        """
        Slerp between `a` and `b` using `t`
        """
        if clamp:
            t = clamp01(t)

        if a.sqrMagnitude == 0.0:
            return Quaternion.identity if b.sqrMagnitude == 0 else b
        elif b.sqrMagnitude == 0.0:
            return a

        cosHalfAngle = a.w*b.w + a.xyz.dot(b.xyz)
        if cosHalfAngle >= 1.0 or cosHalfAngle <= -1.0:
            return a
        elif cosHalfAngle < 0.0:
            b.xyz = -b.xyz
            b.w = -b.w
            cosHalfAngle = -cosHalfAngle

        blendA = 1.0 - t
        blendB = t
        if cosHalfAngle < 0.99:
            halfAngle = acos(cosHalfAngle)
            factorSinHalfAngle = sin(halfAngle)
            blendA = sin(halfAngle*(1.0 - t)) * factorSinHalfAngle
            blendB = sin(halfAngle*t) * factorSinHalfAngle
        quat = Quaternion(
            *(a.xyz*blendA + b.xyz*blendB).components,
            a.w*blendA + b.w*blendB
        )
        if quat.sqrMagnitude > 0.0:
            quat.normalize()
            return quat
        return Quaternion.identity

    @classmethod
    def from_euler(cls, euler: Vec3f, unityStyle: bool = False) -> "Quaternion":
        """
        Create a rotation from `euler` (Unity style)
        """
        if not unityStyle:
            return cls.from_eulers(euler.xyz, dtype=float)
        halfYaw = radians(euler.x) * 0.5
        halfPitch = radians(euler.y) * 0.5
        halfRoll = radians(euler.z) * 0.5
        sinYaw = sin(halfYaw)
        cosYaw = cos(halfYaw)
        sinPitch = sin(halfPitch)
        cosPitch = cos(halfPitch)
        sinRoll = sin(halfRoll)
        cosRoll = cos(halfRoll)
        return cls(
            cosPitch*sinYaw*cosRoll + sinPitch*cosYaw*sinRoll,
            sinPitch*cosYaw*cosRoll - cosPitch*sinYaw*sinRoll,
            cosPitch*cosYaw*sinRoll - sinPitch*sinYaw*cosRoll,
            cosPitch*cosYaw*cosRoll + sinPitch*sinYaw*sinRoll
        )

    def to_euler(self) -> "Vec3f":
        """
        Return a euler rotation from this Quaternion
        """
        magnitude = self.magnitude
        orientation = self.x*self.w - self.y*self.z
        if (orientation > 0.4995 * magnitude):
            # Singularity at north pole
            return Quaternion.normalize_angles(
                Vec3f(
                    degrees(pi / 2),
                    degrees(2 * atan2(self.y, self.x)),
                    0
                )
            )
        if (orientation < -0.4995 * magnitude):
            # Singularity at south pole
            return Quaternion.normalize_angles(
                Vec3f(
                    degrees(-pi / 2),
                    degrees(-2 * atan2(self.y, self.x)),
                    0
                )
            )
        quat = Quaternion(
            self.w,
            self.z,
            self.x,
            self.y
        )
        return Quaternion.normalize_angles(
            Vec3f(
                degrees(atan2(2*quat.x*quat.w + 2*quat.y*quat.z,
                              1 - 2*(quat.z*quat.z+quat.w*quat.w))),
                degrees(asin(2*(quat.x*quat.z - quat.w*quat.y))),
                degrees(atan2(2*quat.x*quat.y + 2*quat.z*quat.w,
                              1 - 2*(quat.yz*quat.y+quat.z*quat.z)))
            )
        )

    @classmethod
    def from_to_rotation(cls, _from: Vec3f, _to: Vec3f) -> "Quaternion":
        """
        Creates a rotation from `_from` to `_to`
        """
        axis = _from.cross(_to)
        angle = _from.angle(_to)
        if (angle >= 179.9196):
            rcross = _from.cross(Vec3f.right)
            axis = rcross.cross(_from)
            if axis.sqrMagnitude < cls.Epsilon:
                axis = Vec3f.up
        return Quaternion.from_angle_axis(angle, axis.normalized)

    @classmethod
    def from_angle_axis(cls, degrees: float, axis: Vec3f = Vec3f.up):
        if axis.sqrMagnitude == 0.0:
            return cls.identity

        quat = cls()
        rad = radians(degrees) * 0.5
        axis.normalize()
        axis = axis * sin(rad)
        quat.x = axis.x
        quat.y = axis.y
        quat.z = axis.z
        quat.w = cos(rad)
        quat.normalize()
        return quat

    def to_angle_axis(self) -> Tuple[float, Vec3f]:
        if abs(self.w) > 1.0:
            self.normalize()
        angle = 2 * acos(self.w)
        den = sqrt(1.0 - self.w*self.w)
        if den > 0.0001:
            axis = self.xyz / den
        else:
            axis = Vec3f.right
        return degrees(angle), axis

    def set(self, x: float, y: float, z: float, w: float):
        """
        Set all the components of this Quaternion
        """
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.w = float(w)

    def normalize(self):
        """
        Normalize the scale of this Quaternion
        """
        normalized = self.normalized
        self.x = normalized.x
        self.y = normalized.y
        self.z = normalized.z
        self.w = normalized.w

    def inverse(self):
        """
        Inverses this Quaternion
        """
        inversed = self.inversed
        self.x = inversed.x
        self.y = inversed.y
        self.z = inversed.z
        self.w = inversed.w

    def dot(self, other: "Quaternion") -> float:
        """
        Returns the dot product of this Quaternion and `other`
        """
        return self.x*other.x + self.y*other.y + self.z*other.z + self.w*other.w

    def angle(self, other: "Quaternion") -> float:
        """
        Returns the angle in degrees between this Quaternion and `other`
        """
        dot = self.dot(other)
        return degrees(acos(min(abs(dot), 1.0)) * 2.0)

    def is_equal_using_dot(self, dot: float) -> bool:
        return dot > (1.0 - self.Epsilon)

    def look_rotation(self, forward: Vec3f, up: Vec3f = Vec3f.up) -> "Quaternion":
        """
        Creates a rotation that is looking at `forward` on the `up` axis
        """
        forward.normalize()
        right = up.cross(forward)
        right.normalize()
        up = forward.cross(right)
        rx = right.x
        ry = right.y
        rz = right.z
        ux = up.x
        uy = up.y
        uz = up.z
        fx = forward.x
        fy = forward.y
        fz = forward.z

        quat = Quaternion()

        sumXYZ = rx + uy + fz
        if sumXYZ > 0:
            scale = sqrt(sumXYZ + 1)
            quat.w = scale / 2
            scale = 0.5 / scale
            quat.x = (uz - fy) * scale
            quat.y = (fx - rz) * scale
            quat.z = (ry - ux) * scale
        elif rx >= uy and rx >= fz:
            scale = sqrt(1 + rx - uy - fz)
            quat.x = scale / 2
            scale = 0.5 / scale
            quat.y = (ry + ux) * scale
            quat.z = (rz + fx) * scale
            quat.w = (uz + fy) * scale
        elif uy > fz:
            scale = sqrt(1 + uy - rx - fz)
            quat.y = scale / 2
            scale = 0.5 / scale
            quat.x = (ux + ry) * scale
            quat.z = (fy + uz) * scale
            quat.w = (fx + rz) * scale
        else:
            scale = sqrt(1 + fz - rx - uy)
            quat.z = scale / 2
            scale = 0.5 / scale
            quat.x = (fx + rz) * scale
            quat.y = (fy + uz) * scale
            quat.w = (ry + ux) * scale
        return quat

    def set_look_rotation(self, view: Vec3f, up: Vec3f = Vec3f.up):
        """
        Sets this Quaternion to be rotated towards `view` on the `up` axis
        """
        self = self.look_rotation(view, up)

    def rotate_towards(self, to: "Quaternion", maxDegreesDelta: float):
        """
        Rotates this Quaternion towards `to`
        """
        angle = self.angle(to)
        if angle == 0.0:
            self = to
        t = min(1.0, maxDegreesDelta / angle)
        self = Quaternion.slerp(self, to, t, False)

    def __eq__(self, other: "Quaternion"):
        return self.is_equal_using_dot(self.dot(other))

    def __ne__(self, other: "Quaternion"):
        return not self.is_equal_using_dot(self.dot(other))

    def __mul__(self, other: "Quaternion") -> Union["Quaternion", Vec3f]:
        if not isinstance(other, (Quaternion, Vec3f)):
            raise ValueError(
                "Can't combine this rotation with a non rotation!")
        if isinstance(other, Quaternion):
            # Combines the rotations
            return Quaternion(
                (self.w*other.x + self.x*other.w + self.y*other.z - self.z*other.y,
                 self.w*other.y + self.y*other.w + self.z*other.x - self.x*other.z,
                 self.w*other.z + self.z*other.w + self.x*other.y - self.y*other.x,
                 self.w*other.w - self.x*other.x - self.y*other.y - self.z*other.z)
            )
        elif isinstance(other, Vec3f):
            # Rotates the point with this rotation
            x = self.x * 2
            y = self.y * 2
            z = self.z * 2
            xx = self.x * x
            yy = self.y * y
            zz = self.z * z
            xy = self.x * y
            xz = self.x * z
            yz = self.y * z
            wx = self.w * x
            wy = self.w * y
            wz = self.w * z
            return Vec3f(
                (1 - (yy + zz))*other.x + (xy - wz)*other.y + (xz + wy)*other.z,
                (xy + wz)*other.x + (1 - (xx + zz))*other.y + (yz - wx)*other.z,
                (xz - wy)*other.x + (yz + wx)*other.y + (1 - (xx + yy))*other.z
            )

    def __next__(self) -> float:
        if self.__iteridx > 3:
            self.__iteridx = 0
            raise StopIteration
        self.__iteridx += 1
        return self[self.__iteridx-1]

    def __getitem__(self, index: int) -> float:
        if index not in range(4):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-3])")
        return super().__getitem__(index)

    def __setitem__(self, index: int, value: float):
        if index not in range(4):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-3])")
        super().__setitem__(index, value)

    def __len__(self) -> float:
        return self.magnitude

    def __str__(self) -> str:
        x = self.x
        y = self.y
        z = self.z
        w = self.w
        return f"{self.__class__.__name__}({x=}, {y=}, {z=}, {w=})"


class Transform():
    """
    Class representing a transform of an entity
    """

    def __init__(
        self,
        position: Vec3f = Vec3f.zero,
        rotation: Union[Quaternion, Vec3f] = Quaternion(),
        scale: Vec3f = Vec3f.one
    ):
        self.translation = position
        if isinstance(rotation, Quaternion):
            self.rotation = rotation
        else:
            self.rotation = Quaternion.from_euler(rotation)
        self.scale = scale

    @property
    def right(self) -> Vec3f:
        return self.rotation * Vec3f.right

    @right.setter
    def right(self, vec: Vec3f):
        self.rotation = Quaternion.from_to_rotation(Vec3f.right, vec)

    @property
    def up(self) -> Vec3f:
        return self.rotation * Vec3f.up

    @up.setter
    def up(self, vec: Vec3f):
        self.rotation = Quaternion.from_to_rotation(Vec3f.up, vec)

    @property
    def forward(self) -> Vec3f:
        return self.rotation * Vec3f.forward

    @forward.setter
    def forward(self, vec: Vec3f):
        self.rotation.set_look_rotation(vec)

    @property
    def eulerRotation(self) -> Vec3f:
        return self.rotation.to_euler()

    @eulerRotation.setter
    def eulerRotation(self, rot: Vec3f):
        self.rotation = Quaternion.from_euler(rot)

    def to_matrix(self) -> Matrix44:
        mtx = Matrix44()
        translate = Matrix44.from_translation(self.translation)
        rotate = Matrix44.from_quaternion(self.rotation)
        scale = Matrix44.from_scale(self.scale)
        return mtx * translate * rotate * scale

    def translate(self, translation: Union[Vec3f, Tuple[float, float, float]]):
        """
        Translate this transform by `translation`
        """
        if isinstance(translation, Vec3f):
            self.translation += translation
        else:
            self.translation.x += translation[0]
            self.translation.y += translation[1]
            self.translation.z += translation[2]

    def rotate(self, eulers: Union[Vec3f, Tuple[float, float, float]]):
        """
        Rotate this transform by `eulers`
        """
        if isinstance(eulers, Vec3f):
            eulerRot = Quaternion.from_euler(eulers)
        else:
            eulerRot = Quaternion.from_euler(Vec3f(*eulers))
        rotation = self.rotation
        self.rotation = rotation * (rotation.inversed * eulerRot * rotation)

    def rotate_around(self, point: Vec3f, axis: Vec3f, angle: float):
        """
        Rotate this transform around `point` along `axis` in world space by `angle` degrees
        """
        quat = Quaternion.from_angle_axis(angle, axis)
        dif = quat * (self.translation - point)
        self.translation = point + dif

    def look_at(self, target: Union["Transform", Vec3f], worldUp: Vec3f = Vec3f.up):
        pos = target.translation if isinstance(target, Transform) else target
        target.rotation.set_look_rotation(pos, worldUp)
