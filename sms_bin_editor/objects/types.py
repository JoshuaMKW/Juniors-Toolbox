import math
from typing import Optional, Tuple, Union
from enum import Enum, IntEnum

from math import acos, asin, atan2, cos, degrees, pi, radians, sin, sqrt
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
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-2])")
        return self.tuple()[index]

    def __setitem__(self, index: int, value: int) -> int:
        if index not in range(4):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-2])")
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

    @property
    def components(self) -> Tuple[float, float, float]:
        return self.x, self.y, self.z

    def set(self, x: float, y: float, z: float):
        """
        Set all the components of this Vector3f
        """
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

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
        normalized = self.normalized
        self.x = normalized.x
        self.y = normalized.y
        self.z = normalized.z

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
        if isinstance(other, Vec3f):
            return Vec3f(
                self.x * other.x,
                self.y * other.y,
                self.z * other.z
            )
        return Vec3f(
            self.x * other,
            self.y * other,
            self.z * other
        )

    def __truediv__(self, other: Union[float, "Vec3f"]) -> "Vec3f":
        if isinstance(other, Vec3f):
            return Vec3f(
                self.x / other.x,
                self.y / other.y,
                self.z / other.z
            )
        return Vec3f(
            self.x / other,
            self.y / other,
            self.z / other
        )

    def __next__(self) -> float:
        if self.__iteridx > 2:
            self.__iteridx = 0
            raise StopIteration
        self.__iteridx += 1
        return self[self.__iteridx-1]

    def __getitem__(self, index: int) -> float:
        if index not in range(3):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-2])")
        return super().__getitem__(index)

    def __setitem__(self, index: int, value: float):
        if index not in range(3):
            raise IndexError(
                f"Index into {self.__class__.__name__} is out of range ([0-2])")
        super().__setitem__(index, value)

    def __len__(self) -> float:
        return self.magnitude

    def __str__(self) -> str:
        x = self.x
        y = self.y
        z = self.z
        return f"{self.__class__.__name__}({x=}, {y=}, {z=})"


class Quaternion():
    """
    Class representing a quaternion rotation
    """
    Epsilon = 0.000001

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        w: float = 1
    ):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.w = float(w)

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
        quat = Quaternion(self.x, self.y, self.z, self.w)
        scale = 1.0 / self.magnitude
        quat.xyz *= scale
        quat.w *= scale
        return quat

    @property
    def inversed(self) -> "Quaternion":
        quat = Quaternion(self.x, self.y, self.z, self.w)
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
    def from_euler(cls, euler: Vec3f) -> "Quaternion":
        """
        Create a rotation from `euler` (Unity style)
        """
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
                degrees(atan2(2*quat.x*quat.w + 2*quat.y*quat.z, 1 - 2*(quat.z*quat.z+quat.w*quat.w))),
                degrees(asin(2*(quat.x*quat.z - quat.w*quat.y))),
                degrees(atan2(2*quat.x*quat.y + 2*quat.z*quat.w, 1 - 2*(quat.yz*quat.y+quat.z*quat.z)))
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
                self.w*other.x + self.x*other.w + self.y*other.z - self.z*other.y,
                self.w*other.y + self.y*other.w + self.z*other.x - self.x*other.z,
                self.w*other.z + self.z*other.w + self.x*other.y - self.y*other.x,
                self.w*other.w - self.x*other.x - self.y*other.y - self.z*other.z,
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
        self.position = position
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

    def translate(self, translation: Union[Vec3f, Tuple[float, float, float]]):
        """
        Translate this transform by `translation`
        """
        if isinstance(translation, Vec3f):
            self.position += translation
        else:
            self.position.x += translation[0]
            self.position.y += translation[1]
            self.position.z += translation[2]

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
        dif = quat * (self.position - point)
        self.position = point + dif

    def look_at(self, target: Union["Transform", Vec3f], worldUp: Vec3f = Vec3f.up):
        pos = target.position if isinstance(target, Transform) else target
        target.rotation.set_look_rotation(pos, worldUp)