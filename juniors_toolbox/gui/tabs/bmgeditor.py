from audioop import add
import math
from msilib.schema import Billboard
import re
import time
from dataclasses import dataclass
from email.charset import QP
from enum import Enum, IntEnum
from pathlib import Path
from tkinter import font
from turtle import back
from typing import Any, Callable, Dict, List, Optional, Union

from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.gui.widgets.interactivelist import InteractiveListWidget, InteractiveListWidgetItem
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.bmg import BMG, RichMessage, SoundID
from juniors_toolbox.utils.filesystem import resource_path
from PySide6.QtCore import (QLine, QModelIndex, QObject, QPoint, QPointF,
                            QRect, QSizeF, Qt, QTimer, Signal, SignalInstance,
                            Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDragEnterEvent,
                           QDropEvent, QFont, QImage, QKeyEvent, QMouseEvent, QIntValidator,
                           QPainter, QPainterPath, QPaintEvent, QResizeEvent,
                           QTransform, QTextCursor)
from PySide6.QtWidgets import (QBoxLayout, QFileDialog, QFormLayout, QFrame, QCheckBox,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QListWidget, QComboBox,
                               QListWidgetItem, QMenu, QMenuBar,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QSpacerItem, QSplitter, QStyle,
                               QTextEdit, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QAbstractItemView)


