import sys
from pathlib import Path
from typing import List, Optional, Tuple

from juniors_toolbox.gui.application import JuniorsToolbox
from juniors_toolbox import __version__
from juniors_toolbox.utils.bintemplate import convert_bin_to_toolbox

def main(argv: Optional[List[str]] = None):
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
