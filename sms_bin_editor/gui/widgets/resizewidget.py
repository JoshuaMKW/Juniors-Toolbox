from PyQt5 import QtCore, QtGui, QtWidgets

Left, Right = 1, 2
Top, Bottom = 4, 8
TopLeft = Top|Left
TopRight = Top|Right
BottomRight = Bottom|Right
BottomLeft = Bottom|Left

class ResizableLabel(QtWidgets.QWidget):
    resizeMargin = 4
    # note that the Left, Top, Right, Bottom constants cannot be used as class
    # attributes if you want to use list comprehension for better performance,
    # and that's due to the variable scope behavior on Python 3
    sections = [x|y for x in (Left, Right) for y in (Top, Bottom)]
    cursors = {
        Left: QtCore.Qt.SizeHorCursor, 
        Top|Left: QtCore.Qt.SizeFDiagCursor, 
        Top: QtCore.Qt.SizeVerCursor, 
        Top|Right: QtCore.Qt.SizeBDiagCursor, 
        Right: QtCore.Qt.SizeHorCursor, 
        Bottom|Right: QtCore.Qt.SizeFDiagCursor, 
        Bottom: QtCore.Qt.SizeVerCursor, 
        Bottom|Left: QtCore.Qt.SizeBDiagCursor, 
    }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.startPos = self.section = None
        self.rects = {section:QtCore.QRect() for section in self.sections}

        # mandatory for cursor updates
        self.setMouseTracking(True)

        # just for demonstration purposes
        background = QtGui.QPixmap(3, 3)
        background.fill(QtCore.Qt.transparent)
        qp = QtGui.QPainter(background)
        pen = QtGui.QPen(QtCore.Qt.darkGray, .5)
        qp.setPen(pen)
        qp.drawLine(0, 2, 2, 0)
        qp.end()
        self.background = QtGui.QBrush(background)

    def updateCursor(self, pos):
        for section, rect in self.rects.items():
            if pos in rect:
                self.setCursor(self.cursors[section])
                self.section = section
                return section
        self.unsetCursor()

    def adjustSize(self):
        del self._sizeHint
        super().adjustSize()

    def minimumSizeHint(self):
        try:
            return self._sizeHint
        except:
            return super().minimumSizeHint()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.updateCursor(event.pos()):
                self.startPos = event.pos()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.startPos is not None:
            delta = event.pos() - self.startPos
            if self.section & Left:
                delta.setX(-delta.x())
            elif not self.section & (Left|Right):
                delta.setX(0)
            if self.section & Top:
                delta.setY(-delta.y())
            elif not self.section & (Top|Bottom):
                delta.setY(0)
            newSize = QtCore.QSize(self.width() + delta.x(), self.height() + delta.y())
            self._sizeHint = newSize
            self.startPos = event.pos()
            self.updateGeometry()
        elif not event.buttons():
            self.updateCursor(event.pos())
        super().mouseMoveEvent(event)
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.updateCursor(event.pos())
        self.startPos = self.section = None
        self.setMinimumSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        outRect = self.rect()
        inRect = self.rect().adjusted(self.resizeMargin, self.resizeMargin, -self.resizeMargin, -self.resizeMargin)
        self.rects[Left] = QtCore.QRect(outRect.left(), inRect.top(), self.resizeMargin, inRect.height())
        self.rects[TopLeft] = QtCore.QRect(outRect.topLeft(), inRect.topLeft())
        self.rects[Top] = QtCore.QRect(inRect.left(), outRect.top(), inRect.width(), self.resizeMargin)
        self.rects[TopRight] = QtCore.QRect(inRect.right(), outRect.top(), self.resizeMargin, self.resizeMargin)
        self.rects[Right] = QtCore.QRect(inRect.right(), self.resizeMargin, self.resizeMargin, inRect.height())
        self.rects[BottomRight] = QtCore.QRect(inRect.bottomRight(), outRect.bottomRight())
        self.rects[Bottom] = QtCore.QRect(inRect.left(), inRect.bottom(), inRect.width(), self.resizeMargin)
        self.rects[BottomLeft] = QtCore.QRect(outRect.bottomLeft(), inRect.bottomLeft()).normalized()

    # ---- optional, mostly for demonstration purposes ----

    def paintEvent(self, event):
        super().paintEvent(event)
        qp = QtGui.QPainter(self)
        if self.underMouse() and self.section:
            qp.save()
            qp.setPen(QtCore.Qt.lightGray)
            qp.setBrush(self.background)
            qp.drawRect(self.rect().adjusted(0, 0, -1, -1))
            qp.restore()
        qp.drawText(self.rect(), QtCore.Qt.AlignCenter, '{}x{}'.format(self.width(), self.height()))

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


class Test(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QGridLayout(self)

        for row in range(3):
            for column in range(3):
                if (row, column) == (1, 1):
                    continue
                layout.addWidget(QtWidgets.QPushButton(), row, column)

        label = ResizableLabel()
        layout.addWidget(label, 1, 1)

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = Test()
    w.show()
    sys.exit(app.exec_())