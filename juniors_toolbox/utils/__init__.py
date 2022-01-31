from abc import ABC, abstractmethod
from typing import BinaryIO


JSYSTEM_PADDING_TEXT = "This is padding data to alignment....."


# pylint: disable=invalid-name
class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()
# pylint: enable=invalid-name


clamp = lambda x, min, max: min if x < min else max if x > max else x
clamp01 = lambda x: clamp(x, 0, 1)
sign = lambda x: 1 if x >= 0 else -1


def write_jsystem_padding(f: BinaryIO, multiple: int):
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)

    diff = next_aligned - f.tell()

    for i in range(diff):
        pos = i % len(JSYSTEM_PADDING_TEXT)
        f.write(JSYSTEM_PADDING_TEXT[pos:pos+1])
        

class Serializable(ABC):
    """
    Interface that ensures compatibility with generic object streaming
    """
    @classmethod
    @abstractmethod
    def from_bytes(cls, data: BinaryIO, *args, **kwargs): ...
    
    @abstractmethod
    def to_bytes(self) -> bytes: ...
