from io import BytesIO
from typing import BinaryIO, Optional
from juniors_toolbox.utils import A_Clonable, A_Serializable, VariadicArgs, VariadicKwargs

from juniors_toolbox.utils.iohelper import read_string, read_uint16, read_uint32, write_string, write_uint16


class NameRefCorruptedError(Exception):
    ...


def get_key_code(key: str, encoding: Optional[str] = None) -> int:
    """
    Encodes `key` using the JDrama algorithm, returning a code
    """
    key = str(key)
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


class NameRef(A_Serializable, A_Clonable):
    """
    Implements the NameRef logic into a str-like object
    """
    def __init__(self, nameref: str) -> None:
        self.__data = nameref

    def __hash__(self) -> int:
        return get_key_code(self.__data, "shift-jis")

    def __str__(self) -> str:
        return self.get_ref()

    def __len__(self) -> int:
        return len(self.encode())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            if hash(self.__data) != get_key_code(other):
                return False
            return super().__eq__(other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, str):
            if hash(self.__data) != get_key_code(other):
                return True
            return super().__ne__(other)
        return NotImplemented

    def get_ref(self) -> str:
        return self.__data

    def set_ref(self, nameref: str) -> None:
        self.__data = nameref
        
    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["NameRef"]:
        keycode = read_uint16(data)
        refLength = read_uint16(data)
        nameref = cls(read_string(data, maxlen=refLength-1))
        thisKeycode = hash(nameref)
        if thisKeycode != keycode:
            raise NameRefCorruptedError(
                f"NameRef \"{nameref}\" is corrupted! {thisKeycode} != {keycode}")
        return nameref

    def to_bytes(self) -> bytes:
        output = BytesIO()
        write_uint16(output, hash(self))
        write_uint16(output, len(self))
        output.write(self.encode())
        return output.getvalue()

    def encode(self, encoding: str = "shift-jis", errors: str = "strict") -> bytes:
        return self.__data.encode(encoding, errors)

    def copy(self, *, deep: bool = False) -> "NameRef":
        cls = self.__class__
        return cls(self.__data)

    def search(self, name: str) -> Optional["NameRef"]:
        if self == name:
            return self
        return None