from pathlib import Path
from typing import Union
from build.lib.sms_bin_editor.objects.object import GameObject

from build.lib.sms_bin_editor.scene import SMSScene


class GenericTabWidget():
    def populate(self, data: Union[SMSScene, GameObject], scenePath: Path): ...

    def __del__(self): ...