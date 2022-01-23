from email.charset import QP
import time
import math
from pathlib import Path
from turtle import back
from typing import Any, List, Optional, Union
from enum import IntEnum
from PySide6.QtWidgets import QPlainTextEdit, QSplitter
from PySide6.QtCore import QLine, QModelIndex, QObject, Qt, QTimer, Slot, SignalInstance, Signal, QSizeF, QPoint, QPointF
from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QImage, QKeyEvent, QPaintEvent, QPainter, QAction, QResizeEvent, QTransform, QMouseEvent
from PySide6.QtWidgets import (QBoxLayout, QFormLayout, QFrame, QGridLayout, QMenu,
                               QGroupBox, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSizePolicy, QSpacerItem, QStyle, QTextEdit,
                               QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QMenuBar, QFileDialog)

from nodeeditor.node_scene import Scene
from nodeeditor.node_node import Node
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_socket import Socket
from numpy import save

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


class BMGMessagePreviewWidget(QWidget):
    TextSpacingScale = 0.00382544309832  # from SMS
    BoxAppearSpeed = 0.04  # from SMS - 0 to 1 range
    TextWaitInverseScale = 1.0  # from SMS
    Rotation = 17.0  # from SMS, clockwise

    class PreviewState(IntEnum):
        IDLE = 0
        SCROLLING = 4
        WAITING = 5
        CLOSE = 6
        NEXTMSG = 7

    class BoxState(IntEnum):
        NPC = 0
        BILLBOARD = 1

    def __init__(self, message: RichMessage = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.__message = message
        self.__playing = False
        self.__curFrame = -1
        self.__endFrame = -1
        self.__curPage = 0
        self.__renderTimer = 0.0
        self.__boxState = BMGMessagePreviewWidget.BoxState.NPC
        self.__factor = 0.0
        self.__imgSize = QSizeF(0.0, 0.0)
        self.__nextPos = QPoint(-1, -1)
        self.__nextRadius = 0.0

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

        backgroundImg = QImage(
            str(resource_path("gui/backgrounds/bmg_preview.png"))
        )

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

        msgImage = QImage(1200, 800, QImage.Format_ARGB32)
        msgImage.fill(Qt.transparent)
        if self.__curFrame == -1:
            msgPainter = QPainter()
            msgPainter.begin(msgImage)
            msgPainter.scale(2.28, 2.27)
            self.__render_any(msgPainter)
            msgPainter.end()

        mainPainter = QPainter()
        mainPainter.begin(backgroundImg)
        mainPainter.drawImage(635, 5, msgImage)
        mainPainter.end()

        scaledBGImg = fit_image_to(self, backgroundImg)

        imgOfs = QPoint(
            (self.width()/2) - (scaledBGImg.width()/2),
            (self.height()/2) - (scaledBGImg.height()/2)
        )

        painter.drawImage(imgOfs, scaledBGImg)

        wFactor = self.width() / backgroundImg.width()
        hFactor = self.height() / backgroundImg.height()

        factor = min(wFactor, hFactor)
        self.__nextPos.setX(
            (635 + self.__nextPos.x()) * factor
        )
        self.__nextPos.setY(
            (5 + self.__nextPos.y()) * factor
        )
        self.__nextPos += imgOfs  # Translate the target by the widget translation
        self.__nextRadius *= factor * 1.15  # Scale target by the widget scale

    def __render_any(self, painter: QPainter):
        numLines = self.__get_num_newlines(self.message)
        numPages = (numLines // self.linesPerPage) + 1

        if self.__curPage >= numPages:
            self.__curPage = 0

        message = self.__get_message_for_page(self.__curPage)
        lines = message.get_string().split("\n")

        isNextButtonVisible = self.__curPage < numPages-1
        isEndButtonVisible = self.__curPage > 0 and self.__curPage == numPages-1
        backDropImg = self.backDropImage

        if self.__boxState == BMGMessagePreviewWidget.BoxState.NPC:
            #img = backDropImg.scaledToWidth(backDropImg.width() * 1.15)
            self.__render_message(
                painter,
                lines,
                backDropImg,
                isNextButtonVisible,
                isEndButtonVisible
            )
        else:
            self.__render_billboard(
                painter,
                lines,
                backDropImg,
                isNextButtonVisible,
                isEndButtonVisible
            )

    def __render_message(
        self,
        painter: QPainter,
        message: List[str],
        backDrop: QImage,
        nextVisible: bool,
        endVisible: bool
    ):
        painter.translate(100, -33)
        painter.rotate(BMGMessagePreviewWidget.Rotation)
        painter.setOpacity(0.7)
        #painter.scale(1.05, 1)
        for i, line in enumerate(message):
            if line == "":
                continue
            painter.translate(0, 33)
            painter.drawImage(0, 0, backDrop)
            painter.drawText(0, 0, line.replace("\x00", ""))
        else:
            if nextVisible:
                self.__render_next_button(
                    painter,
                    QPoint(backDrop.width(), 45),
                    -70
                )
            elif endVisible:
                self.__render_end_button(
                    painter,
                    QPoint(backDrop.width(), 45),
                    -70
                )
            else:
                self.__nextPos = QPoint(-1, -1)

    def __render_billboard(
        self,
        painter: QPainter,
        message: List[str],
        backDrop: QImage,
        nextVisible: bool,
        endVisible: bool
    ):
        for _ in ():
            ...

    def __render_next_button(
        self,
        painter: QPainter,
        targetPos: QPoint,
        rotation: float
    ):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )
        nextImg = nextImg.smoothScaled(
            nextImg.width()*1.1, nextImg.height()*1.1
        )

        arrow = QImage(
            str(resource_path("gui/images/message_cursor.png"))
        )
        arrow = arrow.smoothScaled(
            arrow.width()*0.9, arrow.height()*0.9
        )
        transform = QTransform()
        transform.rotate(rotation)
        arrow = arrow.transformed(transform, Qt.SmoothTransformation)

        transform = painter.combinedTransform()
        self.__nextPos = transform.map(
            QPoint(
                targetPos.x() + (nextImg.width()/2),
                targetPos.y() + (nextImg.height()/2)
            )
        )
        self.__nextRadius = (nextImg.width() + nextImg.height()) / 2
        painter.drawImage(targetPos, nextImg)

        tPointTranslated = QPoint(targetPos.x()+4, targetPos.y()+2)
        _opacity = painter.opacity()
        painter.setOpacity(1.0)
        painter.drawImage(tPointTranslated, arrow)
        painter.setOpacity(_opacity)

    def __render_end_button(
        self,
        painter: QPainter,
        targetPos: QPoint,
        rotation: float
    ):
        nextImg = QImage(
            str(resource_path("gui/images/message_button_back.png"))
        )
        nextImg = nextImg.smoothScaled(
            nextImg.width()*1.1, nextImg.height()*1.1
        )

        arrow = QImage(
            str(resource_path("gui/images/message_return.png"))
        )
        arrow = arrow.smoothScaled(
            arrow.width()*0.7, arrow.height()*0.7
        )
        transform = QTransform()
        transform.rotate(rotation)
        arrow = arrow.transformed(transform, Qt.SmoothTransformation)

        transform = painter.transform()
        #transform = painter.combinedTransform()
        self.__nextPos = transform.map(
            QPoint(
                targetPos.x() + (nextImg.width()/2),
                targetPos.y() + (nextImg.height()/2)
            )
        )
        self.__nextRadius = (nextImg.width() + nextImg.height()) / 2
        painter.drawImage(targetPos, nextImg)

        tPointTranslated = QPoint(targetPos.x()+3, targetPos.y()+2)
        _opacity = painter.opacity()
        painter.setOpacity(1.0)
        painter.drawImage(tPointTranslated, arrow)
        painter.setOpacity(_opacity)

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
                cmpNLines = cmp.count("\n")
            # else:
            #   if _is_escape_code_option(cmp):
            #        newlines = math.ceil(newlines/3)*3 if newlines > 0 else 1

                index = (newlines + cmpNLines) - startIndex
                if index < 0:
                    continue
                components.append(
                    "\n".join(
                        cmp.split("\n")[
                            startIndex-newlines:(linesPerPage+startIndex) - newlines]
                    )
                )
                if index > linesPerPage:
                    break
                newlines += cmpNLines
            else:
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
            nPos = self.__nextPos
            rad = self.__nextRadius
            if self.__nextPos == QPoint(-1, -1):
                return
            diff = ePos - nPos
            dist = ePos.dotProduct(diff, diff)
            drad = self.__nextRadius * self.__nextRadius
            if dist < drad:
                self.__curPage += 1
                self.update()


class BMGMessageListItem(QListWidgetItem):
    def __init__(self, message: BMG.MessageEntry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message

        self.setFlags(
            Qt.ItemIsEnabled |
            Qt.ItemIsEditable |
            Qt.ItemIsSelectable |
            Qt.ItemIsDragEnabled
        )


class BMGMessageListWidget(QListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QListWidget.DragDrop)
        self.setObjectName("Message List")


class BMGMessageTextBox(QTextEdit):
    __ESCAPE_TO_RICH_TEXT = [
        ["{color:white}", "<span style=\"color:#ff0000;\">"]
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setMinimumWidth(130)
        self.textChanged.connect(self.format_escape_codes)

    def format_escape_codes(self):
        text = self.toPlainText()


class BMGMessageMenuBar(QMenuBar):
    openRequested: SignalInstance = Signal()
    closeRequested: SignalInstance = Signal()
    saveRequested: SignalInstance = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setNativeMenuBar(False)
        self.setFixedHeight(28)

        fileMenu = QMenu(self)
        fileMenu.setTitle("File")

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

        fileMenu.addAction(openAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(saveAsAction)
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
        self.setMinimumSize(440, 240)

        self.mainLayout = QVBoxLayout()
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.textEdit = BMGMessageTextBox()
        self.textEdit.setAcceptRichText(True)
        self.textEdit.setObjectName("Message Editor")
        self.textEdit.textChanged.connect(self.update_message_text)

        messageListBox = BMGMessageListWidget()
        messageListBox.currentItemChanged.connect(self.show_message)

        self.messageListBox = messageListBox

        self.messagePreview = BMGMessagePreviewWidget()

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.messageListBox)
        splitter.addWidget(self.textEdit)
        splitter.addWidget(self.messagePreview)
        self.splitter = splitter

        menuBar = BMGMessageMenuBar(self)
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
        self.textEdit.clear()

        self.menuBar.set_region_pal(data.is_pal())

        for i, message in enumerate(data.iter_messages()):
            if message.name == "":
                message.name = f"message_unk_{i}"
            listItem = BMGMessageListItem(message, message.name)
            self.messageListBox.addItem(listItem)

        if self.messageListBox.count() > 0:
            self.messageListBox.setCurrentRow(0)

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
        self.textEdit.clear()

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
        self.textEdit.setPlainText(item.message.message.get_rich_text())
        self.messagePreview.message = item.message.message
        self.messagePreview.reset()
        self.messagePreview.update()

    @Slot()
    def update_message_text(self):
        item: BMGMessageListItem = self.messageListBox.currentItem()
        if item is None:
            return
        item.message.message = RichMessage.from_rich_string(
            self.textEdit.toPlainText())
        self.messagePreview.message = item.message.message
        self.messagePreview.update()


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
