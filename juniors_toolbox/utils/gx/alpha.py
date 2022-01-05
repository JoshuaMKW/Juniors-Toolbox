from dataclasses import dataclass


@dataclass
class ConstantAlpha:
    enabled: bool = False
    value: int = 0