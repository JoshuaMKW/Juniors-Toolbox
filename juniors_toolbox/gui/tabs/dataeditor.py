
from enum import IntEnum
from typing import BinaryIO, Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor, QPalette
from PySide6.QtWidgets import QWidget, QPlainTextEdit, QGridLayout, QLabel
from juniors_toolbox.gui import Serializer

from juniors_toolbox.gui.widgets.dockinterface import A_DockingInterface
from juniors_toolbox.scene import SMSScene
from juniors_toolbox.utils import A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.iohelper import align_int


class EditMode(IntEnum):
    READ = 0
    WRITE = 1


class DataEditorTextEdit(QPlainTextEdit):
    def __init__(self, editMode: EditMode, parent: Optional[QWidget] = None):
        super().__init__(parent)
        font = QFont("Courier New", 10)
        self.setFont(font)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(self.__class__.__name__ + " {background: #00000000}")

        self._editMode = editMode
        self.set_edit_mode(editMode)

    def set_edit_mode(self, editMode: EditMode):
        self._editMode = editMode
        if editMode == EditMode.READ:
            self.setReadOnly(True)
        else:
            self.setReadOnly(False)


class DataEditorLabel(QLabel):
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = QFont("Courier New", 10)
        self.setFont(font)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(self.__class__.__name__ + " {background: #00000000; color: #2F4FCF}")