class BMGMessagePreviewWidget(QWidget):
    TextSpacingScale = 0.00382544309832  # from SMS
    BoxAppearSpeed = 0.04  # from SMS - 0 to 1 range
    TextWaitInverseScale = 1.0  # from SMS
    Rotation = 17.0  # from SMS, clockwise
    FontSize = 15
    BgOpacity = 0.75
    PaddingMap = {
        " ": 4,
        "c": 2,
        "l": 2,
        "u": 1,
        "y": 1,
        ",": 6,
    }

    class PreviewState(IntEnum):
        IDLE = 0
        SCROLLING = 4
        WAITING = 5
        CLOSE = 6
        NEXTMSG = 7

    class BoxState(IntEnum):
        NPC = 0
        BILLBOARD = 1

    class BackGround(str, Enum):
        PIANTA = "shades_pianta"
        TANOOKI = "tanooki"
        NOKI = "old_noki"

    @dataclass
    class ButtonCB():
        position: QPoint = QPoint(0, 0)
        radius: float = 0.0
        cb: Callable[[], None] = lambda: None

        def render(self, painter: QPainter):
            painter.drawEllipse(self.position, self.radius, self.radius)

    def __init__(self, message: RichMessage = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.__message = message
        self.__background: QImage = None
        self.__playing = False
        self.__curFrame = -1
        self.__endFrame = -1
        self.__curPage = 0
        self.__renderTimer = 0.0
        self.__boxState = BMGMessagePreviewWidget.BoxState.NPC
        self.__buttons: List[BMGMessagePreviewWidget.ButtonCB] = []
        self.__is_right_bound = True

        self.set_background(
            BMGMessagePreviewWidget.BackGround.PIANTA
        )

    @property
    def message(self) -> RichMessage:
        return self.__message

    @message.setter
    def message(self, message: RichMessage):
        self.__message = message

    @property
    def boxState(self) -> BoxState:
        return self.__boxState

    @boxState.setter
    def boxState(self, state: BoxState):
        self.__boxState = state

    @property
    def linesPerPage(self) -> int:
        return 3 if self.__boxState == BMGMessagePreviewWidget.BoxState.NPC else 6

    @property
    def backDropImage(self) -> QImage:
        if self.__boxState == BMGMessagePreviewWidget.BoxState.NPC:
            return QImage(str(resource_path("gui/images/message_back.png")))
        else:
            return QImage(str(resource_path("gui/images/message_board.png")))

    def get_background(self) -> QImage:
        return QImage(self.__background)

    def set_background(self, bg: BackGround):
        bgFolder = resource_path("gui/backgrounds/")
        for file in bgFolder.iterdir():
            if not file.name.startswith("bmg_preview_"):
                continue
            if not file.is_file():
                continue
            if file.stem.removeprefix("bmg_preview_") == bg.value:
                self.__background = str(file.resolve())

    def is_playing(self) -> bool:
        return self.__playing and self.__curFrame > -1

    def is_next_button_visible(self) -> bool:
        numLines = self.__get_num_newlines(self.message)
        numPages = (numLines // self.linesPerPage) + 1
        return self.__curPage < numPages-1

    def is_end_button_visible(self) -> bool:
        numLines = self.__get_num_newlines(self.message)
        numPages = (numLines // self.linesPerPage) + 1
        return self.__curPage == numPages-1

    def is_billboard(self) -> bool:
        return self.__boxState == BMGMessagePreviewWidget.BoxState.BILLBOARD

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

    def is_right_aligned(self) -> bool:
        return self.__is_right_bound

    def set_right_aligned(self, raligned: bool):
        self.__is_right_bound = raligned

    def nextPage(self):
        self.__curPage += 1

    def prevPage(self):
        self.__curPage -= 1

    def play(self):
        self.__playing = True
        if self.__curFrame == -1:
            self.__curFrame = 0

    def pause(self):
        self.__playing = False

    def stop(self):
        self.__playing = False
        self.__curFrame = -1
        self.__curPage = 0

    def reset(self):
        self.stop()

    def initPainter(self, painter: QPainter):
        super().initPainter(painter)
        self.__renderTimer = time.perf_counter()

    def render(self, painter: QPainter):
        def fit_image_to(widget: QWidget, img: QImage) -> QImage:
            wFactor = widget.width() / img.width()
            hFactor = widget.height() / img.height()
            if wFactor < hFactor:
                scaledImg = img.smoothScaled(
                    img.width() * wFactor,
                    img.height() * wFactor
                )
            else:
                scaledImg = img.smoothScaled(
                    img.width() * hFactor,
                    img.height() * hFactor
                )
            return scaledImg

        painter.fillRect(0, 0, self.width(), self.height(),
                         QColor(0, 0, 0, 255))

        backgroundImg = self.get_background()

        if self.message is None:
            scaledBGImg = fit_image_to(self, backgroundImg)
            painter.drawImage(
                (self.width()/2) - (scaledBGImg.width()/2),
                (self.height()/2) - (scaledBGImg.height()/2),
                scaledBGImg)
            return

        _len = 0
        curComponent = None
        for cmp in self.message.components:
            if isinstance(cmp, str):
                size = len(cmp.encode(self.message.encoding))
            else:
                size = len(cmp)

            if _len < self.__curFrame < _len+size:
                curComponent = cmp
                break

        if curComponent is None:
            self.__curFrame = -1

        self.__buttons.clear()

        msgImage = QImage(1920, 1080, QImage.Format_ARGB32)
        msgImage.fill(Qt.transparent)

        msgPainter = QPainter()
        msgPainter.begin(msgImage)
        msgPainter.scale(2.28, 2.27)
        font = QFont("FOT-PopHappiness Std EB")
        font.setPointSize(self.FontSize)
        msgPainter.setFont(font)
        msgPainter.setPen(Qt.white)
        buttonPos = self.__render_any(msgPainter)
        msgPainter.end()

        if self.is_billboard():
            messageImgOfs = QPoint(470, 30)
        else:
            if self.__is_right_bound:
                messageImgOfs = QPoint(635, 5)
            else:
                messageImgOfs = QPoint(210, 53)

        mainPainter = QPainter()
        mainPainter.begin(backgroundImg)
        mainPainter.drawImage(messageImgOfs, msgImage)
        mainPainter.end()

        scaledBGImg = fit_image_to(self, backgroundImg)

        imgOfs = QPoint(
            (self.width()/2) - (scaledBGImg.width()/2),
            (self.height()/2) - (scaledBGImg.height()/2)
        )

        painter.drawImage(imgOfs, scaledBGImg)

        # Set Button Callback

        if buttonPos == QPoint(-1, -1):
            return

        button = BMGMessagePreviewWidget.ButtonCB()

        wFactor = self.width() / backgroundImg.width()
        hFactor = self.height() / backgroundImg.height()

        factor = min(wFactor, hFactor)
        buttonPos.setX(
            (messageImgOfs.x() + buttonPos.x()) * factor
        )
        buttonPos.setY(
            (messageImgOfs.y() + buttonPos.y()) * factor
        )
        buttonPos += imgOfs

        button.position = buttonPos
        button.radius = 30 * factor
        button.cb = self.nextPage

        self.__buttons.append(button)

    def __render_any(self, painter: QPainter) -> QPoint:
        numLines = self.__get_num_newlines(self.message)
        numPages = (numLines // self.linesPerPage) + 1

        if self.__curPage >= numPages:
            self.__curPage = 0

        message = self.__get_message_for_page(self.__curPage)

        isEndButtonVisible = self.__curPage == numPages-1
        backDropImg = self.backDropImage

        if self.__boxState == BMGMessagePreviewWidget.BoxState.NPC:
            #img = backDropImg.scaledToWidth(backDropImg.width() * 1.15)
            buttonPos = self.__render_message(
                painter,
                message,
                backDropImg,
                isEndButtonVisible
            )
        else:
            buttonPos = self.__render_billboard(
                painter,
                message,
                backDropImg,
                isEndButtonVisible
            )
        return buttonPos

    def __render_message(
        self,
        painter: QPainter,
        message: RichMessage,
        backDrop: QImage,
        endVisible: bool
    ) -> QPoint:
        def next_line(painter: QPainter, lineImg: QImage):
            painter.translate(0, 33)
            painter.setOpacity(self.BgOpacity)
            painter.drawImage(0, 0, lineImg)
            painter.setOpacity(1.0)

        def render_char(painter: QPainter, char: str, path: QPainterPath, lerp: float) -> float:
            if lerp > 1.0:
                return 0.0

            fontMetrics = painter.fontMetrics()

            point = path.pointAtPercent(lerp)
            angle = path.angleAtPercent(lerp)

            charWidth = fontMetrics.horizontalAdvanceChar(char)
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

        pathLerp = 0.0
        path = QPainterPath(QPoint(24, 41))
        path.cubicTo(
            QPoint(backDrop.width() / 3, 16),
            QPoint(backDrop.width() - (backDrop.width() / 3), 16),
            QPoint(backDrop.width() - 16, 50)
        )
        plen = path.length()

        if self.is_right_aligned():
            painter.translate(100, -33)
            painter.rotate(BMGMessagePreviewWidget.Rotation)
        else:
            painter.translate(0, 63)
            painter.rotate(-BMGMessagePreviewWidget.Rotation - 4)
        backDropRendered = False

        next_line(painter, backDrop)
        backDropRendered = True
        lastChar = ""
        queueLine = False
        queueSize = 0
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
                        charWidth = render_char(painter, char, path, pathLerp)
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
                        charWidth = render_char(painter, char, path, pathLerp)
                        pathLerp += charWidth / plen
                        lastChar = char
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

                charWidth = render_char(painter, char, path, pathLerp)
                pathLerp += charWidth / plen

                lastChar = char
                
        if not backDropRendered:
            next_line(painter, backDrop)

        buttonImg = QImage(27, 27, QImage.Format_ARGB32)
        buttonImg.fill(Qt.transparent)

        buttonPainter = QPainter()
        buttonPainter.begin(buttonImg)

        if self.is_next_button_visible():
            self.__render_next_button(buttonPainter)
            buttonPainter.end()
        elif endVisible:
            self.__render_end_button(buttonPainter)
            buttonPainter.end()
        else:
            buttonPainter.end()
            return QPoint(-1, -1)

        targetPos = QPoint(backDrop.width() - 5, 39)

        transform = QTransform()
        transform.rotate(-70)
        buttonImg = buttonImg.transformed(transform, Qt.SmoothTransformation)

        painter.save()
        painter.setOpacity(1.0)
        painter.drawImage(targetPos, buttonImg)
        painter.restore()

        centerOfs = buttonImg.rect().width() / 2
        transform = painter.combinedTransform()
        return transform.map(
            QPoint(
                targetPos.x() + centerOfs,
                targetPos.y() + centerOfs
            )
        )

    def __render_billboard(
        self,
        painter: QPainter,
        message: RichMessage,
        backDrop: QImage,
        endVisible: bool
    ) -> QPoint:
        painter.rotate(-10)
        painter.setOpacity(self.BgOpacity)
        painter.translate(0, 100)
        painter.drawImage(0, 0, backDrop)
        painter.setOpacity(1.0)
        painter.save()
        painter.translate(0, 20)
        fontMetrics = painter.fontMetrics()
        lines = message.get_string().split("\n")
        for line in lines:
            line = line.replace("\x00", "")
            lineWidth = fontMetrics.tightBoundingRect(line).width()
            painter.translate(0, 32)
            painter.drawText((backDrop.width() - lineWidth) / 2, 0, line)
        painter.restore()

        buttonImg = QImage(27, 27, QImage.Format_ARGB32)
        buttonImg.fill(Qt.transparent)

        buttonPainter = QPainter()
        buttonPainter.begin(buttonImg)

        if self.is_next_button_visible():
            self.__render_next_button(buttonPainter)
            buttonPainter.end()
        elif endVisible:
            self.__render_end_button(buttonPainter)
            buttonPainter.end()
        else:
            buttonPainter.end()
            return QPoint(-1, -1)

        targetPos = QPoint(backDrop.width() / 2.15, backDrop.height() + 5)
        painter.drawImage(targetPos, buttonImg)

        transform = painter.combinedTransform()
        return transform.map(
            QPoint(
                targetPos.x() + 13,
                targetPos.y() + 13
            )
        )

    def __render_next_button(self, painter: QPainter):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )
        arrowImg = QImage(
            str(resource_path("gui/images/message_cursor.png"))
        )
        painter.setOpacity(self.BgOpacity)
        painter.drawImage(0, 0, nextImg)
        painter.setOpacity(1.0)
        painter.drawImage(5, 7, arrowImg)

    def __render_end_button(self, painter: QPainter):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )

        returnImg = QImage(
            str(resource_path("gui/images/message_return.png"))
        )
        painter.setOpacity(self.BgOpacity)
        painter.drawImage(0, 0, nextImg)
        painter.setOpacity(1.0)
        painter.drawImage(5, 5, returnImg)

    def __get_num_newlines(self, message: RichMessage) -> int:
        num = 0
        for cmp in message.components:
            if isinstance(cmp, str):
                num += cmp.count("\n")
        return num

    def __get_message_for_page(self, page: int) -> RichMessage:
        components = []

        linesPerPage = self.linesPerPage
        startIndex = linesPerPage * page

        newlines = 0
        for cmp in self.message.components:
            if isinstance(cmp, str):
                cmpNewLines = 0
                substr = ""
                for char in cmp:
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
                components.append(cmp)
        return RichMessage(components)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter()
        painter.begin(self)

        self.render(painter)
        if self.__playing:
            self.__curFrame += 1
            if self.__curFrame > self.__endFrame:
                self.stop()

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            ePos = event.pos()
            for button in self.__buttons:
                buttonPosition = button.position
                buttonRadius = button.radius * button.radius
                diff = ePos - buttonPosition
                if ePos.dotProduct(diff, diff) < buttonRadius:
                    button.cb()
            else:
                self.update()


class BMGMessageListItem(InteractiveListWidgetItem):
    def __init__(self, item: Union["BMGMessageListItem", str], message: BMG.MessageEntry):
        super().__init__(item)
        self.message = message

    def clone(self) -> "BMGMessageListItem":
        message = BMG.MessageEntry(
            self.message.name,
            self.message.message,
            self.message.soundID,
            self.message.startFrame,
            self.message.endFrame
        )
        item = BMGMessageListItem(self, message)
        return item


class BMGMessageListWidget(InteractiveListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(150, 100)

    @Slot(BMGMessageListItem)
    def rename_item(self, item: BMGMessageListItem):
        name = super().rename_item(item)
        item.message.name = name

    @Slot(BMGMessageListItem)
    def duplicate_item(self, item: BMGMessageListItem):
        name = super().duplicate_item(item)
        item.message.name = name

    
class BMGMessageListInterfaceWidget(QWidget):
    addRequested: SignalInstance = Signal()
    removeRequested: SignalInstance = Signal()
    copyRequested: SignalInstance = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setFixedHeight(45)

        addButton = QPushButton("New", self)
        addButton.clicked.connect(self.addRequested.emit)
        self.__addButton = addButton

        removeButton = QPushButton("Remove", self)
        removeButton.clicked.connect(self.removeRequested.emit)
        self.__removeButton = removeButton

        copyButton = QPushButton("Copy", self)
        copyButton.clicked.connect(self.copyRequested.emit)
        self.__copyButton = copyButton

        layout = QHBoxLayout(self)
        layout.addWidget(self.__addButton)
        layout.addWidget(self.__removeButton)
        layout.addWidget(self.__copyButton)
        #layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(layout)


class BMGMessageInterfaceWidget(QWidget):
    attributeUpdateRequested: SignalInstance = Signal(str, int, int)

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
        soundIdComboBox.currentIndexChanged.connect(self.__push_update_request)
        self.__soundIdComboBox = soundIdComboBox

        soundIdLayout.addRow("Sound ID:", self.__soundIdComboBox)

        startFrameLayout = QFormLayout()

        startFrameLineEdit = QLineEdit()
        startFrameLineEdit.setText("0")
        startFrameLineEdit.setValidator(QIntValidator(0, 65535))
        startFrameLineEdit.textChanged.connect(self.__push_update_request)
        self.__startFrameLineEdit = startFrameLineEdit

        startFrameLayout.addRow("Start Frame:", self.__startFrameLineEdit)

        endFrameLayout = QFormLayout()

        endFrameLineEdit = QLineEdit()
        endFrameLineEdit.setText("0")
        endFrameLineEdit.setValidator(QIntValidator(0, 65535))
        endFrameLineEdit.textChanged.connect(self.__push_update_request)
        self.__endFrameLineEdit = endFrameLineEdit

        endFrameLayout.addRow("End Frame: ", self.__endFrameLineEdit)

        layout.addLayout(soundIdLayout)
        layout.addLayout(startFrameLayout)
        layout.addLayout(endFrameLayout)

        self.setLayout(layout)

    def set_values(self, soundID: SoundID, startFrame: int, endFrame: int):
        self.__soundIdComboBox.setCurrentIndex(soundID.value)
        self.__startFrameLineEdit.setText(str(startFrame))
        self.__endFrameLineEdit.setText(str(endFrame))

    @Slot()
    def __push_update_request(self):
        soundName = self.__soundIdComboBox.currentText()

        text = self.__startFrameLineEdit.text()
        if text == "":
            startFrame = 0
        else:
            startFrame = int(self.__startFrameLineEdit.text())

        text = self.__endFrameLineEdit.text()
        if text == "":
            endFrame = 0
        else:
            endFrame = int(self.__endFrameLineEdit.text())

        self.attributeUpdateRequested.emit(soundName, startFrame, endFrame)


class BMGMessagePreviewBGSelectWidget(QWidget):
    bgUpdateRequested: SignalInstance = Signal(str)
    boxChangeRequested: SignalInstance = Signal(bool)
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
            lambda idx: self.bgUpdateRequested.emit(self.comboBox.itemText(idx))
        )
        self.comboBox = comboBox

        billboard = QCheckBox("Is Billboard")
        billboard.setCheckable(True)
        billboard.stateChanged.connect(self.boxChangeRequested.emit)
        self.billboard = billboard

        layout.addRow("Background", comboBox)
        layout.addRow(billboard)

        self.setLayout(layout)


class BMGMessageTextBox(QPlainTextEdit):
    class CmdAction(QAction):
        clicked: SignalInstance = Signal(str)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self.__click)

        def __click(self):
            subname = self.text()
            parent: QMenu = self.parent()
            if parent:
                category = parent.title()
            self.clicked.emit("{" + category.lower() + ":" + subname + "}")

    class SpeedCmdAction(QAction):
        clicked: SignalInstance = Signal(str)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self.__click)

        def __click(self):
            self.clicked.emit("{speed:0}")

    class OptionCmdAction(QAction):
        clicked: SignalInstance = Signal(str)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.triggered.connect(self.__click)

        def __click(self):
            self.clicked.emit("{option:0:}")


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setMinimumSize(130, 100)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self.context_menu)

    @Slot(QPoint)
    def context_menu(self, point: QPoint):
        menu = self.createStandardContextMenu(point)

        categories: Dict[str, str] = {}
        for rich in RichMessage._RICH_TO_COMMAND:
            category, specifier = rich[1:-1].split(":")
            items: List[str] = categories.setdefault(category, [])
            items.append(specifier)

        menu.addSeparator()

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

        menu.exec(self.mapToGlobal(point))

    @Slot(str)
    def insert_token(self, token: str):
        self.insertPlainText(token)

    @Slot(str)
    def insert_format_token(self, token: str):
        self.insertPlainText(token)
        self.moveCursor(QTextCursor.Left, QTextCursor.MoveAnchor)


