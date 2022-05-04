from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Type, TypeVar, Union


JSYSTEM_PADDING_TEXT = "This is padding data to alignment....."

_T = TypeVar("_T")


class classproperty(property):
    def __get__(self, __obj: Any, __type: type | None = None) -> Any:
        return classmethod(self.fget).__get__(None, __type)() # type: ignore


Numeric = Union[int, float]
VariadicArgs = Any
VariadicKwargs = Any

clamp: Callable[[Numeric, Numeric, Numeric],
                Numeric] = lambda x, min, max: min if x < min else max if x > max else x
clamp01: Callable[[Numeric], Numeric] = lambda x: clamp(x, 0, 1)
sign: Callable[[Numeric], Numeric] = lambda x: 1 if x >= 0 else -1


def write_jsystem_padding(f: BinaryIO, multiple: int) -> None:
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)

    diff = next_aligned - f.tell()

    for i in range(diff):
        pos = i % len(JSYSTEM_PADDING_TEXT)
        f.write(JSYSTEM_PADDING_TEXT[pos:pos+1].encode())


class A_Serializable(ABC):
    """
    Interface that ensures compatibility with generic object streaming
    """
    @classmethod
    @abstractmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **
                   kwargs: VariadicKwargs) -> Optional[A_Serializable]: ...

    @abstractmethod
    def to_bytes(self) -> bytes: ...


class A_Clonable(ABC):
    """
    Interface that ensures this object supports deep copying
    """
    @abstractmethod
    def copy(self, *, deep: bool = False) -> A_Clonable: ...
