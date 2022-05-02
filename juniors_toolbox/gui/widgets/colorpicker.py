# ------------------------------------- #
#                                       #
# Modern Color Picker by Tom F.         #
# Version 1.3.0                         #
# made with Qt Creator & qtpy          #
#                                       #
# ------------------------------------- #

import colorsys

from PySide6.QtCore import (QPoint, QRegularExpression, Qt, QSize)
from PySide6.QtGui import QColor, QDragLeaveEvent, QIntValidator, QKeyEvent, QPaintEvent, QPainter, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (QDialog, QGraphicsDropShadowEffect, QLabel, QWidget)
from juniors_toolbox.gui.widgets.colorgrabber import ColorPickerDialog

from juniors_toolbox.gui.widgets.ui.img import *

from juniors_toolbox.gui.widgets.ui.ui_dark import Ui_ColorPicker as Ui_Dark
from juniors_toolbox.gui.widgets.ui.ui_dark_alpha import Ui_ColorPicker as Ui_Dark_Alpha
from juniors_toolbox.gui.widgets.ui.ui_light import Ui_ColorPicker as Ui_Light
from juniors_toolbox.gui.widgets.ui.ui_light_alpha import Ui_ColorPicker as Ui_Light_Alpha
from juniors_toolbox.utils.types import RGBA8
from juniors_toolbox.utils.filesystem import resource_path