class DataEditorWidget(A_DockingInterface):
    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._editMode = EditMode.READ

        self.mainWidget = QWidget()

        self.mainLayout = QGridLayout()
        self.mainLayout.setSpacing(0)

        self.offsetTextLabel = DataEditorLabel("Offset(h)")
        self.mainTextLabel = DataEditorLabel("00000000 00000004 00000008 0000000C")
        self.asciiTextLabel = DataEditorLabel("Decoded UTF-8")

        self.mainLayout.addWidget(self.offsetTextLabel, 0, 0, 1, 1)
        self.mainLayout.addWidget(self.mainTextLabel, 0, 1, 1, 1)
        self.mainLayout.addWidget(self.asciiTextLabel, 0, 2, 1, 1)

        self.offsetTextArea = DataEditorTextEdit(self._editMode)
        self.offsetTextArea.setFixedWidth(90)
        self.offsetTextArea.setFrameShape(DataEditorTextEdit.NoFrame)
        self.offsetTextArea.setTextInteractionFlags(Qt.NoTextInteraction)
        self.offsetTextArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.offsetTextArea.setCursor(Qt.ArrowCursor)
        self.offsetTextArea.setStyleSheet("background: #00000000; color: #2F4FCF")
        self.mainTextArea = DataEditorTextEdit(self._editMode)
        self.mainTextArea.setFixedWidth(304)
        self.mainTextArea.setFrameShape(DataEditorTextEdit.NoFrame)
        self.mainTextArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.asciiTextArea = DataEditorTextEdit(self._editMode)
        self.asciiTextArea.setMinimumWidth(160)
        self.asciiTextArea.setFrameShape(DataEditorTextEdit.NoFrame)
        self.asciiTextArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.mainLayout.addWidget(self.offsetTextArea, 1, 0, 1, 1)
        self.mainLayout.addWidget(self.mainTextArea, 1, 1, 1, 1)
        self.mainLayout.addWidget(self.asciiTextArea, 1, 2, 1, 1)

        self.mainWidget.setLayout(self.mainLayout)
        self.setWidget(self.mainWidget)

        self.sync_scrolls()
        self.sync_selections()

        self.rowSpacing = 32  # How many bytes before a double space.
        self.rowLength = 16  # How many bytes in a row.
        self.packetWidth = 4  # How many bytes in a packet


    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        if "serializable" not in kwargs:
            return
        serializable: A_Serializable = kwargs["serializable"]
        self.serializeThread = QThread()
        self.serializer = Serializer(serializable)
        self.serializer.moveToThread(self.serializeThread)
        self.serializeThread.started.connect(self.serializer.run)
        self.serializer.finished.connect(self.generate_view)
        self.serializer.finished.connect(self.serializeThread.quit)
        self.serializer.finished.connect(self.serializer.deleteLater)
        self.serializeThread.finished.connect(self.serializeThread.deleteLater)
        self.serializeThread.start()

    # generateView ... Generates text view for hexdump likedness.
    def generate_view(self, text: bytes):
        VALID_CHARACTERS = list(range(32, 128))
        offset = 0

        offsetText = ""
        mainText = ""
        asciiText = ""

        for chars in range(1, len(text) + 1):
            byte = text[chars - 1]
            if byte in VALID_CHARACTERS:
                asciiText += chr(text[chars - 1])
            else:
                asciiText += "."

            # mainText += format(byte, f"0{self.byteWidth*2}x")

            mainText += format(byte, "02X")
            if chars % self.rowLength == 0:
                offsetText += format(offset, "08x") + "\n"
                offset += self.rowLength
                mainText += "\n"
                asciiText += "\n"
            elif chars % self.packetWidth == 0:
                mainText += " "
        if len(text) % self.rowLength != 0:
            offsetText += format(offset, "08x") + "\n"

        self.offsetTextArea.setPlainText(offsetText)
        self.mainTextArea.setPlainText(mainText)
        self.asciiTextArea.setPlainText(asciiText)

    # highlightMain ... Bi-directional highlighting from main.

    def highlight_main(self):
        # Create and get cursors for getting and setting selections.
        highlightCursor = QTextCursor(self.asciiTextArea.document())
        cursor = self.mainTextArea.textCursor()

        # Clear any current selections and reset text color.
        highlightCursor.select(QTextCursor.Document)
        highlightCursor.setCharFormat(QTextCharFormat())
        highlightCursor.clearSelection()

        # Information about where selections and rows start.
        selectedText = cursor.selectedText()  # The actual text selected.
        if selectedText.endswith(" "):
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 1)
            self.mainTextArea.setTextCursor(cursor)

        selectionStart = cursor.selectionStart()
        selectionEnd = cursor.selectionEnd()

        mainText = self.mainTextArea.toPlainText()
        print(selectionStart, selectionEnd)

        lines = mainText[selectionStart:selectionEnd].split("\n")
        totalBytes = sum([align_int(len(line.replace(" ", "")), 2) for line in lines]) >> 1
        totalBytes += len(lines) - 1
        lines = mainText[:selectionStart].split("\n")
        asciiStart = sum([len(line.replace(" ", "")) for line in lines]) >> 1
        asciiStart += len(lines) - 1

        totalBytes = totalBytes
        asciiStart = asciiStart
        asciiEnd = asciiStart + totalBytes

        asciiText = self.asciiTextArea.toPlainText()

        # Select text and highlight it.
        highlightCursor.setPosition(asciiStart, QTextCursor.MoveAnchor)
        highlightCursor.setPosition(asciiEnd, QTextCursor.KeepAnchor)

        highlight = QTextCharFormat()
        highlight.setBackground(QColor(90, 160, 220))
        highlightCursor.setCharFormat(highlight)
        highlightCursor.clearSelection()

    # highlightAscii ... Bi-directional highlighting from ascii.
    def highlight_ascii(self):
        selectedText = self.asciiTextArea.textCursor().selectedText()

    def sync_scrolls(self):
        scroll0 = self.offsetTextArea.verticalScrollBar()
        scroll1 = self.mainTextArea.verticalScrollBar()
        scroll2 = self.asciiTextArea.verticalScrollBar()

        scroll0.valueChanged.connect(
            scroll1.setValue
        )

        scroll0.valueChanged.connect(
            scroll2.setValue
        )

        scroll1.valueChanged.connect(
            scroll0.setValue
        )

        scroll1.valueChanged.connect(
            scroll2.setValue
        )

        scroll2.valueChanged.connect(
            scroll1.setValue
        )

        scroll2.valueChanged.connect(
            scroll0.setValue
        )

    def sync_selections(self):
        self.mainTextArea.selectionChanged.connect(self.highlight_main)
        self.asciiTextArea.selectionChanged.connect(self.highlight_ascii)