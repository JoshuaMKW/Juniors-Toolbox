from dataclasses import dataclass

from juniors_toolbox.utils.gx.color import Color

@dataclass
class TevStageInfo:
    colorIn: Color
    colorOp: int