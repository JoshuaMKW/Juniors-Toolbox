from enum import Enum
from typing import Optional
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCursor, QIcon, QImage, QPixmap

from juniors_toolbox.utils.filesystem import resource_path

class CommonCursor(str, Enum):
    COLOR_PICKER = "gui/cursors/color_picker.png"

def get_common_cursor(cursor: CommonCursor, size: QSize = QSize(20, 20)) -> QCursor:
    cursorPix = QPixmap(str(resource_path(cursor.value)))
    cursorScaledPix = cursorPix.scaled(size, Qt.KeepAspectRatio)

    return QCursor(cursorScaledPix, -1, -1)

def get_image(filename: str, size: Optional[QSize] = None) -> QImage:
    image = QImage(str(resource_path("gui/images/" + filename)))
    if size:
        return image.scaled(size)
    return image

def get_icon(filename: str) -> QIcon:
    icon = QIcon(str(resource_path("gui/icons/" + filename)))
    return icon