class BMGMessageMenuBar(QMenuBar):
    newRequested: SignalInstance = Signal()
    openRequested: SignalInstance = Signal()
    closeRequested: SignalInstance = Signal()
    saveRequested: SignalInstance = Signal(bool)

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
            lambda toggled: palAction.setChecked(not toggled))
        palAction.toggled.connect(
            lambda toggled: usaAction.setChecked(not toggled))

        kindMenu.addAction(usaAction)
        kindMenu.addAction(palAction)

        self.__usaAction = usaAction
        self.__palAction = palAction

        self.addMenu(fileMenu)
        self.addMenu(kindMenu)

    def is_region_pal(self) -> bool:
        return self.__palAction.isChecked() and not self.__usaAction.isChecked()

    def set_region_pal(self, isPal: bool):
        self.__palAction.setChecked(isPal)
        self.__usaAction.setChecked(not isPal)


class BMGMessageEditor(QWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(664, 300)

        self.mainLayout = QVBoxLayout()

        messageListBox = BMGMessageListWidget()
        messageListBox.currentItemChanged.connect(self.show_message)
        self.messageListBox = messageListBox

        messageListInterface = BMGMessageListInterfaceWidget()
        messageListInterface.addRequested.connect(self.new_message)
        messageListInterface.removeRequested.connect(self.remove_selected_message)
        messageListInterface.copyRequested.connect(self.copy_selected_message)
        self.messageListInterface = messageListInterface

        messageTextEdit = BMGMessageTextBox()
        messageTextEdit.setObjectName("Message Editor")
        messageTextEdit.textChanged.connect(self.update_message_text)
        self.messageTextEdit = messageTextEdit

        messageInterface = BMGMessageInterfaceWidget()
        messageInterface.attributeUpdateRequested.connect(
            self.update_message_attributes
        )
        self.messageInterface = messageInterface

        messagePreviewInterface = BMGMessagePreviewBGSelectWidget()
        messagePreviewInterface.bgUpdateRequested.connect(
            self.set_background
        )
        messagePreviewInterface.boxChangeRequested.connect(
            self.set_billboard
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
        messageInterfaceWidget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)

        messageListLayout = QVBoxLayout()
        messageListLayout.addWidget(messageListInterface)
        messageListLayout.addWidget(messageListBox)
        messageListLayout.setContentsMargins(0, 0, 0, 0)

        messageListWidget = QWidget()
        messageListWidget.setLayout(messageListLayout)
        self.messageListWidget = messageListWidget

        messageWidget = QWidget()
        self.messagePreview = BMGMessagePreviewWidget()

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
        messageWidget.setEnabled(False)
        self.messageWidget = messageWidget

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(messageListWidget)
        splitter.addWidget(messageWidget)
        #splitter.addWidget(self.messagePreview)
        self.splitter = splitter

        menuBar = BMGMessageMenuBar(self)
        menuBar.newRequested.connect(self.new_bmg)
        menuBar.openRequested.connect(self.open_bmg)
        menuBar.closeRequested.connect(self.close_bmg)
        menuBar.saveRequested.connect(
            lambda saveAs: self.save_bmg(saveAs=saveAs))
        self.menuBar = menuBar

        self.mainLayout.addWidget(self.menuBar)
        self.mainLayout.addWidget(self.splitter)

        self.setLayout(self.mainLayout)

        self.messages: List[BMG.MessageEntry] = []

        self.__cachedOpenPath: Path = None

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, BMG):
            return

        self.messageListBox.clear()
        self.messageTextEdit.clear()

        self.menuBar.set_region_pal(data.is_pal())

        for i, message in enumerate(data.iter_messages()):
            if message.name == "":
                message.name = f"message_unk_{i}"
            listItem = BMGMessageListItem(message.name, message)
            self.messageListBox.addItem(listItem)

        if self.messageListBox.count() > 0:
            self.messageListBox.setCurrentRow(0)

    @Slot()
    def new_bmg(self):
        self.populate(
            BMG(self.menuBar.is_region_pal(), 12),
            None
        )
        self.messageWidget.setEnabled(True)

    @Slot(Path)
    def open_bmg(self, path: Optional[Path] = None):
        if path is None:
            dialog = QFileDialog(
                parent=self,
                caption="Open BMG...",
                directory=str(
                    self.__cachedOpenPath.parent if self.__cachedOpenPath else Path.home()
                ),
                filter="Binary Messages (*.bmg);;All files (*)"
            )

            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setFileMode(QFileDialog.AnyFile)

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self.__cachedOpenPath = path

        with path.open("rb") as f:
            bmg = BMG.from_bytes(f)

        self.populate(bmg, None)

    @Slot()
    def close_bmg(self):
        self.messageListBox.clear()
        self.messageTextEdit.clear()
        self.messageInterface.set_values(
            SoundID(0), 0, 0
        )
        self.messageWidget.setEnabled(False)

    @Slot(Path, bool)
    def save_bmg(self, path: Optional[Path] = None, saveAs: bool = False):
        if (saveAs or self.__cachedOpenPath is None) and path is None:
            dialog = QFileDialog(
                parent=self,
                caption="Save BMG...",
                directory=str(
                    self.__cachedOpenPath.parent if self.__cachedOpenPath else Path.home()
                ),
                filter="Binary Messages (*.bmg);;All files (*)"
            )

            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setFileMode(QFileDialog.AnyFile)

            if dialog.exec_() != QFileDialog.Accepted:
                return False

            path = Path(dialog.selectedFiles()[0]).resolve()
            self.__cachedOpenPath = path

        with path.open("wb") as f:
            bmg = BMG.from_bytes(f)

        self.populate(bmg, None)

    @Slot(BMGMessageListItem)
    def show_message(self, item: BMGMessageListItem):
        if item is None or item.text() == "":
            return

        message = item.message
        self.messageTextEdit.setPlainText(message.message.get_rich_text().replace("\x00", ""))
        self.messageInterface.set_values(
            message.soundID,
            message.startFrame,
            message.endFrame
        )
        self.messagePreview.message = message.message
        self.messagePreview.reset()
        self.messagePreview.update()
        self.messageWidget.setEnabled(True)

    @Slot()
    def new_message(self):
        name = self.messageListBox._resolve_name("message")
        item = BMGMessageListItem(
            name,
            BMG.MessageEntry(name, RichMessage(), SoundID(0), 0, 0)
        )
        self.messageListBox.blockSignals(True)
        self.messageListBox.addItem(item)
        self.messageListBox.blockSignals(False)
        self.messageListBox.editItem(item, new=True)

    @Slot()
    def remove_selected_message(self):
        self.messageListBox.takeItem(self.messageListBox.currentRow())

    @Slot()
    def copy_selected_message(self):
        self.messageListBox.duplicate_item(self.messageListBox.currentItem())

    @Slot()
    def update_message_text(self):
        item: BMGMessageListItem = self.messageListBox.currentItem()
        if item is None:
            return
        item.message.message = RichMessage.from_rich_string(
            self.messageTextEdit.toPlainText())
        self.messagePreview.message = item.message.message
        self.messagePreview.update()

    @Slot(str, int, int)
    def update_message_attributes(self, soundName: str, startFrame: int, endFrame: int):
        item: BMGMessageListItem = self.messageListBox.currentItem()

        message = item.message
        message.soundID = SoundID.name_to_sound_id(soundName)
        message.startFrame = startFrame
        message.endFrame = endFrame

    @Slot(bool)
    def set_billboard(self, toggled: bool):
        self.messagePreview.boxState = (
            BMGMessagePreviewWidget.BoxState.BILLBOARD if toggled else BMGMessagePreviewWidget.BoxState.NPC
        )
        self.messagePreview.update()

    @Slot(str)
    def set_background(self, bgname: str):
        bg = BMGMessagePreviewWidget.BackGround._member_map_[bgname.upper()]
        self.messagePreview.set_background(bg)
        self.messagePreview.set_right_aligned(bg != BMGMessagePreviewWidget.BackGround.NOKI)
