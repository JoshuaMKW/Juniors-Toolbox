from typing import List
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPaintEvent, QPainter, QPolygonF
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget
from juniors_toolbox.objects.object import GameObject

from juniors_toolbox.gui.tools import walk_layout
from juniors_toolbox.utils.types import Vec3f


class EntryLayout(QGridLayout):
    SpacerWidth = 10
    FieldMinWidth = 100

    entryModified = Signal(str, object)

    def __init__(
        self, 
        name: str, 
        entry: QWidget, 
        entryKind: type, 
        directChildren: List[QLineEdit], 
        labelWidth: int = 100,
        minEntryWidth: int = 100, 
        parent=None, 
        newlining: bool = True,
        labelFixed: bool = True
    ):
        super().__init__(parent)
        self.entryLabelWidth = labelWidth
        self.entryLabel = QLabel(name, parent)
        if labelFixed:
            self.entryLabel.setFixedWidth(labelWidth)
        else:
            self.entryLabel.setMinimumWidth(labelWidth)
            #self.entryLabel.setSizePolicy(
            #    QSizePolicy.MinimumExpanding, QSizePolicy.Expanding)
        self.entryLabel.setObjectName(name + " (Label)")
        self.entrySpacer = QSpacerItem(
            self.SpacerWidth, 20, QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.entryWidget = entry
        self.entryKind = entryKind
        self.directChildren = directChildren
        self.newLineActive = False
        self.minEntryWidth = minEntryWidth
        self.recordedFlagSize = QRect(QPoint(0, 0), QSize(0, 0))

        self.addWidget(self.entryLabel, 0, 0, 1, 1)
        self.addWidget(self.entryWidget, 0, 1, 1, 1)
        if labelFixed:
            self.setColumnStretch(0, 0)
            self.setColumnStretch(1, 1)
        else:
            self.setColumnStretch(0, 1)
            self.setColumnStretch(1, 2)
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
        """
        isWidgetTooSmall = False
        if not _out:
            for item in walk_layout(self):
                widget = item.widget()
                if widget is None:
                    continue
                if isinstance(widget, QLineEdit):
                    #print(bounds, self.recordedFlagSize)
                    #print(widget.width(), widget.minimumSizeHint().width(), widget.objectName())
                    if widget.width() <= widget.minimumSizeHint().width():
                        isWidgetTooSmall = True
                        self.recordedFlagSize = bounds
                        break
        else:
            isWidgetTooSmall = bounds.width() <= self.recordedFlagSize.width()
        """

        minpos = 0
        maxpos = 0
        for item in walk_layout(self):
            widget = item.widget()
            if widget is None:
                continue
            minpos = min(minpos, widget.pos().x())
            maxpos = max(maxpos, widget.pos().x() + widget.size().width())
                
        #print(self.objectName(), (maxpos - minpos) - textRect.width(), self.minEntryWidth)
        isWidgetTooSmall = (maxpos - minpos) < self.minEntryWidth
        return isTextTooLong or isWidgetTooSmall

        ##print(bounds.width() - textRect.width())
        ##print(self.entryWidget.pos(), self.entryWidget.sizeHint(),
        #      self.entryWidget.size())
        #if not _out:
        #    return (textRect.width() + self.SpacerWidth) >= self.entryWidget.pos().x()
        #return (bounds.width() - textRect.width()) < self.FieldMinWidth
        return textRect.width() > self.entryLabelWidth

    def checkNewLine(self, bounds: QSize):
        newLineReady = self.isNewLineReady(bounds, self.newLineActive)
        ##print(newLineReady, self.newLineActive)
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
            self.newLineActive = False

    def updateFromChild(self, child: QWidget, value: object):
        if issubclass(self.entryKind, Vec3f):
            try:
                vec = Vec3f(*[float(c.text()) for c in self.directChildren])
                self.entryModified.emit(self.objectName(), vec)
            except ValueError:
                return
        else:
            self.entryModified.emit(self.objectName(), self.entryKind(value))
        