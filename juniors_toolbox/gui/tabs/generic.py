from pathlib import Path
from typing import Any


class GenericTabWidget():
    def populate(self, data: Any, scenePath: Path): ...

    def __del__(self): ...