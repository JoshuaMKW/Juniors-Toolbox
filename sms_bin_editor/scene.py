from pathlib import Path

class SMSScene():
    BIN_PARAM_PATH = Path("Parameters")

    def __init__(self):
        self.reset()

    @classmethod
    def from_bin(self, bin: Path) -> "SMSScene":
        ...

    def reset(self):
        self.objects = []

    