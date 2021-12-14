from PySide2.QtCore import QPoint
from PySide2.QtGui import QScreen
from PySide2.QtWidgets import QLayout

from sms_bin_editor.objects.types import ColorRGBA

def clear_layout(layout: QLayout):
    if layout is not None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
            elif child.layout() is not None:
                clear_layout(child.layout())

def get_screen_pixel_color(pos: QPoint) -> ColorRGBA:
    from PIL import ImageGrab

    px = ImageGrab.grab().load()
    print(pos)
    return ColorRGBA.from_tuple(px[pos.x(), pos.y()])
