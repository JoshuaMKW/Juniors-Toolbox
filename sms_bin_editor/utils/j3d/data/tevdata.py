from dataclasses import dataclass

from sms_bin_editor.utils.gx.color import Color

@dataclass
class TevStageInfo:
    colorIn: Color
    colorOp: int