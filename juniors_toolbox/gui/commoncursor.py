from enum import Enum
from PySide2.QtCore import QSize, Qt
from PySide2.QtGui import QCursor, QPixmap

from juniors_toolbox.utils.filesystem import resource_path

class CommonCursor(str, Enum):
    COLOR_PICKER = "gui/cursors/color_picker.png"

def get_common_cursor(cursor: CommonCursor, size: QSize = QSize(20, 20)) -> QCursor:
    cursorPix = QPixmap(str(resource_path(cursor.value)))
    cursorScaledPix = cursorPix.scaled(size, Qt.KeepAspectRatio)

    return QCursor(cursorScaledPix, -1, -1)