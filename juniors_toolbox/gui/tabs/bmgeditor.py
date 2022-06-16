import time
from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Union

from juniors_toolbox.gui import ToolboxManager
from juniors_toolbox.gui.widgets import ABCWidget
from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.gui.widgets.interactivestructs import (
    InteractiveListView, InteractiveListWidget, InteractiveListWidgetItem)
from juniors_toolbox.gui.widgets.listinterface import ListInterfaceWidget
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.bmg import BMG, RichMessage, SoundID
from juniors_toolbox.utils.filesystem import resource_path
from juniors_toolbox.utils.iohelper import decode_raw_string
from PySide6.QtCore import (QByteArray, QDataStream, QIODevice, QMimeData, QRegularExpression,
                            QModelIndex, QObject, QPersistentModelIndex,
                            QPoint, QRect, QSize, QSortFilterProxyModel, Qt,
                            Signal, Slot)
from PySide6.QtGui import (QAction, QColor, QFont, QImage, QIntValidator,
                           QMouseEvent, QPainter, QPainterPath, QPaintEvent,
                           QPolygon, QStandardItem, QStandardItemModel,
                           QTextCursor, QTransform)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLineEdit, QMenu, QMenuBar,
                               QPlainTextEdit, QPushButton, QSizePolicy,
                               QSplitter, QVBoxLayout, QWidget)


class ButtonCB(ABC):
    def __init__(self, position: QPoint, cb: Callable[[], None]):
        self._position = position
        self._rotation = 0.0
        self._scale = 1.0
        self._cb = cb

    def position(self) -> QPoint:
        return self._position

    def set_position(self, position: QPoint):
        self._position = position

    def rotation(self) -> float:
        return self._rotation

    def set_rotation(self, rotation: float):
        self._rotation = rotation

    @abstractmethod
    def render_(self, painter: QPainter): ...

    @abstractmethod
    def contains(self, point: QPoint) -> bool: ...

    def translate(self, x: int, y: int):
        self._position.setX(
            self._position.x() + x
        )
        self._position.setY(
            self._position.y() + y
        )

    def rotate(self, degrees: float):
        self._rotation += degrees

    def scale(self, scale: float):
        self._scale *= scale

    def exec(self):
        self._cb()


class CircleButton(ButtonCB):
    def __init__(self, position: QPoint, radius: int, cb: Callable[[], None]):
        super().__init__(position, cb)
        self._radius = radius

    def render_(self, painter: QPainter):
        painter.save()
        radius = self._radius * self._scale
        painter.drawEllipse(self._position, radius, radius)
        painter.drawPoint(self._position)
        painter.restore()

    def contains(self, point: QPoint) -> bool:
        diff = point - self._position
        radius = self._radius * self._scale
        return QPoint.dotProduct(diff, diff) < radius * radius


class RectangleButton(ButtonCB):
    def __init__(self, rect: QRect, cb: Callable[[], None]):
        super().__init__(rect.topLeft(), cb)
        self._size = rect.size()

    def render_(self, painter: QPainter):
        rect = QRect(self._position, self._size*self._scale)
        center = rect.center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self._rotation)
        transform.translate(-center.x(), -center.y())
        poly = transform.mapToPolygon(rect)

        painter.save()
        painter.drawPolyline(poly)
        painter.drawPoint(center)
        painter.restore()

    def contains(self, point: QPoint) -> bool:
        rect = QRect(self._position, self._size*self._scale)
        center = rect.center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self._rotation)
        transform.translate(-center.x(), -center.y())
        poly = transform.mapToPolygon(rect)
        return poly.containsPoint(point, Qt.WindingFill)


class PolygonButton(ButtonCB):
    def __init__(self, polygon: QPolygon, cb: Callable[[], None]):
        super().__init__(QPoint(0, 0), cb)
        self._polygon = polygon

    def translate(self, x: int, y: int):
        self._polygon.translate(x, y)

    def render_(self, painter: QPainter):
        center = self._polygon.boundingRect().center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.scale(self._scale, self._scale)
        transform.rotate(self._rotation)
        transform.translate(-center.x(), -center.y())
        poly = transform.map(self._polygon)

        painter.save()
        painter.drawPolyline(poly)
        painter.drawPoint(center)
        painter.restore()

    def contains(self, point: QPoint) -> bool:
        center = self._polygon.boundingRect().center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.scale(self._scale, self._scale)
        transform.rotate(self._rotation)
        transform.translate(-center.x(), -center.y())
        poly = transform.map(self._polygon)
        return poly.containsPoint(point, Qt.WindingFill)


class BMGMessageView(QObject, ABCWidget):
    FontSize = 15
    PaddingMap = {
        " ": 4,
        "c": 2,
        "l": 2,
        "u": 1,
        "y": 1,
        ",": 6,
    }

    startRequested = Signal()
    stopRequested = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    @staticmethod
    def get_color(index: int) -> QColor:
        return [
            QColor(0xFF, 0xFF, 0xFF, 0xFF),
            QColor(0xFF, 0xFF, 0xFF, 0xFF),
            QColor(0xFF, 0xB4, 0x8C, 0xFF),
            QColor(0x6E, 0xE6, 0xFF, 0xFF),
            QColor(0xFF, 0xFF, 0x00, 0xFF),
            QColor(0xAA, 0xFF, 0x50, 0xFF)
        ][index]

    @staticmethod
    def get_fruit(index: int) -> int:
        return [3, 3, 3, 3][index]

    @staticmethod
    def get_record(index: int) -> str:
        return [
            "00:30:00",
            "00:35:00",
            "30",
            "1",
            "",
            "",
            "00:40:00",
        ][index]

    @abstractmethod
    def render_(self, painter: QPainter, message: RichMessage,
                currentPage: int) -> List[ButtonCB]: ...

    @abstractmethod
    def get_end_page(self, message: RichMessage) -> int: ...

    @abstractmethod
    def get_message_for_page(self, message: RichMessage,
                             page: int) -> RichMessage: ...

    @abstractmethod
    def get_message_backdrop(self) -> QImage: ...

    def set_current_frame(self, frame: int):
        self._frame = frame

    def get_current_frame(self) -> int:
        return self._frame

    def get_num_newlines(self, message: RichMessage) -> int:
        num = 0
        for cmp in message.components:
            if isinstance(cmp, str):
                num += cmp.count("\n")
        return num

    def get_text_width(self, painter: QPainter, text: str) -> int:
        fontMetrics = painter.fontMetrics()
        charWidth = 0
        for char in text:
            # type: ignore
            charWidth += fontMetrics.horizontalAdvanceChar(char)
            if char in self.PaddingMap:
                charWidth += self.PaddingMap[char]
        return charWidth

    def _render_text(self, painter: QPainter, text: str, path: Optional[QPainterPath] = None, newLineHBuffer: int = 0) -> QSize:
        text = text.replace("\x00", "")
        if text == "":
            return QSize(0, 0)

        pathLerp = 0.0
        fontMetrics = painter.fontMetrics()
        textWidths = []
        lineWidth = 0
        charWidth = 0
        textHeight = fontMetrics.height()
        painter.save()
        for char in text:
            if char == "\n":
                textWidths.append(lineWidth)
                lineWidth = 0
                height = fontMetrics.height() + newLineHBuffer
                textHeight += height
                painter.translate(0, height)
            if path:
                plen = path.length()
                self._render_char_on_path(
                    painter,
                    char,
                    path,
                    pathLerp
                )
                pathLerp += charWidth / plen
                lineWidth += charWidth
            else:
                charWidth = fontMetrics.horizontalAdvanceChar(char)
                if char in self.PaddingMap:
                    charWidth += self.PaddingMap[char]
                painter.drawText(0, 0, char)
                painter.translate(charWidth, 0)
                lineWidth += charWidth
        painter.restore()
        textWidths.append(lineWidth)
        return QSize(max(textWidths), textHeight)

    def _render_char_on_path(self, painter: QPainter, char: str, path: QPainterPath, lerp: float) -> int:
        if lerp > 1.0:
            return 0

        fontMetrics = painter.fontMetrics()

        point = path.pointAtPercent(lerp)
        angle = path.angleAtPercent(lerp)

        charWidth = fontMetrics.horizontalAdvanceChar(char)  # type: ignore
        if char in self.PaddingMap:
            charWidth += self.PaddingMap[char]

        painter.save()
        # Move the virtual origin to the point on the curve
        painter.translate(point)
        # Rotate to match the angle of the curve
        # Clockwise is positive so we negate the angle from above
        painter.rotate(-angle)
        # Draw a line width above the origin to move the text above the line
        # and let Qt do the transformations
        painter.drawText(QPoint(0, 0), char)
        painter.restore()

        return charWidth


