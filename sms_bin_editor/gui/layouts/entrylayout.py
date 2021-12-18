from typing import List
from PySide2.QtCore import QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide2.QtGui import QColor, QCursor, QMouseEvent, QPaintEvent, QPainter, QPolygonF
from PySide2.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget
from build.lib.sms_bin_editor.objects.object import GameObject

from sms_bin_editor.gui.tools import walk_layout
from sms_bin_editor.objects.types import Vec3f


class EntryLayout(QGridLayout):
    SpacerWidth = 10
    FieldMinWidth = 100

    entryModified = Signal(str, object)

    def __init__(self, name: str, entry: QWidget, entryKind: type, directChildren: List[QLineEdit], labelWidth: int = 100, parent=None, newlining: bool = True):
        super().__init__(parent)
        self.entryLabelWidth = labelWidth
        self.entryLabel = QLabel(name, parent)
        self.entryLabel.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Expanding)
        self.entryLabel.setFixedWidth(labelWidth)
        self.entryLabel.setObjectName(name + " (Label)")
        self.entrySpacer = QSpacerItem(
            self.SpacerWidth, 20, QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.entryWidget = entry
        self.entryKind = entryKind
        self.directChildren = directChildren
        self.newLineActive = False
        self.expandFactor = 1.4
        self.recordedFlagSize = QRect(QPoint(0, 0), QSize(0, 0))

        self.addWidget(self.entryLabel, 0, 0, 1, 1)
        self.addWidget(self.entryWidget, 0, 1, 1, 1)
        self.setColumnStretch(0, 0)
        self.setColumnStretch(1, 1)
        self.setNewLining(newlining)

    def setFieldSizePolicy(self, policy: QSizePolicy):
        self.entryWidget.setSizePolicy(policy)

    def setLabelSizePolicy(self, policy: QSizePolicy):
        self.entryLabel.setSizePolicy(policy)

    def setNewLining(self, enabled: bool):
        self.newLining = enabled

    def setExpandFactor(self, factor: float):
        self.expandFactor = factor

    def addDirectChild(self, child: QLineEdit):
        self.directChildren.append(child)

    def removeDirectChild(self, child: QLineEdit):
        self.directChildren.remove(child)

    def isNewLineReady(self, bounds: QSize, _out: bool) -> bool:
        if not self.newLining:
            return False

        textRect: QRect = self.entryLabel.fontMetrics().boundingRect(self.entryLabel.text())
        isTextTooLong = textRect.width() > self.entryLabelWidth
        isWidgetTooSmall = False
        """
        if not _out:
            for item in walk_layout(self):
                widget = item.widget()
                if widget is None:
                    continue
                if isinstance(widget, QLineEdit):
                    print(bounds, self.recordedFlagSize)
                    print(widget.width(), widget.minimumSizeHint().width(), widget.objectName())
                    if widget.width() <= widget.minimumSizeHint().width():
                        isWidgetTooSmall = True
                        self.recordedFlagSize = bounds
                        break
        else:
            isWidgetTooSmall = bounds.width() <= self.recordedFlagSize.width()
        """

        for item in walk_layout(self):
            widget = item.widget()
            if widget is None:
                continue
            if isinstance(widget, QLineEdit):
                if _out:
                    check = widget.width() <= widget.minimumSizeHint().width() * self.expandFactor
                else:
                    check = widget.width() <= widget.minimumSizeHint().width()
                if check:
                    isWidgetTooSmall = True
                    self.recordedFlagSize = bounds
                    break

        return isTextTooLong or isWidgetTooSmall

        #print(bounds.width() - textRect.width())
        #print(self.entryWidget.pos(), self.entryWidget.sizeHint(),
        #      self.entryWidget.size())
        #if not _out:
        #    return (textRect.width() + self.SpacerWidth) >= self.entryWidget.pos().x()
        #return (bounds.width() - textRect.width()) < self.FieldMinWidth
        return textRect.width() > self.entryLabelWidth

    def checkNewLine(self, bounds: QSize):
        newLineReady = self.isNewLineReady(bounds, self.newLineActive)
        #print(newLineReady, self.newLineActive)
        if newLineReady and not self.newLineActive:
            self.entryLabel.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.entryLabel.setMinimumWidth(0)
            self.entryLabel.setMaximumWidth(10000)
            self.removeWidget(self.entryLabel)
            self.removeWidget(self.entryWidget)
            self.removeItem(self.entrySpacer)
            self.addWidget(self.entryLabel, 0, 0, 1, 2)
            self.addItem(self.entrySpacer, 1, 0, 1, 1)
            self.addWidget(self.entryWidget, 1, 1, 1, 1)
            self.setColumnStretch(0, 0)
            self.setColumnStretch(1, 1)
            self.newLineActive = True
        elif newLineReady is False and self.newLineActive:
            self.entryLabel.setSizePolicy(
                QSizePolicy.MinimumExpanding, QSizePolicy.Expanding)
            self.entryLabel.setFixedWidth(self.entryLabelWidth)
            self.removeWidget(self.entryLabel)
            self.removeWidget(self.entryWidget)
            self.removeItem(self.entrySpacer)
            self.addWidget(self.entryLabel, 0, 0, 1, 1)
            self.addWidget(self.entryWidget, 0, 1, 1, 1)
            self.setColumnStretch(0, 0)
            self.setColumnStretch(1, 1)
            self.newLineActive = False

    def updateFromChild(self, child: QLineEdit):
        if issubclass(self.entryKind, Vec3f):
            try:
                vec = Vec3f(*[float(c.text()) for c in self.directChildren])
                self.entryModified.emit(self.objectName(), vec)
            except ValueError:
                return
        else:
            self.entryModified.emit(self.objectName(), self.entryKind(child.text()))
        