from pathlib import Path
from typing import Union
from juniors_toolbox.objects.object import GameObject

from juniors_toolbox.scene import SMSScene


class GenericTabWidget():
    def populate(self, data: Union[SMSScene, GameObject], scenePath: Path): ...

    def __del__(self): ...