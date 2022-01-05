import sys
from pathlib import Path
from typing import Optional, Tuple

from sms_bin_editor.gui.application import JuniorsToolbox
from sms_bin_editor import __version__

def main(argv: Optional[Tuple] = None):
    if argv is None:
        argv = sys.argv[1:]

    app = JuniorsToolbox()

    if len(argv) == 1:
        scenePath = Path(argv[0])
        if scenePath.name.lower() == "scene.bin" and scenePath.is_file():
            scenePath = scenePath.parent.parent
        print(scenePath)
        app.load_scene(scenePath)

    app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

#scene = SMSScene.from_bytes(open("scene.bin", "rb"))
#with open("scene_layout.log", "w", encoding="shift-jis") as f:
#    scene.dump(f)
