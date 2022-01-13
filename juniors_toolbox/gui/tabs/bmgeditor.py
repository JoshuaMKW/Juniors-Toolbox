import time
import math
from pathlib import Path
from typing import Any, List, Union
from enum import IntEnum
from PySide6.QtWidgets import QPlainTextEdit, QSplitter
from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QImage, QKeyEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle, QTextEdit,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from nodeeditor.node_scene import Scene
from nodeeditor.node_node import Node
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_socket import Socket

from juniors_toolbox.gui.tabs.generic import GenericTabWidget
from juniors_toolbox.objects.object import GameObject
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils.bmg import BMG, RichMessage
from juniors_toolbox.utils.filesystem import resource_path

def _is_escape_code_option(code: bytes):
    return all([
        code[0] == b"\x1A",
        code[2:4] == b"\x01\x00"
    ])

class MessagePreview(QWidget):
    TextSpacingScale = 0.00382544309832 # from SMS
    BoxAppearSpeed = 0.04 # from SMS - 0 to 1 range
    TextWaitInverseScale = 1.0 # from SMS
    Rotation = 17.0 # from SMS, clockwise

    class PreviewState(IntEnum):
        IDLE = 0
        SCROLLING = 4
        WAITING = 5
        CLOSE = 6
        NEXTMSG = 7

    class BoxState(IntEnum):
        NPC = 0
        BILLBOARD = 1

    def __init__(self, message: RichMessage, parent=None):
        super().__init__(parent)
        self.__message = message
        self.__playing = False
        self.__curFrame = -1
        self.__endFrame = -1
        self.__curPage = 0
        self.__renderTimer = 0.0
        self.__boxState = MessagePreview.BoxState.NPC

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
        return 3 if self.__boxState == MessagePreview.BoxState.NPC else 6

    @property
    def backDropImage(self) -> QImage:
        if self.__boxState == MessagePreview.BoxState.NPC:
            QImage(str(resource_path("gui/images/message_back.png")))
        else:
            QImage(str(resource_path("gui/images/message_board.png")))

    def is_playing(self) -> bool:
        return self.__playing and self.__curFrame > -1

    def play(self):
        self.__playing = True
        if self.__curFrame == -1:
            self.__curFrame = 0

    def pause(self):
        self.__playing = False

    def stop(self):
        self.__playing = False
        self.__curFrame = -1

    def initPainter(self, painter: QPainter):
        super().initPainter(painter)
        self.__renderTimer = time.perf_counter()

    def render(self, painter: QPainter):
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

        if self.__curFrame == -1:
            self.render_all(painter)
        
    def render_all(self, painter: QPainter):
        numLines = self.__get_num_newlines(self.message)
        numPages = (numLines // self.linesPerPage) + 1

        if self.__curPage >= numPages:
            self.__curPage = 0

        isNextButtonVisible = self.__curPage < numPages-1
        backDropImg = self.backDropImage

        if self.__boxState == MessagePreview.BoxState.NPC:
            self.__render_message(painter, backDropImg, isNextButtonVisible)
        else:
            self.__render_billboard(painter, backDropImg, isNextButtonVisible)
        
    def __render_message(self, painter: QPainter, backDrop: QImage, nextVisible: bool):
        for _ in (): ...


    def __render_billboard(self, painter: QPainter, backDrop: QImage, nextVisible: bool):
        for _ in (): ...


    def __get_num_newlines(self, message: RichMessage) -> int:
        num = 0
        for cmp in message.components:
            if isinstance(cmp, str):
                num += cmp.count("\n")
        return num

    def __get_message_for_page(self, page: int) -> RichMessage:
        components = []
        newlines = 0
        linesPerPage = self.linesPerPage
        for cmp in self.message.components:
            if isinstance(cmp, str):
                newlines += cmp.count("\n")
            #else:
            #   if _is_escape_code_option(cmp):
            #        newlines = math.ceil(newlines/3)*3 if newlines > 0 else 1
                index = newlines - (linesPerPage * page)
                if index > linesPerPage:
                    break
                if index > 0:
                    components.extend(cmp.split("\n")[index:])
            else:
                index = newlines - (linesPerPage * page)
                if index > linesPerPage:
                    break
                if index > 0:
                    components.append(cmp)
        return RichMessage(components)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.begin()

        self.render(painter)
        if self.__playing:
            self.__curFrame += 1
            if self.__curFrame > self.__endFrame:
                self.stop()

        painter.end()


class BMGMessageListItem(QListWidgetItem):
    def __init__(self, message: RichMessage, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

class BMGMessageTextBox(QPlainTextEdit):
    __ESCAPE_TO_RICH_TEXT = [
        ["{color:white}", "<span style=\"color:#ff0000;\">"]
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textChanged.connect(self.format_escape_codes)

    def format_escape_codes(self):
        text = self.toPlainText()


class BMGMessageEditor(QWidget, GenericTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 300)

        self.mainLayout = QHBoxLayout()
        
        self.textEdit = QTextEdit()
        self.textEdit.setAcceptRichText(True)
        self.textEdit.setObjectName("Message Editor")

        self.messageListBox = QListWidget()
        self.messageListBox.setDragEnabled(True)
        self.messageListBox.setAcceptDrops(True)
        #self.messageListBox.setMaximumWidth(180)
        self.messageListBox.setObjectName("Message List")

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.messageListBox)
        splitter.addWidget(self.textEdit)
        self.splitter = splitter

        self.mainLayout.addWidget(self.splitter)

        self.setLayout(self.mainLayout)

        self.messages: List[BMG.MessageEntry] = []

    def populate(self, data: Any, scenePath: Path):
        if not isinstance(data, BMG):
            return

        for i, message in enumerate(data.iter_messages()):
            name = message.name
            if message.name == "":
                name = f"message_unk_{i}"
            listItem = BMGMessageListItem(message.message, name)
            self.messageListBox.addItem(listItem)


# class BMGNodeEditorWidget(NodeEditorWidget, GenericTabWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setAcceptDrops(True)
#         self.setMinimumSize(300, 300)

#     def populate(self, data: Any, scenePath: Path):
#         if not isinstance(data, BMG):
#             return

#         scene = Scene()
#         prevEscapeNodes = []
#         prevTextNode: Node = None
#         for message in data.iter_messages():
#             for component in message.message.components:
#                 if isinstance(component, str):
#                     node = Node(
#                         scene,
#                         message.name,
#                         [1, 2, 3],
#                         [1]
#                     )
                    
#                     socket: Socket = node.inputs[0]
#                     prevTextNode.conn
#                 else: