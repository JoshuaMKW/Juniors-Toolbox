from io import BytesIO
from typing import BinaryIO, Optional
from juniors_toolbox.utils import A_Serializable

from juniors_toolbox.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16


class NameRefCorruptedError(Exception):
    ...


def get_key_code(key: str, encoding: Optional[str] = None) -> int:
    """
    Encodes `key` using the JDrama algorithm, returning a code
    """
    if encoding is None:
        data = key.encode()
    else:
        try:
            data = key.encode(encoding)
        except UnicodeEncodeError:
            data = key.encode()

    context = 0
    for char in data:
        context = char + (context * 3)
        if context > 0xFFFFFFFF:
            context -= 0x100000000
    return context & 0xFFFF


class NameRef(str, A_Serializable):
    """
    Implements the NameRef logic into a str-like object
    """

    def __hash__(self) -> int:
        return get_key_code(self, "shift-jis")

    def __eq__(self, other: str) -> bool:
        if hash(self) != get_key_code(other):
            return False
        return super().__eq__(other)

    def __ne__(self, other: str) -> bool:
        if hash(self) != get_key_code(other):
            return True
        return super().__ne__(other)

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args, **kwargs):
        keycode = read_uint16(data)
        nameref = cls(read_string(data))
        thisKeycode = hash(nameref)
        if thisKeycode != keycode:
            raise NameRefCorruptedError(
                f"NameRef \"{nameref}\" is corrupted! {thisKeycode} != {keycode}")

    def to_bytes(self) -> bytes:
        output = BytesIO()
        write_uint16(output, hash(self))
        write_string(output, self)
        return output.getvalue()

    def search(self, name: str) -> "NameRef":
        if self == name:
            return self
            