class ColorPicker(QDialog):

    def _generic_paint_event(self, label: QLabel, event: QPaintEvent, prevColor: bool):
        fillpattern = QPixmap(str(resource_path("gui/backgrounds/transparent.png")))
        fillpattern = fillpattern.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio)
        """
        pen = QPen()
        pen.setBrush(QBrush(fillpattern))
        pen.setStyle(Qt.NoPen)
        """
        painter = QPainter()
        painter.begin(label)
        if prevColor:
            painter.setOpacity(1 - (self.lastcolor[3] / 255))
        else:
            painter.setOpacity(1 - (self.color[3] / 255))
        painter.drawTiledPixmap(label.rect(), fillpattern)
        painter.end()
        super().paintEvent(event)

    def __init__(self, lightTheme=False, useAlpha=False):
        super().__init__()

        self.usingAlpha = useAlpha

        # Call UI Builder function
        if useAlpha:
            if lightTheme:
                self.ui = Ui_Light_Alpha()
            else:
                self.ui = Ui_Dark_Alpha()
            self.ui.setupUi(self)
        else:
            if lightTheme:
                self.ui = Ui_Light()
            else:
                self.ui = Ui_Dark()
            self.ui.setupUi(self)

        # Make Frameless
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Color Picker")

        # Add DropShadow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(17)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(0)
        self.shadow.setColor(QColor(0, 0, 0, 150))
        self.ui.drop_shadow_frame.setGraphicsEffect(self.shadow)

        # Add color grabber screen
        self.color_grabber_screen = ColorPickerDialog(self)
        self.color_grabber_screen.colorChanged.connect(
            self.update_display_color)
        self.color_grabber_screen.colorPicked.connect(
            self.finalize_display_color)
        self.color_grabber_screen.colorDismissed.connect(
            self.dismiss_display_color)

        # Connect update functions
        intValidator = QIntValidator()
        intValidator.setRange(0, 255)
        hexRegexp = QRegularExpression("[0-9a-fA-F]{0,8}")
        hexValidator = QRegularExpressionValidator(hexRegexp)
        self.ui.hue.mouseMoveEvent = self.moveHueSelector
        self.ui.red.textChanged.connect(self.rgbChanged)
        self.ui.red.setValidator(intValidator)
        self.ui.green.textChanged.connect(self.rgbChanged)
        self.ui.green.setValidator(intValidator)
        self.ui.blue.textChanged.connect(self.rgbChanged)
        self.ui.blue.setValidator(intValidator)
        self.ui.hex.textChanged.connect(self.hexChanged)
        self.ui.hex.setValidator(hexValidator)
        if self.usingAlpha:
            self.ui.alpha.textChanged.connect(self.alphaChanged)

        # Connect window dragging functions
        self.ui.title_bar.mouseMoveEvent = self.moveWindow
        self.ui.title_bar.mousePressEvent = self.setDragPos
        self.ui.window_title.mouseMoveEvent = self.moveWindow
        self.ui.window_title.mousePressEvent = self.setDragPos

        # Connect selector moving function
        self.ui.black_overlay.mouseMoveEvent = self.moveSVSelector
        self.ui.black_overlay.mousePressEvent = self.moveSVSelector

        # Connect Ok|Cancel Button Box and X Button
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.ui.exit_btn.clicked.connect(self.reject)

        self.ui.color_picker.clicked.connect(self.useScreenCapture)
        if self.usingAlpha:
            self.ui.color_vis.paintEvent = lambda e: self._generic_paint_event(self.ui.color_vis, e, False)
            self.ui.lastcolor_vis.paintEvent = lambda e: self._generic_paint_event(self.ui.lastcolor_vis, e, True)

        self.lastcolor = (0, 0, 0, 255)
        self.color = (0, 0, 0, 255)
        self.alpha = 255

    # Main Function

    def getColor(self, lc=None):
        if not self.usingAlpha and len(lc) == 3:
            lc.append(255)
        if lc != None and self.usingAlpha:
            alpha = lc[3]
            self.setAlpha(alpha)
            self.alpha = alpha
        if lc == None:
            lc = self.lastcolor
        else:
            self.lastcolor = lc

        self.setRGBA(lc)
        self.rgbChanged()
        r, g, b, a = lc
        self.ui.lastcolor_vis.setStyleSheet(
            f"background-color: rgba({r},{g},{b},{a})")

        if self.exec_():
            self.lastcolor = self.hsv2rgba(self.color)
            return self.lastcolor

        else:
            return self.lastcolor

    # Update Functions

    def hsvChanged(self):
        h, s, v = (100 - self.ui.hue_selector.y() / 1.85,
                   (self.ui.selector.x() + 6) / 2.0, (194 - self.ui.selector.y()) / 2.0)
        r, g, b, a = self.hsv2rgba(h, s, v, self.alpha)
        self.color = (h, s, v, a)
        self.setRGBA((r, g, b, a))
        self.setHex(self.hsv2hex(self.color))
        self.ui.color_vis.setStyleSheet(f"background-color: rgba({r},{g},{b},{a})")
        self.ui.color_view.setStyleSheet(
            f"border-radius: 5px;background-color: qlineargradient(x1:1, x2:0, stop:0 hsl({h}%,100%,50%), stop:1 #fff);")

    def rgbChanged(self):
        r, g, b = self.i(self.ui.red.text()), self.i(
            self.ui.green.text()), self.i(self.ui.blue.text())
        cr, cg, cb = self.clampRGB((r, g, b))
        ca = self.i(self.ui.alpha.text())

        if r != cr or (r == 0 and self.ui.red.hasFocus()):
            self.setRGBA((cr, cg, cb, ca))
            self.ui.red.selectAll()
        if g != cg or (g == 0 and self.ui.green.hasFocus()):
            self.setRGBA((cr, cg, cb, ca))
            self.ui.green.selectAll()
        if b != cb or (b == 0 and self.ui.blue.hasFocus()):
            self.setRGBA((cr, cg, cb, ca))
            self.ui.blue.selectAll()

        self.color = self.rgba2hsv(cr, cg, cb, ca)
        self.setHSV(self.color)
        
        self.setHex(self.rgba2hex((cr, cg, cb, ca)))
        self.ui.color_vis.setStyleSheet(f"background-color: rgba({cr},{cg},{cb},{ca})")

    def hexChanged(self):
        hex = self.ui.hex.text()
        if len(hex) != 8:
            return
        r, g, b, a = self.hex2rgba(hex)
        self.color = self.hex2hsv(hex)
        self.alpha = a
        self.setHSV(self.color)
        self.setRGBA((r, g, b, a))
        self.ui.color_vis.setStyleSheet(f"background-color: rgba({r},{g},{b},{a})")

    def alphaChanged(self):
        alpha = self.i(self.ui.alpha.text())
        oldalpha = alpha
        if alpha < 0:
            alpha = 0
        if alpha > 255:
            alpha = 255
        if alpha != oldalpha or alpha == 0:
            self.ui.alpha.setText(str(alpha))
            self.ui.alpha.selectAll()
        self.color = (*self.color[:3], alpha)
        self.setHex(self.rgba2hex(self.hsv2rgba(self.color)))

    def useScreenCapture(self):
        self.color_grabber_screen.set_dismiss_color(RGBA8.from_tuple(
            [*self.hsv2rgba(self.color), int(self.ui.alpha.text())]))
        self.color_grabber_screen.reset()
        self.color_grabber_screen.show()
        self.color_grabber_screen.showFullScreen()

    def update_display_color(self, color: RGBA8):
        self.ui.red.setText(str(color.red))
        self.ui.green.setText(str(color.green))
        self.ui.blue.setText(str(color.blue))
        self.ui.alpha.setText("255")
        self.rgbChanged()

    def finalize_display_color(self, color: RGBA8):
        self.ui.red.setText(str(color.red))
        self.ui.green.setText(str(color.green))
        self.ui.blue.setText(str(color.blue))
        self.ui.alpha.setText("255")
        self.rgbChanged()

    def dismiss_display_color(self, color: RGBA8):
        self.ui.red.setText(str(color.red))
        self.ui.green.setText(str(color.green))
        self.ui.blue.setText(str(color.blue))
        self.ui.alpha.setText("255")
        self.rgbChanged()

    # Internal setting functions
    def setRGBA(self, c):
        r, g, b, a = c
        self.ui.red.setText(str(self.i(r)))
        self.ui.green.setText(str(self.i(g)))
        self.ui.blue.setText(str(self.i(b)))
        self.ui.alpha.setText(str(self.i(a)))

    def setHSV(self, c):
        self.ui.hue_selector.move(7, (100 - c[0]) * 1.85)
        self.ui.color_view.setStyleSheet(
            f"border-radius: 5px;background-color: qlineargradient(x1:1, x2:0, stop:0 hsl({c[0]}%,100%,50%), stop:1 #fff);")
        self.ui.selector.move(c[1] * 2 - 6, (200 - c[2] * 2) - 6)

    def setHex(self, c):
        self.ui.hex.setText(c.upper())

    def setAlpha(self, a):
        self.ui.alpha.setText(str(a))

    # Color Utility

    def hsv2rgba(self, h_or_color, s=0, v=0, a=None):
        if type(h_or_color).__name__ == "tuple":
            if len(h_or_color) == 4:
                h, s, v, a = h_or_color
            else:
                h, s, v = h_or_color
        else:
            h = h_or_color
        r, g, b = colorsys.hsv_to_rgb(h / 100.0, s / 100.0, v / 100.0)
        if a != None:
            return (r * 255, g * 255, b * 255, a)
        return (r * 255, g * 255, b * 255)

    def rgba2hsv(self, r_or_color, g=0, b=0, a=None):
        if type(r_or_color).__name__ == "tuple":
            if len(r_or_color) == 4:
                r, g, b, a = r_or_color
            else:
                r, g, b = r_or_color
        else:
            r = r_or_color
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if a != None:
            return (h * 100, s * 100, v * 100, a)
        return (h * 100, s * 100, v * 100)

    def hex2rgba(self, hex):
        if len(hex) < 6:
            hex += "0"*(6-len(hex))
        elif len(hex) == 8:
            return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4, 6))
        return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))

    def rgba2hex(self, r_or_color, g=0, b=0, a=255):
        if type(r_or_color).__name__ == "tuple":
            if len(r_or_color) == 3:
                r, g, b = r_or_color
            else:
                r, g, b, a = r_or_color
        else:
            r = r_or_color
        hex = '%02x%02x%02x%02x' % (int(r), int(g), int(b), int(a))
        return hex

    def hex2hsv(self, hex):
        return self.rgba2hsv(self.hex2rgba(hex))

    def hsv2hex(self, h_or_color, s=0, v=0, a=255):
        if type(h_or_color).__name__ == "tuple":
            
            if len(h_or_color) == 3:
                h, s, v = h_or_color
            else:
                h, s, v, a = h_or_color
        else:
            h = h_or_color
        return self.rgba2hex(*self.hsv2rgba(h, s, v), a)

    # Dragging Functions

    def setDragPos(self, event):
        self.dragPos = event.globalPos()

    def moveWindow(self, event):
        # MOVE WINDOW
        if event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self.dragPos)
            self.dragPos = event.globalPos()
            event.accept()

    def moveSVSelector(self, event):
        if event.buttons() == Qt.LeftButton:
            pos = event.pos()
            if pos.x() < 0:
                pos.setX(0)
            if pos.y() < 0:
                pos.setY(0)
            if pos.x() > 200:
                pos.setX(200)
            if pos.y() > 200:
                pos.setY(200)
            self.ui.selector.move(pos - QPoint(6, 6))
            self.hsvChanged()

    def moveHueSelector(self, event):
        if event.buttons() == Qt.LeftButton:
            pos = event.pos().y() - 7
            if pos < 0:
                pos = 0
            if pos > 185:
                pos = 185
            self.ui.hue_selector.move(QPoint(7, pos))
            self.hsvChanged()

    # Utility

    # Custom int() function, that converts uncastable strings to 0
    def i(self, text):
        try:
            return int(text)
        except:
            return 0

    # clamp function to remove near-zero values
    def clampRGB(self, rgb):
        r, g, b = rgb
        if r < 0.0001:
            r = 0
        if g < 0.0001:
            g = 0
        if b < 0.0001:
            b = 0
        if r > 255:
            r = 255
        if g > 255:
            g = 255
        if b > 255:
            b = 255
        return (r, g, b)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            return
        super().keyPressEvent(event);