class BMGMessageViewNPC(BMGMessageView):
    TextSpacingScale = 0.00382544309832  # from SMS
    BoxAppearSpeed = 0.04  # from SMS - 0 to 1 range
    TextWaitInverseScale = 1.0  # from SMS
    Rotation = 17.0  # from SMS, clockwise
    BgOpacity = 0.75

    pageRequested = Signal(int)

    class PreviewState(IntEnum):
        IDLE = 0
        SCROLLING = 4
        WAITING = 5
        CLOSE = 6
        NEXTMSG = 7

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._rightAligned = True

    def is_right_aligned(self) -> bool:
        return self._rightAligned

    def set_right_aligned(self, ra: bool):
        self._rightAligned = ra

    def get_lines_per_page(self) -> int:
        return 3

    def get_end_page(self, message: RichMessage) -> int:
        numLines = self.get_num_newlines(message)
        return numLines // self.get_lines_per_page()

    def get_message_for_page(self, message: RichMessage, page: int) -> RichMessage:
        components = []

        linesPerPage = self.get_lines_per_page()
        startIndex = linesPerPage * page

        newlines = 0
        for component in message.components:
            if isinstance(component, str):
                cmpNewLines = 0
                substr = ""
                for char in component:
                    index = (newlines + cmpNewLines) - startIndex

                    if char == "\n":
                        cmpNewLines += 1

                    if index < 0:
                        continue

                    substr += char
                    if (linesPerPage + startIndex) - (newlines + cmpNewLines) <= 0:
                        components.append(substr)
                        return RichMessage(components)
                if substr != "":
                    components.append(substr)
                newlines += cmpNewLines
            else:
                if newlines - startIndex < 0:
                    continue
                components.append(component)
        return RichMessage(components)

    def get_message_backdrop(self) -> QImage:
        return QImage(
            str(
                resource_path("gui/images/message_back.png")
            )
        )

    def is_next_button_visible(self, message: RichMessage, currentPage: int) -> bool:
        numLines = self.get_num_newlines(message)
        numPages = (numLines // self.get_lines_per_page()) + 1
        return currentPage < numPages-1

    def is_end_button_visible(self, message: RichMessage, currentPage: int) -> bool:
        numLines = self.get_num_newlines(message)
        numPages = (numLines // self.get_lines_per_page()) + 1
        return currentPage == numPages-1

    def render_(self, painter: QPainter, message: RichMessage, currentPage: int) -> List[ButtonCB]:
        font = QFont("FOT-PopHappiness Std EB")
        font.setPointSize(self.FontSize)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.scale(2.28, 2.27)

        numLines = self.get_num_newlines(message)
        numPages = self.get_end_page(message) + 1

        if currentPage >= numPages:
            currentPage = 0

        message = self.get_message_for_page(message, currentPage)

        buttons = self._render_message(
            painter, message, currentPage
        )
        return buttons

    def _render_message(self, painter: QPainter, message: RichMessage, currentPage: int) -> list[ButtonCB]:
        def next_line(painter: QPainter, lineImg: QImage):
            painter.translate(0, 33)
            painter.setOpacity(self.BgOpacity)
            painter.drawImage(0, 0, lineImg)
            painter.setOpacity(1.0)

        painter.save()

        backDrop = self.get_message_backdrop()

        pathLerp = 0.0
        path = QPainterPath(QPoint(24, 41))
        path.cubicTo(
            QPoint(backDrop.width() // 3, 16),
            QPoint(backDrop.width() - (backDrop.width() // 3), 16),
            QPoint(backDrop.width() - 16, 50)
        )
        plen = path.length()

        if self.is_right_aligned():
            painter.translate(100, -33)
            rotation = self.Rotation
        else:
            painter.translate(0, 63)
            rotation = -self.Rotation - 4
        painter.rotate(rotation)

        next_line(painter, backDrop)  # Render first line

        lastChar = ""
        queueLine = False
        queueSize = 0
        options = {}
        for component in message.components:
            if isinstance(component, bytes):
                if component.startswith(b"\x1A\x06\xFF\x00\x00"):
                    color = self.get_color(component[-1])
                    painter.setPen(color)
                elif component.startswith(b"\x1A\x06\x02\x00\x04"):
                    if lastChar == "\n" and queueLine:
                        for _ in range(queueSize):
                            next_line(painter, backDrop)
                        queueLine = False
                        queueSize = 0
                    fruitNum = str(self.get_fruit(component[-1]))
                    for char in fruitNum:
                        charWidth = self._render_char_on_path(
                            painter, char, path, pathLerp)
                        pathLerp += charWidth / plen
                        lastChar = char
                elif component.startswith(b"\x1A\x05\x02\x00"):
                    if lastChar == "\n" and queueLine:
                        for _ in range(queueSize):
                            next_line(painter, backDrop)
                        queueLine = False
                        queueSize = 0
                    text = self.get_record(component[-1])
                    for char in text:
                        charWidth = self._render_char_on_path(
                            painter, char, path, pathLerp)
                        pathLerp += charWidth / plen
                        lastChar = char
                elif component[2:4] == b"\x01\x00":
                    string = decode_raw_string(component[5:])
                    if component[4] not in options:
                        options[component[4]] = string
                continue

            line = component.replace("\x00", "")
            if line == "":
                continue

            lines = 1
            for char in line:
                if char == "\n" and lastChar != "\n":
                    queueLine = True
                    queueSize = 1
                    pathLerp = 0.0
                    lines += 1
                    lastChar = char
                    continue
                if lastChar == "\n" and queueLine:
                    if char == "\n":
                        queueSize += 1
                        continue
                    for _ in range(queueSize):
                        next_line(painter, backDrop)
                    queueLine = False
                    queueSize = 0

                charWidth = self._render_char_on_path(
                    painter, char, path, pathLerp)
                pathLerp += charWidth / plen

                lastChar = char

        buttonImg = QImage(27, 27, QImage.Format_ARGB32)
        buttonImg.fill(Qt.transparent)


        # /- RENDER BUTTONS -/ #
        buttonPainter = QPainter()
        buttonPainter.begin(buttonImg)

        buttons: list[ButtonCB] = []
        targetPos = QPoint(backDrop.width() - 5, 39)

        if self.is_next_button_visible(message, currentPage):
            self._render_next_button(buttonPainter)
        else:
            self._render_end_button(buttonPainter)

        buttonPainter.end()

        transform = QTransform()
        transform.rotate(-70)
        buttonImg = buttonImg.transformed(transform, Qt.SmoothTransformation)

        painter.save()
        painter.setOpacity(1.0)
        painter.drawImage(targetPos, buttonImg)
        painter.restore()

        # /- CALCULATE PROGRESSION BUTTON -/ #

        centerOfs = buttonImg.rect().width() // 2
        transform = painter.combinedTransform()
        buttonAbsPos = transform.map(
            QPoint(
                targetPos.x() + centerOfs,
                targetPos.y() + centerOfs+1
            )
        )

        buttons.append(
            CircleButton(
                buttonAbsPos,
                30,
                lambda: self.pageRequested.emit(
                    currentPage + 1
                )
            )
        )

        if len(options) == 0:
            painter.restore()
            return buttons

        # /- CALCULATE OPTION BUTTONS -/ #

        optionsImgSize = QSize(112, 76)
        targetPos = QPoint(
            (backDrop.width() // 2) - (optionsImgSize.width() // 2),
            36
        )

        optionsImg = QImage(optionsImgSize, QImage.Format_ARGB32)
        optionsImg.fill(Qt.transparent)

        optionsPainter = QPainter()
        optionsPainter.begin(optionsImg)
        optionsPainter.setFont(painter.font())
        optionsPainter.setPen(Qt.white)
        buttonRects = self._render_options_button(optionsPainter, options)
        optionsPainter.end()

        painter.save()
        painter.setOpacity(1.0)
        painter.drawImage(targetPos, optionsImg)
        painter.restore()

        for buttonRect in buttonRects:
            buttonRect.translate(targetPos)
            rect = transform.mapRect(buttonRect)
            button = RectangleButton(
                rect,
                lambda: self.pageRequested.emit(0)
            )
            button.set_rotation(rotation)
            buttons.append(button)

        painter.restore()
        return buttons

    def _render_next_button(self, painter: QPainter):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )
        arrowImg = QImage(
            str(resource_path("gui/images/message_cursor.png"))
        )
        painter.save()
        painter.setOpacity(self.BgOpacity)
        painter.drawImage(0, 0, nextImg)
        painter.setOpacity(1.0)
        painter.drawImage(5, 7, arrowImg)
        painter.restore()

    def _render_end_button(self, painter: QPainter):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )

        returnImg = QImage(
            str(resource_path("gui/images/message_return.png"))
        )
        painter.save()
        painter.setOpacity(self.BgOpacity)
        painter.drawImage(0, 0, nextImg)
        painter.setOpacity(1.0)
        painter.drawImage(5, 5, returnImg)
        painter.restore()

    def _render_options_button(self, painter: QPainter, options: Dict[int, str]) -> List[QRect]:
        buttonPositions = []
        backImg = QImage(
            str(resource_path("gui/images/message_option_back.png"))
        )
        painter.save()
        painter.setOpacity(self.BgOpacity)
        painter.drawImage(0, 0, backImg)
        painter.setOpacity(1.0)
        yPos = 34
        for index, option in options.items():
            if index > 1:
                continue
            optionPos = QPoint(
                39, yPos + (index * 25)
            )
            painter.save()
            painter.translate(optionPos)
            buttonSize = self._render_text(painter, option)
            buttonSize.setHeight(int(buttonSize.height() * 0.5))
            buttonPos = QPoint(
                optionPos.x(),
                optionPos.y() - buttonSize.height()
            )
            buttonPositions.append(
                QRect(buttonPos, buttonSize)
            )
            painter.restore()
        painter.restore()
        return buttonPositions


class BMGMessageViewBillboard(BMGMessageViewNPC):
    def get_lines_per_page(self) -> int:
        return 6

    def get_message_backdrop(self) -> QImage:
        return QImage(
            str(
                resource_path("gui/images/message_board.png")
            )
        )

    def _render_message(self, painter: QPainter, message: RichMessage, currentPage: int) -> List[ButtonCB]:
        font = QFont("FOT-PopHappiness Std EB")
        font.setPointSize(self.FontSize)
        painter.setFont(font)
        painter.setPen(Qt.white)

        backDrop = self.get_message_backdrop()

        painter.save()

        painter.rotate(-10)
        painter.setOpacity(self.BgOpacity)
        painter.translate(0, 100)
        painter.drawImage(0, 0, backDrop)
        painter.setOpacity(1.0)

        painter.save()
        painter.translate(0, 20)

        lines = message.get_string().split("\n")
        for line in lines:
            line = line.replace("\x00", "")
            painter.translate(0, 32)
            painter.save()
            lineWidth = self.get_text_width(painter, line)
            painter.translate((backDrop.width() - lineWidth) / 2, 0)
            self._render_text(painter, line)
            painter.restore()
        painter.restore()

        buttonImg = QImage(27, 27, QImage.Format_ARGB32)
        buttonImg.fill(Qt.transparent)

        buttonPainter = QPainter()
        buttonPainter.begin(buttonImg)

        if self.is_next_button_visible(message, currentPage):
            self._render_next_button(buttonPainter)
        else:
            self._render_end_button(buttonPainter)

        buttonPainter.end()

        targetPos = QPoint(int(backDrop.width() / 2.15), backDrop.height() + 5)
        painter.drawImage(targetPos, buttonImg)

        transform = painter.combinedTransform()
        painter.restore()

        buttonAbsPos = transform.map(
            QPoint(
                targetPos.x() + 13,
                targetPos.y() + 13
            )
        )
        return [
            CircleButton(
                buttonAbsPos,
                30,
                lambda: self.pageRequested.emit(
                    currentPage + 1
                )
            )
        ]


class BMGMessageViewDEBS(BMGMessageView):
    def render_(self, painter: QPainter, message: RichMessage, currentPage: int) -> List[ButtonCB]:
        debsRect = QRect(0, 0, 500, 80)
        debsShadowRect = debsRect.translated(10, 10)

        painter.setBackground()
        painter.drawRoundedRect(
            debsShadowRect, 5, 5
        )

        font = QFont("FOT-PopHappiness Std EB")
        font.setPointSize(self.FontSize)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.scale(2.6, 3.0)

        lines = message.get_string().split("\n")
        for line in lines:
            line = line.replace("\x00", "")
            painter.save()
            lineWidth = self.get_text_width(painter, line)
            painter.translate(-(lineWidth / 2), 0)
            self._render_text(painter, line)
            painter.restore()

        return []


class BMGMessageViewStage(BMGMessageView):
    def render_(self, painter: QPainter, message: RichMessage, currentPage: int) -> List[ButtonCB]:
        painter.translate(1920 / 2, 66)

        font = QFont("FOT-PopHappiness Std EB")
        font.setPointSize(self.FontSize)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.scale(2.6, 3.0)

        lines = message.get_string().split("\n")
        if len(lines) == 0:
            return []

        lineWidth = self.get_text_width(painter, lines[0])
        painter.translate(-(lineWidth / 2), 0)

        for line in lines:
            self._render_text(painter, line.replace("\x00", ""))

        return []


class BMGMessagePreviewWidget(QWidget):
    class BoxState(IntEnum):
        NPC = 0
        BILLBOARD = 1
        DEBS = 2
        STAGENAME = 3

    class BackGround(str, Enum):
        PIANTA = "shades_pianta"
        TANOOKI = "tanooki"
        NOKI = "old_noki"
        # STAGE = "stage_select"

    def __init__(self, message: RichMessage = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 113)
        if message is None:
            message = RichMessage()
        self._message = message
        self._background: Optional[Path] = None
        self._playing = False
        self._curFrame = -1
        self._endFrame = -1
        self._curPage = 0
        self._boxState = BMGMessagePreviewWidget.BoxState.NPC
        self._buttons: List[ButtonCB] = []
        self._is_right_bound = True

        self.npcRenderer = BMGMessageViewNPC()
        self.npcRenderer.pageRequested.connect(self.set_page)
        self.billboardRenderer = BMGMessageViewBillboard()
        self.billboardRenderer.pageRequested.connect(self.set_page)
        self.debsRenderer = BMGMessageViewDEBS()
        self.stagenameRenderer = BMGMessageViewStage()

        self.renderers: dict[BMGMessagePreviewWidget.BoxState, BMGMessageView] = {
            BMGMessagePreviewWidget.BoxState.NPC: self.npcRenderer,
            BMGMessagePreviewWidget.BoxState.BILLBOARD: self.billboardRenderer,
            BMGMessagePreviewWidget.BoxState.DEBS: self.debsRenderer,
            BMGMessagePreviewWidget.BoxState.STAGENAME: self.stagenameRenderer,
        }

        self.set_background(
            BMGMessagePreviewWidget.BackGround.PIANTA
        )

    @property
    def message(self) -> RichMessage:
        return self._message

    @message.setter
    def message(self, message: RichMessage):
        self._message = message

    @property
    def boxState(self) -> BoxState:
        return self._boxState

    @boxState.setter
    def boxState(self, state: BoxState):
        self._boxState = state

    def get_background(self) -> QImage:
        if self._background is None:
            return QImage()
        if self.is_stage_name():
            return QImage(
                str(
                    resource_path("gui/backgrounds/") /
                    "bmg_preview_stage_select.png"
                )
            )
        return QImage(str(self._background))

    def set_background(self, bg: BackGround):
        bgFolder = resource_path("gui/backgrounds/")
        for file in bgFolder.iterdir():
            if not file.name.startswith("bmg_preview_"):
                continue
            if not file.is_file():
                continue
            if file.stem.removeprefix("bmg_preview_") == bg.value:
                self._background = file.resolve()

    def is_anim_playing(self) -> bool:
        return self._playing and self._curFrame > -1

    def is_npc(self) -> bool:
        return self._boxState == BMGMessagePreviewWidget.BoxState.NPC

    def is_billboard(self) -> bool:
        return self._boxState == BMGMessagePreviewWidget.BoxState.BILLBOARD

    def is_debs(self) -> bool:
        return self._boxState == BMGMessagePreviewWidget.BoxState.DEBS

    def is_stage_name(self) -> bool:
        return self._boxState == BMGMessagePreviewWidget.BoxState.STAGENAME

    def is_right_aligned(self) -> bool:
        return self.npcRenderer.is_right_aligned()

    def set_right_aligned(self, raligned: bool):
        self.npcRenderer.set_right_aligned(raligned)

    def set_page(self, page: int):
        renderer = self.renderers[self._boxState]
        endPage = renderer.get_end_page(self._message)

        self._curPage = page
        if page > endPage:
            self._curPage = 0
        elif page < 0:
            self._curPage = 0

    def nextPage(self):
        self._curPage += 1

    def prevPage(self):
        self._curPage -= 1

    def play(self):
        self._playing = True
        if self._curFrame == -1:
            self._curFrame = 0

    def pause(self):
        self._playing = False

    def stop(self):
        self._playing = False
        self._curFrame = -1
        self._curPage = 0

    def reset(self):
        self.stop()

    def initPainter(self, painter: QPainter):
        super().initPainter(painter)
        self._renderTimer = time.perf_counter()

    def render_(self, painter: QPainter):
        def fit_image_to(widget: QWidget, img: QImage) -> QImage:
            wFactor = widget.width() / img.width()
            hFactor = widget.height() / img.height()
            if wFactor < hFactor:
                scaledImg = img.smoothScaled(
                    int(img.width() * wFactor),
                    int(img.height() * wFactor)
                )
            else:
                scaledImg = img.smoothScaled(
                    int(img.width() * hFactor),
                    int(img.height() * hFactor)
                )
            return scaledImg

        painter.save()

        painter.fillRect(0, 0, self.width(), self.height(),
                         QColor(0, 0, 0, 255))

        backgroundImg = self.get_background()

        if self.message.get_rich_text() == "":
            scaledBGImg = fit_image_to(self, backgroundImg)
            painter.drawImage(
                (self.width() // 2) - (scaledBGImg.width() // 2),
                (self.height() // 2) - (scaledBGImg.height() // 2),
                scaledBGImg
            )
            painter.restore()
            return

        encoding = self.message.encoding
        if encoding is None:
            encoding = "shift-jis"

        _len = 0
        curComponent = None
        for cmp in self.message.components:
            if isinstance(cmp, str):
                size = len(cmp.encode(encoding))
            else:
                size = len(cmp)

            if _len < self._curFrame < _len + size:
                curComponent = cmp
                break

        if curComponent is None:
            self._curFrame = -1

        self._buttons.clear()

        msgImage = QImage(1920, 1080, QImage.Format_ARGB32)
        msgImage.fill(Qt.transparent)

        msgPainter = QPainter()
        msgPainter.begin(msgImage)

        buttons = self.renderers[self._boxState].render_(
            msgPainter, self.message, self._curPage
        )

        msgPainter.end()

        if self.is_npc():
            if self.is_right_aligned():
                messageImgOfs = QPoint(635, 5)
            else:
                messageImgOfs = QPoint(210, 53)
        elif self.is_billboard():
            messageImgOfs = QPoint(470, 30)
        elif self.is_debs():
            messageImgOfs = QPoint(210, 800)
        elif self.is_stage_name():
            messageImgOfs = QPoint(0, 760)

        mainPainter = QPainter()
        mainPainter.begin(backgroundImg)
        mainPainter.drawImage(messageImgOfs, msgImage)
        mainPainter.end()

        scaledBGImg = fit_image_to(self, backgroundImg)

        imgOfs = QPoint(
            (self.width() // 2) - (scaledBGImg.width() // 2),
            (self.height() // 2) - (scaledBGImg.height() // 2)
        )

        painter.drawImage(imgOfs, scaledBGImg)

        # Set Button Callback

        if len(buttons) == 0:
            painter.restore()
            return

        for button in buttons:
            wFactor = self.width() / backgroundImg.width()
            hFactor = self.height() / backgroundImg.height()

            factor = min(wFactor, hFactor)

            button.set_position(
                QPoint(
                    int((messageImgOfs.x() + button.position().x()) * factor),
                    int((messageImgOfs.y() + button.position().y()) * factor)
                )
            )
            button.translate(imgOfs.x(), imgOfs.y())
            button.scale(factor)

            self._buttons.append(button)

        painter.restore()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter()
        painter.begin(self)

        self.render_(painter)
        if self._playing:
            self._curFrame += 1
            if self._curFrame > self._endFrame:
                self.stop()

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            ePos = event.pos()
            for button in self._buttons:
                if button.contains(ePos):
                    button.exec()
            else:
                self.update()


class BMGMessageItem(QStandardItem):
    _message: BMG.MessageEntry

    def __init__(self, other: Optional[BMG.MessageEntry] | Optional["BMGMessageItem"] = None):
        if isinstance(other, BMGMessageItem):
            super().__init__(other)
            self._message = other._message.copy(deep=True)
            return

        super().__init__()

        self._message = BMG.MessageEntry("((null))")
        if other is None:
            return

        self._message = other

    def isAutoTristate(self) -> bool:
        return False

    def isCheckable(self) -> bool:
        return False

    def isDragEnabled(self) -> bool:
        return True

    def isDropEnabled(self) -> bool:
        return True

    def isEditable(self) -> bool:
        return True

    def isSelectable(self) -> bool:
        return True

    def isUserTristate(self) -> bool:
        return False

    def read(self, in_: QDataStream) -> None:
        name = in_.readString()

        rdata = QByteArray()
        in_ >> rdata

        richMessage = RichMessage.from_bytes(
            BytesIO(rdata)
        )
        if richMessage is None:
            raise ValueError("Invalid Rich Message")

        soundID = SoundID(in_.readUInt32())
        startFrame = in_.readInt32()
        endFrame = in_.readInt32()

        flagsData = QByteArray()
        in_ >> flagsData

        unkFlags = flagsData.data()

        message = BMG.MessageEntry(
            name,
            richMessage,
            soundID,
            startFrame,
            endFrame,
            unkFlags
        )
        self.setData(message)

    def write(self, out: QDataStream) -> None:
        message: BMG.MessageEntry = self.data()

        out.writeString(message.name)
        out << message.message.to_bytes()
        out.writeUInt32(message.soundID.value)
        out.writeInt32(message.startFrame)
        out.writeInt32(message.endFrame)
        out << message._unkflags

    def data(self, role: int = Qt.UserRole + 1) -> Any:
        if role == Qt.DisplayRole:
            return self._message.name

        if role == Qt.EditRole:
            return self._message.name

        elif role == Qt.SizeHintRole:
            return QSize(40, self.font().pointSize() * 2)

        elif role == Qt.UserRole + 1:
            return self._message

    def setData(self, value: Any, role: int = Qt.UserRole + 1) -> None:
        if role == Qt.DisplayRole:
            self._message.name = value

        if role == Qt.EditRole:
            self._message.name = value

        elif role == Qt.UserRole + 1:
            self._message = value

    def clone(self) -> "BMGMessageItem":
        return BMGMessageItem(self)


class BMGMessageListModel(QStandardItemModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setItemPrototype(BMGMessageItem())

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.CopyAction | Qt.MoveAction

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.CopyAction | Qt.MoveAction

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.UserRole + 1) -> Any:
        if section == 0:
            return "Messages"
        return None

    def itemData(self, index: Union[QModelIndex, QPersistentModelIndex]) -> dict[int, Any]:
        roles = {}
        for i in range(Qt.UserRole + 2):
            variant = self.data(index, i)
            if variant:
                roles[i] = variant
        return roles

    def mimeTypes(self) -> list[str]:
        return ["application/x-bmgmessagelist"]

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        mimeType = self.mimeTypes()[0]

        encodedData = data.data(mimeType)
        stream = QDataStream(
            encodedData,
            QIODevice.ReadOnly
        )

        itemCount = stream.readInt32()
        if action & Qt.CopyAction:
            for i in range(itemCount):
                item = BMGMessageItem()
                item.read(stream)
                item.setData(
                    self._resolve_name(item.data(Qt.DisplayRole)),
                    Qt.DisplayRole
                )
                self.insertRow(row + i, item)
        else:
            oldItems: list[BMGMessageItem] = []
            for i in range(itemCount):
                item = BMGMessageItem()
                item.read(stream)
                name = item.data(Qt.DisplayRole)
                oldItems.append(
                    self.findItems(name)[0]
                )
                self.insertRow(row + i, item)
            for item in oldItems:
                self.removeRow(item.row())

        return action == Qt.CopyAction

    def mimeData(self, indexes: list[int]) -> QMimeData:
        mimeType = self.mimeTypes()[0]
        mimeData = QMimeData()

        encodedData = QByteArray()
        stream = QDataStream(
            encodedData,
            QIODevice.WriteOnly
        )

        stream.writeInt32(len(indexes))
        for index in indexes:
            item = self.itemFromIndex(index)  # type: ignore
            item.write(stream)

        mimeData.setData(
            mimeType,
            encodedData
        )
        return mimeData

    def _resolve_name(self, name: str, filterItem: Optional[QStandardItem] = None) -> str:
        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.rowCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = self.item(i)
            if item == filterItem:
                continue
            itemText: str = item.data(Qt.DisplayRole)
            if itemText.startswith(ogName):
                possibleNames.append(itemText)

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        return name


class BMGMessageFilterModel(QSortFilterProxyModel):
    def lessThan(self, source_left: Union[QModelIndex, QPersistentModelIndex], source_right: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        messageLeft: BMG.MessageEntry = source_left.data(Qt.UserRole + 1)
        messageRight: BMG.MessageEntry = source_right.data(Qt.UserRole + 1)

        return messageLeft.name < messageRight.name

    def filterAcceptsRow(self, source_row: int, source_parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        model: BMGMessageListModel = self.sourceModel()
        item = model.item(source_row)
        if item is None:
            return False
        message: BMG.MessageEntry = item.data(Qt.UserRole + 1)

        regexp = self.filterRegularExpression()
        pattern = regexp.pattern()
        regexpMatch = regexp.match(message.message.get_rich_text())
        return regexpMatch.hasMatch()


class BMGMessageListView(InteractiveListView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(150, 100)


class BMGMessageInterfaceWidget(QWidget):
    attributeUpdateRequested = Signal(str, int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setFixedHeight(100)

        layout = QVBoxLayout()

        soundIdLayout = QFormLayout()

        soundIdComboBox = QComboBox()
        soundIdComboBox.setEditable(False)
        for sound in SoundID._member_names_:
            soundIdComboBox.addItem(sound)
        soundIdComboBox.setCurrentIndex(0)
        soundIdComboBox.currentIndexChanged.connect(self._push_update_request)
        self._soundIdComboBox = soundIdComboBox

        soundIdLayout.addRow("Sound ID:", self._soundIdComboBox)

        startFrameLayout = QFormLayout()

        startFrameLineEdit = QLineEdit()
        startFrameLineEdit.setText("0")
        startFrameLineEdit.setValidator(QIntValidator(0, 65535))
        startFrameLineEdit.textChanged.connect(self._push_update_request)
        self._startFrameLineEdit = startFrameLineEdit

        startFrameLayout.addRow("Start Frame:", self._startFrameLineEdit)

        endFrameLayout = QFormLayout()

        endFrameLineEdit = QLineEdit()
        endFrameLineEdit.setText("0")
        endFrameLineEdit.setValidator(QIntValidator(0, 65535))
        endFrameLineEdit.textChanged.connect(self._push_update_request)
        self._endFrameLineEdit = endFrameLineEdit

        endFrameLayout.addRow("End Frame: ", self._endFrameLineEdit)

        layout.addLayout(soundIdLayout)
        layout.addLayout(startFrameLayout)
        layout.addLayout(endFrameLayout)

        self.setLayout(layout)

    def set_values(self, soundID: SoundID, startFrame: int, endFrame: int):
        startFrame = min(startFrame, 65535)
        endFrame = min(endFrame, 65535)
        index = self._soundIdComboBox.findText(
            soundID.name, Qt.MatchFixedString
        )
        index = max(0, index)
        self._soundIdComboBox.setCurrentIndex(index)
        self._startFrameLineEdit.setText(str(startFrame))
        self._endFrameLineEdit.setText(str(endFrame))

    def blockSignals(self, b: bool) -> bool:
        blocked = super().blockSignals(b)
        blocked |= self._soundIdComboBox.blockSignals(b)
        blocked |= self._startFrameLineEdit.blockSignals(b)
        blocked |= self._endFrameLineEdit.blockSignals(b)
        return blocked

    @Slot()
    def _push_update_request(self):
        soundName = self._soundIdComboBox.currentText()

        text = self._startFrameLineEdit.text()
        if text == "":
            startFrame = 0
        else:
            startFrame = min(int(self._startFrameLineEdit.text()), 65535)

        text = self._endFrameLineEdit.text()
        if text == "":
            endFrame = 0
        else:
            endFrame = min(int(self._endFrameLineEdit.text()), 65535)

        self.attributeUpdateRequested.emit(soundName, startFrame, endFrame)


class BMGMessagePreviewStateWidget(QWidget):
    bgUpdateRequested = Signal(str)
    boxChangeRequested = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(150, 100)

        layout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.WrapAllRows)

        comboBox = QComboBox()
        for bg in BMGMessagePreviewWidget.BackGround._member_names_:
            name = bg.replace("_", " ").title()
            comboBox.addItem(name)
        comboBox.currentIndexChanged.connect(
            lambda idx: self.bgUpdateRequested.emit(
                comboBox.itemText(idx))
        )
        self.comboBox = comboBox

        stateComboBox = QComboBox()
        stateComboBox.addItems(
            [
                "NPC",
                "Board",
                "DEBS"
            ]
        )
        stateComboBox.currentIndexChanged.connect(self.boxChangeRequested.emit)

        self.stateComboBox = stateComboBox

        layout.addRow("Background", comboBox)
        layout.addRow(stateComboBox)

        self.setLayout(layout)


class BMGMessageTextBox(QPlainTextEdit):
    class CmdAction(QAction):
        clicked = Signal(str)

        def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self._click)

        def _click(self):
            subname = self.text()
            parent: QMenu = self.parent()
            if parent:
                category = parent.title()
            self.clicked.emit("{" + category.lower() + ":" + subname + "}")

    class SpeedCmdAction(QAction):
        clicked = Signal(str)

        def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self._click)

        def _click(self):
            self.clicked.emit("{speed:0}")

    class OptionCmdAction(QAction):
        clicked = Signal(str)

        def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self._click)

        def _click(self):
            self.clicked.emit("{option:0:}")

    class RawCmdAction(QAction):
        clicked = Signal(str)

        def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self._click)

        def _click(self):
            self.clicked.emit("{raw:0x}")

    def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
        super().__init__(*args, **kwargs)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setMinimumSize(130, 100)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self.context_menu)

    @Slot(QPoint)
    def context_menu(self, point: QPoint):
        menu = self.createStandardContextMenu(point)

        categories: Dict[str, list] = {}
        for rich in RichMessage._RICH_TO_COMMAND:
            category, specifier = rich[1:-1].split(":")
            items: List[str] = categories.setdefault(category, [])
            items.append(specifier)

        menu.addSection("Formatters")

        optionAction = BMGMessageTextBox.OptionCmdAction("New Option", menu)
        optionAction.clicked.connect(self.insert_format_token)

        speedAction = BMGMessageTextBox.SpeedCmdAction("Speed", menu)
        speedAction.clicked.connect(self.insert_format_token)

        menu.addAction(optionAction)
        menu.addAction(speedAction)

        if len(categories) > 0:
            menu.addSeparator()
            for category, items in categories.items():
                submenu = QMenu(category.capitalize(), menu)
                for item in items:
                    action = BMGMessageTextBox.CmdAction(item, submenu)
                    action.clicked.connect(
                        self.insert_token
                    )
                    submenu.addAction(action)
                menu.addMenu(submenu)

        menu.addSeparator()

        rawAction = BMGMessageTextBox.RawCmdAction("Raw", menu)
        rawAction.clicked.connect(self.insert_format_token)

        menu.addAction(rawAction)

        menu.exec(self.mapToGlobal(point))

    @Slot(str)
    def insert_token(self, token: str):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        self.blockSignals(True)
        if "color" in token and abs(end - start) > 1:
            textToWrap = cursor.selectedText()
            resetToken = "{color:white}"
            targetPos = min(start, end)
            cursor.removeSelectedText()
            cursor.setPosition(targetPos, QTextCursor.MoveAnchor)
            cursor.insertText(token + textToWrap + resetToken)
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(
                textToWrap) + len(resetToken))
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.setTextCursor(cursor)
        elif "text:slow" in token and abs(end - start) > 1:
            textToWrap = cursor.selectedText()
            resetToken = "{speed:0}"
            targetPos = min(start, end)
            cursor.removeSelectedText()
            cursor.setPosition(targetPos, QTextCursor.MoveAnchor)
            cursor.insertText(token + textToWrap + resetToken)
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(
                textToWrap) + len(resetToken))
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.setTextCursor(cursor)
        else:
            self.insertPlainText(token)
        self.blockSignals(False)
        self.textChanged.emit()

    @Slot(str)
    def insert_format_token(self, token: str):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        self.blockSignals(True)
        if "speed" in token and abs(end - start) > 1:
            textToWrap = cursor.selectedText()
            targetPos = min(start, end)
            cursor.removeSelectedText()
            cursor.setPosition(targetPos, QTextCursor.MoveAnchor)
            cursor.insertText(token + textToWrap + token)
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(
                textToWrap) + len(token) + 1)
            self.setTextCursor(cursor)
        else:
            self.insertPlainText(token)
            self.moveCursor(QTextCursor.Left, QTextCursor.MoveAnchor)
        self.blockSignals(False)
        self.textChanged.emit()


class BMGMessageMenuBar(QMenuBar):
    newRequested = Signal()
    openRequested = Signal()
    closeRequested = Signal()
    saveRequested = Signal(bool)

    packetSizeUpdated = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setNativeMenuBar(False)
        self.setFixedHeight(28)

        fileMenu = QMenu(self)
        fileMenu.setTitle("File")

        newAction = QAction(self)
        newAction.setText("New")
        newAction.triggered.connect(lambda toggled: self.newRequested.emit())

        openAction = QAction(self)
        openAction.setText("Open...")
        openAction.triggered.connect(lambda toggled: self.openRequested.emit())

        saveAction = QAction(self)
        saveAction.setText("Save")
        saveAction.triggered.connect(
            lambda toggled: self.saveRequested.emit(False))

        saveAsAction = QAction(self)
        saveAsAction.setText("Save As...")
        saveAsAction.triggered.connect(
            lambda toggled: self.saveRequested.emit(True))

        closeAction = QAction(self)
        closeAction.setText("Close")
        closeAction.triggered.connect(
            lambda toggled: self.closeRequested.emit())

        fileMenu.addAction(newAction)
        fileMenu.addAction(openAction)
        fileMenu.addSeparator()
        fileMenu.addAction(saveAction)
        fileMenu.addAction(saveAsAction)
        fileMenu.addSeparator()
        fileMenu.addAction(closeAction)

        kindMenu = QMenu(self)
        kindMenu.setTitle("Region")

        usaAction = QAction(kindMenu)
        usaAction.setText("NTSC-U")
        usaAction.setCheckable(True)
        usaAction.setChecked(True)

        palAction = QAction(kindMenu)
        palAction.setText("PAL")
        palAction.setCheckable(True)

        usaAction.toggled.connect(
            lambda toggled: palAction.setChecked(not toggled)
        )
        palAction.toggled.connect(
            lambda toggled: usaAction.setChecked(not toggled)
        )
        self._usaAction = usaAction
        self._palAction = palAction

        kindMenu.addAction(usaAction)
        kindMenu.addAction(palAction)

        sizeMenu = QMenu(self)
        sizeMenu.setTitle("Packet Size")

        sizeAction4 = QAction(sizeMenu)
        sizeAction4.setText("4 (System)")
        sizeAction4.setCheckable(True)
        sizeAction4.toggled.connect(
            lambda toggled: self.set_packet_size(4)
        )

        sizeAction8 = QAction(sizeMenu)
        sizeAction8.setText("8 (Unknown)")
        sizeAction8.setCheckable(True)
        sizeAction8.toggled.connect(
            lambda toggled: self.set_packet_size(8)
        )

        sizeAction12 = QAction(sizeMenu)
        sizeAction12.setText("12 (NPC)")
        sizeAction12.setCheckable(True)
        sizeAction12.setChecked(True)
        sizeAction12.toggled.connect(
            lambda toggled: self.set_packet_size(12)
        )
        self._sizeAction4 = sizeAction4
        self._sizeAction8 = sizeAction8
        self._sizeAction12 = sizeAction12

        sizeMenu.addAction(sizeAction4)
        sizeMenu.addAction(sizeAction8)
        sizeMenu.addAction(sizeAction12)

        self.addMenu(fileMenu)
        self.addMenu(kindMenu)
        self.addMenu(sizeMenu)

    def is_region_pal(self) -> bool:
        return self._palAction.isChecked() and not self._usaAction.isChecked()

    def set_region_pal(self, isPal: bool):
        self._palAction.setChecked(isPal)
        self._usaAction.setChecked(not isPal)

    def set_packet_size(self, size: int):
        self._sizeAction4.blockSignals(True)
        self._sizeAction8.blockSignals(True)
        self._sizeAction12.blockSignals(True)
        if size == 4:
            self._sizeAction4.setChecked(True)
            self._sizeAction8.setChecked(False)
            self._sizeAction12.setChecked(False)
        elif size == 8:
            self._sizeAction4.setChecked(False)
            self._sizeAction8.setChecked(True)
            self._sizeAction12.setChecked(False)
        elif size == 12:
            self._sizeAction4.setChecked(False)
            self._sizeAction8.setChecked(False)
            self._sizeAction12.setChecked(True)
        self._sizeAction4.blockSignals(False)
        self._sizeAction8.blockSignals(False)
        self._sizeAction12.blockSignals(False)
        self.packetSizeUpdated.emit(size)

    def get_packet_size(self) -> int:
        if self._sizeAction4.isChecked():
            return 4
        if self._sizeAction8.isChecked():
            return 8
        if self._sizeAction12.isChecked():
            return 12
        return 12


class BMGMessageEditorWidget(A_DockingInterface):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(685, 300)

        self.mainWidget = QWidget()

        self.mainLayout = QVBoxLayout()
        self.mainLayout.setContentsMargins(10, 0, 10, 10)

        messageListFilter = QLineEdit()
        messageListFilter.setPlaceholderText(" *Search for text here*")
        messageListFilter.textChanged.connect(self.set_message_filter)
        self.messageListFilter = messageListFilter

        self.messageListModel = BMGMessageListModel()

        messageFilterModel = BMGMessageFilterModel()
        messageFilterModel.setSourceModel(self.messageListModel)
        self.messageFilterModel = messageFilterModel

        messageListBox = BMGMessageListView()
        messageListBox.setModel(messageFilterModel)
        messageListBox.selectionModel().currentChanged.connect(self.show_message)
        self.messageListBox = messageListBox

        messageListInterface = ListInterfaceWidget()
        messageListInterface.addRequested.connect(self.new_message)
        messageListInterface.removeRequested.connect(
            self.remove_selected_message)
        messageListInterface.copyRequested.connect(self.copy_selected_message)
        self.messageListInterface = messageListInterface

        messageTextEdit = BMGMessageTextBox()
        messageTextEdit.setObjectName("Message Editor")
        messageTextEdit.setEnabled(False)
        messageTextEdit.textChanged.connect(self.update_message_text)
        self.messageTextEdit = messageTextEdit

        messageInterface = BMGMessageInterfaceWidget()
        messageInterface.setEnabled(False)
        messageInterface.attributeUpdateRequested.connect(
            self.update_message_attributes
        )
        self.messageInterface = messageInterface

        messagePreviewInterface = BMGMessagePreviewStateWidget()
        messagePreviewInterface.bgUpdateRequested.connect(
            self.set_background
        )
        messagePreviewInterface.boxChangeRequested.connect(
            self.set_state
        )
        self.messagePreviewInterface = messagePreviewInterface

        messageInterfaceLayoutline = QFrame()
        messageInterfaceLayoutline.setFrameShape(QFrame.VLine)
        messageInterfaceLayoutline.setFrameShadow(QFrame.Sunken)

        messageInterfaceLayout = QHBoxLayout()
        messageInterfaceLayout.addWidget(messageInterface)
        messageInterfaceLayout.addWidget(messageInterfaceLayoutline)
        messageInterfaceLayout.addWidget(messagePreviewInterface)
        messageInterfaceLayout.setContentsMargins(0, 0, 0, 0)

        messageInterfaceWidget = QWidget()
        messageInterfaceWidget.setLayout(messageInterfaceLayout)
        messageInterfaceWidget.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)

        messageListLayout = QVBoxLayout()
        messageListLayout.addWidget(messageListInterface)
        messageListLayout.addWidget(messageListFilter)
        messageListLayout.addWidget(messageListBox)
        messageListLayout.setContentsMargins(0, 0, 0, 0)

        messageListWidget = QWidget()
        messageListWidget.setLayout(messageListLayout)
        messageListWidget.setEnabled(False)
        self.messageListWidget = messageListWidget

        messageWidget = QWidget()
        self.messagePreview = BMGMessagePreviewWidget()
        self._prevPreviewState = BMGMessagePreviewWidget.BoxState.NPC

        messageSplitter = QSplitter()
        messageSplitter.setChildrenCollapsible(False)
        messageSplitter.addWidget(self.messageTextEdit)
        messageSplitter.addWidget(self.messagePreview)

        messageLayoutline = QFrame()
        messageLayoutline.setFrameShape(QFrame.HLine)
        messageLayoutline.setFrameShadow(QFrame.Sunken)

        messageLayout = QVBoxLayout()
        messageLayout.addWidget(messageInterfaceWidget)
        messageLayout.addWidget(messageLayoutline)
        messageLayout.addWidget(messageSplitter)
        messageLayout.setContentsMargins(0, 0, 0, 0)

        messageWidget = QWidget()
        messageWidget.setLayout(messageLayout)
        self.messageWidget = messageWidget

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(messageListWidget)
        splitter.addWidget(messageWidget)
        self.splitter = splitter

        menuBar = BMGMessageMenuBar(self)
        menuBar.newRequested.connect(self.new_bmg)
        menuBar.openRequested.connect(self.open_bmg)
        menuBar.closeRequested.connect(self.close_bmg)
        menuBar.saveRequested.connect(
            lambda saveAs: self._save_bmg_as(saveAs=saveAs))
        self.menuBar = menuBar
        menuBar.packetSizeUpdated.connect(self.update_is_stagename)

        self.mainLayout.addWidget(self.menuBar)
        self.mainLayout.addWidget(self.splitter)

        self.mainWidget.setLayout(self.mainLayout)
        self.setWidget(self.mainWidget)

        self.messages: List[BMG.MessageEntry] = []

        self._cachedOpenPath: Optional[Path] = None

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs):
        data: BinaryIO = args[0]
        if not isinstance(data, BMG):
            return

        self.messageListBox.clear()
        self.messageTextEdit.blockSignals(True)
        self.messageTextEdit.clear()
        self.messageTextEdit.blockSignals(False)

        self.menuBar.set_region_pal(data.is_str1_present())
        self.menuBar.set_packet_size(data.flagSize)

        for i, message in enumerate(data.iter_messages()):
            if message.name == "":
                message.name = f"message_unk_{i}"
            self.set_message(i, message)

        model = self.messageListModel
        if model.rowCount() > 0:
            self.messageListBox.setCurrentIndex(
                model.index(0, 0)
            )

        self.messageListWidget.setEnabled(True)

    def get_message(self, index: QModelIndex) -> Optional[BMG.MessageEntry]:
        item: Optional[BMGMessageItem] = self.messageListModel.item(
            self.messageFilterModel.mapToSource(index).row()
        )
        if item is None:
            return None
        return item.data(Qt.UserRole + 1)

    def set_message(self, row: int, message: BMG.MessageEntry):
        self.messageListModel.setItem(row, BMGMessageItem(message))

    @Slot()
    def new_bmg(self):
        self.populate(BMG(self.menuBar.is_region_pal(), 12))
        self.messageListWidget.setEnabled(True)

    @Slot(Path)
    def open_bmg(self, path: Optional[Path] = None):
        if path is None:
            dialog = QFileDialog(
                parent=self,
                caption="Open BMG...",
                directory=str(
                    self._cachedOpenPath.parent if self._cachedOpenPath else Path.home()
                ),
                filter="Binary Messages (*.bmg);;All files (*)"
            )

            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setFileMode(QFileDialog.AnyFile)

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self._cachedOpenPath = path

        with path.open("rb") as f:
            bmg = BMG.from_bytes(f)

        manager = ToolboxManager.get_instance()
        self.populate(manager.get_scene(), bmg)

    @Slot()
    def close_bmg(self):
        self.messageListBox.clear()
        self.messageTextEdit.clear()
        self.messagePreview.stop()
        self.messagePreview.message = None
        self.messageInterface.set_values(
            SoundID(0), 0, 0
        )
        self.messageTextEdit.setEnabled(False)
        self.messageInterface.setEnabled(False)
        self.messageListWidget.setEnabled(False)

    @Slot(Path)
    def save_bmg(self, path: Optional[Path] = None):
        dialog = QFileDialog(
            parent=self,
            caption="Save BMG...",
            directory=str(
                self._cachedOpenPath.parent if self._cachedOpenPath else Path.home()
            ),
            filter="Binary Messages (*.bmg);;All files (*)"
        )

        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setFileMode(QFileDialog.AnyFile)

        if path is None:
            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self._cachedOpenPath = path

        bmg = BMG(self.menuBar.is_region_pal(), self.menuBar.get_packet_size())

        model = self.messageListModel
        for row in range(model.rowCount()):
            item: BMGMessageItem = model.item(row)
            bmg.add_message(item.data())

        with path.open("wb") as f:
            f.write(bmg.to_bytes())

    @Slot(bool)
    def _save_bmg_as(self, saveAs: bool):
        if saveAs:
            self.save_bmg()
        else:
            self.save_bmg(self._cachedOpenPath)

    @Slot(QModelIndex, QModelIndex)
    def show_message(self, index: QModelIndex, previous: QModelIndex):
        message = self.get_message(index)
        if message is None or message.name == "":
            self.messageTextEdit.clear()
            self.messageTextEdit.setDisabled(True)
            self.messageInterface.blockSignals(True)
            self.messageInterface.set_values(
                SoundID.NOTHING, 0, 0
            )
            self.messageInterface.blockSignals(False)
            self.messageInterface.setDisabled(True)
            self.messagePreview.stop()
            self.messagePreview.message = RichMessage()
            return

        self.messageTextEdit.setPlainText(
            message.message.get_rich_text().replace("\x00", ""))
        self.messageInterface.blockSignals(True)
        self.messageInterface.set_values(
            message.soundID,
            message.startFrame,
            message.endFrame
        )
        self.messageInterface.blockSignals(False)
        self.messagePreview.message = message.message
        self.messagePreview.reset()
        self.messagePreview.update()
        self.messageTextEdit.setEnabled(True)
        self.messageInterface.setEnabled(True)

    @Slot()
    def new_message(self):
        model = self.messageListModel
        row = model.rowCount()

        name = self.messageListBox._resolve_name("message")
        message = BMG.MessageEntry(name)

        self.messageListBox.blockSignals(True)
        self.set_message(row, message)
        self.messageListBox.blockSignals(False)
        # self.messageListBox.edit(model.index(row, 0))

    @Slot()
    def remove_selected_message(self):
        model = self.messageListModel
        model.removeRow(
            self.messageListBox.currentIndex().row()
        )

    @Slot()
    def copy_selected_message(self):
        self.messageListBox.duplicate_items(
            [
                self.messageListModel.item(
                    self.messageListBox.currentIndex()
                )
            ]
        )

    @Slot()
    def update_message_text(self):
        index = self.messageListBox.currentIndex()
        if not index.isValid():
            self.messagePreview.update()
            return

        message = self.get_message(index)

        message.message = RichMessage.from_rich_string(
            self.messageTextEdit.toPlainText())

        # self.messageListModel.dataChanged.emit(
        #     index,
        #     index,
        #     [Qt.UserRole + 1]
        # )

        self.messagePreview.message = message.message
        self.messagePreview.update()

    @Slot(str, int, int)
    def update_message_attributes(self, soundName: str, startFrame: int, endFrame: int):
        message = self.get_message(
            self.messageListBox.currentIndex()
        )
        if message is None:
            return

        message.soundID = SoundID.name_to_sound_id(soundName)
        message.startFrame = startFrame
        message.endFrame = endFrame

    @Slot(int)
    def update_is_stagename(self, packetSize: int):
        if packetSize == 4:
            self._prevPreviewState = self.messagePreview.boxState
            self.messagePreview.boxState = BMGMessagePreviewWidget.BoxState.STAGENAME
        else:
            self.messagePreview.boxState = self._prevPreviewState

    @Slot()
    def set_message_filter(self):
        self.messageFilterModel.setFilterRegularExpression(
            QRegularExpression(
                QRegularExpression.escape(self.messageListFilter.text()),
                QRegularExpression.CaseInsensitiveOption
            )
        )

    @Slot(int)
    def set_state(self, index: int):
        if self.messagePreview.is_stage_name():
            self._prevPreviewState = BMGMessagePreviewWidget.BoxState(index)
        else:
            self.messagePreview.boxState = BMGMessagePreviewWidget.BoxState(
                index)
        self.messagePreview.update()

    @Slot(str)
    def set_background(self, bgname: str):
        bg = BMGMessagePreviewWidget.BackGround._member_map_[bgname.upper()]
        self.messagePreview.set_background(bg)
        self.messagePreview.set_right_aligned(
            bg != BMGMessagePreviewWidget.BackGround.NOKI)
