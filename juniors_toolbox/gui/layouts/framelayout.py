from typing import Optional, Tuple
from PySide6.QtCore import QPoint, QPointF, Signal, Slot, SignalInstance
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPolygonF, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QLayout

class FrameLayout(QFrame):
    class Arrow(QFrame):
        def __init__(self, parent: Optional[QWidget] = None, collapsed: bool = False) -> None:
            QFrame.__init__(self, parent=parent)

            self.setMaximumSize(24, 24)

            # horizontal == 0
            self._arrow_horizontal = (QPointF(7.0, 8.0), QPointF(17.0, 8.0), QPointF(12.0, 13.0))
            # vertical == 1
            self._arrow_vertical = (QPointF(8.0, 7.0), QPointF(13.0, 12.0), QPointF(8.0, 17.0))
            # arrow
            self._arrow: Tuple[QPointF, QPointF, QPointF] = self._arrow_horizontal
            self.setArrow(collapsed)

        def setArrow(self, vertical: bool) -> None:
            if vertical:
                self._arrow = self._arrow_vertical
            else:
                self._arrow = self._arrow_horizontal

        @Slot(QPaintEvent)
        def paintEvent(self, event: QPaintEvent) -> None:
            arrowPoly = QPolygonF()
            for p in self._arrow:
                arrowPoly.append(p)
            painter = QPainter()
            painter.begin(self)
            painter.setBrush(QColor(192, 192, 192))
            painter.setPen(QColor(64, 64, 64))
            painter.drawPolygon(arrowPoly)
            painter.end()

    class TitleFrame(QFrame):
        clicked = Signal(QMouseEvent)

        def __init__(self, parent: Optional[QWidget] = None, title: Optional[str] = None, collapsed: bool = False) -> None:
            super().__init__(parent)

            self.setFrameShape(QFrame.Shape.Box)
            self.setMinimumHeight(24)
            self.move(QPoint(24, 0))

            self._hlayout = QHBoxLayout(self)
            self._hlayout.setContentsMargins(0, 0, 0, 0)
            self._hlayout.setSpacing(0)

            self._arrow: Optional[FrameLayout.Arrow] = None
            self._title: Optional[QLabel] = None

            self._hlayout.addWidget(self.initArrow(collapsed))
            self._hlayout.addWidget(self.initTitle(title))

        def initArrow(self, collapsed: bool) -> "FrameLayout.Arrow":
            self._arrow = FrameLayout.Arrow(collapsed=collapsed)
            self._arrow.setStyleSheet("border:0px")

            return self._arrow

        def initTitle(self, title: Optional[str] = None) -> QLabel:
            self._title = QLabel(title)
            self._title.setMinimumHeight(24)
            self._title.move(QPoint(24, 0))
            self._title.setStyleSheet("border:0px")

            return self._title

        @Slot(QPaintEvent)
        def paintEvent(self, event: QPaintEvent) -> None:
            super().paintEvent(event)

        @Slot(QPaintEvent)
        def mousePressEvent(self, event: QMouseEvent) -> None:
            self.clicked.emit(event)

            return super().mousePressEvent(event)

    def __init__(self, parent: Optional[QWidget] = None, title: Optional[str] = None) -> None:
        super().__init__(parent)

        self._is_collasped = True
        self._title_frame: Optional[FrameLayout.TitleFrame] = None
        self._content = QWidget()
        self._content_layout = QVBoxLayout()

        self._main_v_layout = QVBoxLayout(self)
        self._main_v_layout.addWidget(self.initTitleFrame(title, self._is_collasped))
        self._main_v_layout.addWidget(self.initContent(self._is_collasped))

        self.initCollapsable()

    def initTitleFrame(self, title: Optional[str] = None, collapsed: bool = True) -> "TitleFrame":
        self._title_frame = self.TitleFrame(title=title, collapsed=collapsed)

        return self._title_frame

    def initContent(self, collapsed: bool = True) -> QWidget:
        self._content.setLayout(self._content_layout)
        self._content.setVisible(not collapsed)

        return self._content

    def addWidget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def addLayout(self, layout: QLayout) -> None:
        self._content_layout.addLayout(layout)

    def initCollapsable(self) -> None:
        if self._title_frame:
            self._title_frame.clicked.connect(self.toggleCollapsed)

    def toggleCollapsed(self) -> None:
        self._content.setVisible(self._is_collasped)
        self._is_collasped = not self._is_collasped
        if self._title_frame and self._title_frame._arrow:
            self._title_frame._arrow.setArrow(self._is_collasped)
