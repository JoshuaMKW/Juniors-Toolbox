
from enum import IntEnum
from typing import BinaryIO, Optional
import time

from PySide6.QtCore import Qt, QThread, Signal, Slot, QMutex, QMutexLocker, QObject, QRunnable
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor, QPalette, QTextFormat, QTextFrameFormat
from PySide6.QtWidgets import QWidget, QPlainTextEdit, QGridLayout, QLabel, QTextEdit
from juniors_toolbox.gui import RunnableSerializer, ThreadSerializer, WorkerSignals

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


class DataEditorCompiler(QRunnable):
    def __init__(self, data: bytes, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.rowSpacing = 32  # How many bytes before a double space.
        self.rowLength = 16  # How many bytes in a row.
        self.packetWidth = 4  # How many bytes in a packet

        self._data = data
        self.signals = WorkerSignals()

    def run(self) -> None:
        print("running")
        VALID_CHARACTERS = list(range(32, 128))
        offset = 0

        offsetText = ""
        mainText = ""
        asciiText = ""

        data = self._data

        for chars in range(1, len(data) + 1):
            byte = data[chars - 1]
            if byte in VALID_CHARACTERS:
                asciiText += chr(data[chars - 1])
            else:
                asciiText += "."

            mainText += format(byte, "02X")
            if chars % self.rowLength == 0:
                offsetText += format(offset, "08X") + "\n"
                offset += self.rowLength
                mainText += "\n"
                asciiText += "\n"
            elif chars % self.packetWidth == 0:
                mainText += " "
        if len(data) % self.rowLength != 0:
            offsetText += format(offset, "08X") + "\n"

        print("finished")
        self.signals.finished.emit()
        self.signals.result.emit((offsetText, mainText, asciiText))

    def _process_data(self) -> tuple:
        VALID_CHARACTERS = list(range(32, 128))
        offset = 0

        offsetText = ""
        mainText = ""
        asciiText = ""

        data = self._data

        for chars in range(1, len(data) + 1):
            byte = data[chars - 1]
            if byte in VALID_CHARACTERS:
                asciiText += chr(data[chars - 1])
            else:
                asciiText += "."

            mainText += format(byte, "02X")
            if chars % self.rowLength == 0:
                offsetText += format(offset, "08X") + "\n"
                offset += self.rowLength
                mainText += "\n"
                asciiText += "\n"
            elif chars % self.packetWidth == 0:
                mainText += " "
        if len(data) % self.rowLength != 0:
            offsetText += format(offset, "08X") + "\n"

        return (offsetText, mainText, asciiText)



class DataEditorWidget(A_DockingInterface):
    dataChanged = Signal(bytes)

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

        self._sync_scrolls()
        self._sync_selections()
        self.dataChanged.connect(self.generate_view)

        self._sync_scrolls()
        self._sync_selections()

        self.rowSpacing = 32  # How many bytes before a double space.
        self.rowLength = 16  # How many bytes in a row.
        self.packetWidth = 4  # How many bytes in a packet

        self._data = b""
        self._dataMutex = QMutex()

    def populate(self, scene: Optional[SMSScene], *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        if "serializable" not in kwargs:
            return

        serializable: A_Serializable = kwargs["serializable"]
        # self.serializeThread = QThread()
        # self.serializer = Serializer(serializable)
        # self.serializer.moveToThread(self.serializeThread)
        # self.serializeThread.started.connect(self.serializer.run)
        # self.serializer.finished.connect(self.set_data)
        # self.serializer.finished.connect(self.serializeThread.quit)
        # self.serializer.finished.connect(self.serializer.deleteLater)
        # self.serializeThread.finished.connect(self.serializeThread.deleteLater)
        # self.serializeThread.start()
        self.set_data(serializable.to_bytes())

    def set_data(self, data: bytes):
        with QMutexLocker(self._dataMutex) as mutexLock:
            self._data = data
            self.dataChanged.emit(data)

    def get_data(self) -> bytes:
        return self._data

    @Slot(bytes)
    def generate_view(self, data: bytes):
        compiler = DataEditorCompiler(data)
        self.set_text_fields(compiler._process_data())

    @Slot()
    def highlight_main(self):
        self.mainTextArea.blockSignals(True)
        self.asciiTextArea.blockSignals(True)

        asciiCursor = self.asciiTextArea.textCursor()
        asciiCursor.clearSelection()
        self.asciiTextArea.setTextCursor(asciiCursor)
        
        self.mainTextArea.setExtraSelections([])

        # Create and get cursors for getting a
        selfHighlightCursor = QTextCursor(self.mainTextArea.document())
        otherHighlightCursor = QTextCursor(self.asciiTextArea.document())

        # Clear any current selections and reset text color.
        selfHighlightCursor.select(QTextCursor.Document)
        selfHighlightCursor.setCharFormat(QTextCharFormat())
        selfHighlightCursor.clearSelection()
        otherHighlightCursor.select(QTextCursor.Document)
        otherHighlightCursor.setCharFormat(QTextCharFormat())
        otherHighlightCursor.clearSelection()

        highlightSelection = QTextEdit.ExtraSelection()
        highlightSelection.format.setBackground(self.palette().color(QPalette.Highlight))
        highlightSelection.format.setForeground(self.palette().color(QPalette.Text))
        cursor = self.mainTextArea.textCursor()

        # Information about where selections and rows start.
        selectedText = cursor.selectedText()  # The actual text selected.
        if selectedText.endswith(" "):
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 1)
            self.mainTextArea.setTextCursor(cursor)

        selectionStart = cursor.selectionStart()
        selectionEnd = cursor.selectionEnd()

        mainText = self.mainTextArea.toPlainText()

        lines = mainText[selectionStart:selectionEnd].split("\n")
        totalBytes = sum([align_int(len(line.replace(" ", "")), 2) for line in lines]) >> 1
        totalBytes += len(lines) - 1
        lines = mainText[:selectionStart].split("\n")
        asciiStart = sum([len(line.replace(" ", "")) for line in lines]) >> 1
        asciiStart += len(lines) - 1

        totalBytes = totalBytes
        asciiStart = asciiStart
        asciiEnd = asciiStart + totalBytes

        # Select text and highlight it.
        # Select text and highlight it.
        otherHighlightCursor.setPosition(asciiStart, QTextCursor.MoveAnchor)
        otherHighlightCursor.setPosition(asciiEnd, QTextCursor.KeepAnchor)
        highlightSelection.cursor = otherHighlightCursor
        
        self.asciiTextArea.setExtraSelections([highlightSelection])
        self.asciiTextArea.blockSignals(True)
        self.asciiTextArea.verticalScrollBar().setValue(self.mainTextArea.verticalScrollBar().value())
        self.asciiTextArea.blockSignals(False)

        self.asciiTextArea.blockSignals(False)
        self.mainTextArea.blockSignals(False)

    @Slot()
    def highlight_ascii(self):
        self.asciiTextArea.blockSignals(True)
        self.mainTextArea.blockSignals(True)

        mainCursor = self.asciiTextArea.textCursor()
        mainCursor.clearSelection()
        self.mainTextArea.setTextCursor(mainCursor)

        self.asciiTextArea.setExtraSelections([])

        selfHighlightCursor = QTextCursor(self.asciiTextArea.document())
        otherHighlightCursor = QTextCursor(self.mainTextArea.document())

        # Clear any current selections and reset text color.
        selfHighlightCursor.select(QTextCursor.Document)
        selfHighlightCursor.setCharFormat(QTextCharFormat())
        selfHighlightCursor.clearSelection()
        otherHighlightCursor.select(QTextCursor.Document)
        otherHighlightCursor.setCharFormat(QTextCharFormat())
        otherHighlightCursor.clearSelection()

        # Create and get cursors for getting and setting selections.
        highlightSelection = QTextEdit.ExtraSelection()
        highlightSelection.format.setBackground(self.palette().color(QPalette.Highlight))
        highlightSelection.format.setForeground(self.palette().color(QPalette.Text))
        cursor = self.asciiTextArea.textCursor()

        # Information about where selections and rows start.
        selectionStart = cursor.selectionStart()
        selectionEnd = cursor.selectionEnd()

        asciiText = self.asciiTextArea.toPlainText()

        lines = asciiText[:selectionStart].split("\n")
        newLines = len(lines) - 1
        bytesPreLength = sum([len(line) for line in lines]) << 1
        bytesSpaces = (bytesPreLength % (self.rowLength << 1)) // 8
        bytesStart = bytesPreLength + (newLines * 4)

        lines = asciiText[selectionStart:selectionEnd].split("\n")
        newLines = len(lines) - 1
        totalPreLength = sum([len(line) for line in lines]) << 1
        totalSpaces = (totalPreLength + (bytesPreLength % 8) - 1) // 8

        totalBytes = max(totalPreLength + totalSpaces, 0)
        bytesStart = bytesStart + bytesSpaces
        bytesEnd = bytesStart + totalBytes

        # Select text and highlight it.
        otherHighlightCursor.setPosition(bytesStart, QTextCursor.MoveAnchor)
        otherHighlightCursor.setPosition(bytesEnd, QTextCursor.KeepAnchor)
        highlightSelection.cursor = otherHighlightCursor
        
        self.mainTextArea.setExtraSelections([highlightSelection])
        self.mainTextArea.blockSignals(True)
        self.mainTextArea.verticalScrollBar().setValue(self.asciiTextArea.verticalScrollBar().value())
        self.mainTextArea.blockSignals(False)

        self.mainTextArea.blockSignals(False)
        self.asciiTextArea.blockSignals(False)

    @Slot(tuple)
    def set_text_fields(self, texts: tuple):
        self.offsetTextArea.setPlainText(texts[0])
        self.mainTextArea.setPlainText(texts[1])
        self.asciiTextArea.setPlainText(texts[2])

    def _sync_scrolls(self):
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

    def _sync_selections(self):
        self.mainTextArea.selectionChanged.connect(self.highlight_main)
        self.asciiTextArea.selectionChanged.connect(self.highlight_ascii)

    def __remove_thread(self, thread: QThread):
        try:
            self._threads.remove(thread)
        except KeyError:
            pass