from io import BytesIO
import sys
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, TextIO

from sms_bin_editor.objects.object import GameObject

class SMSScene():
    BIN_PARAM_PATH = Path("Parameters")

    def __init__(self):
        self.reset()

    @classmethod
    def from_bytes(cls, data: BinaryIO) -> "SMSScene":
        _startPos = data.tell()

        data.seek(0, 2)
        end = data.tell()

        data.seek(_startPos, 0)

        this = cls()
        while data.tell() < end:
            this._objects.append(GameObject.from_bytes(data))

        return this

    def reset(self):
        self._objects = []

    def dump(self, out: Optional[TextIO] = None, indentwidth: int = 2):
        for obj in self.iter_objects():
            obj.print_map(out, 0, indentwidth)

    def iter_objects(self) -> Iterable[GameObject]:
        for obj in self._objects:
            yield obj