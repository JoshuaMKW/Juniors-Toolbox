from enum import IntEnum, auto
from typing import List, Tuple
from io import BytesIO

from sms_bin_editor.objects.types import Vec3f


class JUTTransparency(IntEnum):
    OPAQUE = 0
    CLIP = auto()
    TRANSLUCENT = auto()


class TextureData():
    def __init__(
        self,
        name: str,
        width: int,
        height: int,
        format,
        transparency: JUTTransparency = JUTTransparency.OPAQUE,
        paletteFormat: int = 0,
        minLOD: int = 0,
        maxLOD: int = 0
    ):
        self.name = name
        self.width = width
        self.height = height
        self.format = format
        self.transparency = transparency,
        self.paletteFormat = paletteFormat,
        self.minLOD = minLOD
        self.maxLOD = maxLOD
        self.imageCount = 1
        self.paletteNum = 0
        self.paletteOfs = 0

        self.data = BytesIO()