from typing import Iterable, Union
from PySide6.QtCore import QPoint
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget

from juniors_toolbox.utils.types import RGBA8

def clear_layout(layout: QLayout):
    if layout is not None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
            elif child.layout() is not None:
                clear_layout(child.layout())

def walk_layout(layout: QLayout) -> Iterable[QLayoutItem]:
    if layout is not None:
        for i in range(layout.count()):
            child = layout.itemAt(i)
            yield child
            _widget = child.widget()
            _layout = child.layout()
            child = _widget.layout() if _widget is not None else _layout
            yield from walk_layout(child)

def get_screen_pixel_color(pos: QPoint) -> RGBA8:
    from PIL import ImageGrab

    px = ImageGrab.grab().load()
    return RGBA8.from_tuple(px[pos.x(), pos.y()])
