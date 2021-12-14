from enum import IntEnum
from typing import List, Union
from PySide2.QtCore import QRect, QSize
from PySide2.QtCore import QCoreApplication, QEvent, QObject, Qt, QMimeData, QPoint, Signal, SignalInstance, Slot
from PySide2.QtGui import QColor, QCursor, QDrag, QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QIcon, QMouseEvent, QPainter, QPixmap, QRegion
from PySide2.QtWidgets import QApplication, QFrame, QLayout, QListWidget, QMainWindow, QTabBar, QTabWidget, QTreeWidget, QTreeWidgetItem, QWidgetAction, QWidget
#from PySide2.QtWidgets import qApp as QAppInstance
from sms_bin_editor.objects.object import GameObject
from sms_bin_editor.scene import SMSScene

##
# The DetachableTabWidget adds additional functionality to Qt's QTabWidget that allows it
# to detach and re-attach tabs.
#
# Additional Features:
#   Detach tabs by
#     dragging the tabs away from the tab bar
#     double clicking the tab
#   Re-attach tabs by
#     dragging the detached tab's window into the tab bar
#     closing the detached tab's window
#   Remove tab (attached or detached) by name
#
# Modified Features:
#   Re-ordering (moving) tabs by dragging was re-implemented
#
#   Original by Stack Overflow user: Blackwood, 13/11/2017
#
#   Adapted for PySide2 
#
class DetachableTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.tabBar = self.TabBar(self)
        self.tabBar.onDetachTabSignal.connect(self.detachTab)
        self.tabBar.onMoveTabSignal.connect(self.moveTab)
        self.tabBar.detachedTabDropSignal.connect(self.detachedTabDrop)

        self.setTabBar(self.tabBar)

        # Used to keep a reference to detached tabs since their QMainWindow
        # does not have a parent
        self.detachedTabs = {}

        # Close all detached tabs if the application is closed explicitly
        QApplication.instance().aboutToQuit.connect(self.closeDetachedTabs)


    ##
    #  The default movable functionality of QTabWidget must remain disabled
    #  so as not to conflict with the added features
    def setMovable(self, movable):
        pass

    ##
    #  Move a tab from one position (index) to another
    #
    #  @param    fromIndex    the original index location of the tab
    #  @param    toIndex      the new index location of the tab
    @Slot(int, int)
    def moveTab(self, fromIndex, toIndex):
        widget = self.widget(fromIndex)
        icon = self.tabIcon(fromIndex)
        text = self.tabText(fromIndex)

        self.removeTab(fromIndex)
        self.insertTab(toIndex, widget, icon, text)
        self.setCurrentIndex(toIndex)


    ##
    #  Detach the tab by removing it's contents and placing them in
    #  a DetachedTab window
    #
    #  @param    index    the index location of the tab to be detached
    #  @param    point    the screen position for creating the new DetachedTab window
    @Slot(int, QPoint)
    def detachTab(self, index: int, point: QPoint):

        # Get the tab content
        name = self.tabText(index)
        icon = self.tabIcon(index)
        if icon.isNull():
            icon = self.window().windowIcon()
        contentWidget = self.widget(index)

        try:
            contentWidgetRect = contentWidget.frameGeometry()
        except AttributeError:
            return

        # Create a new detached tab window
        detachedTab = self.DetachedTab(name, contentWidget)
        detachedTab.setWindowModality(Qt.NonModal)
        detachedTab.setWindowIcon(icon)
        detachedTab.setGeometry(contentWidgetRect)
        detachedTab.onCloseSignal.connect(self.attachTab)
        detachedTab.onDropSignal.connect(self.tabBar.detachedTabDrop)
        detachedTab.move(point)
        detachedTab.show()


        # Create a reference to maintain access to the detached tab
        self.detachedTabs[name] = detachedTab


    ##
    #  Re-attach the tab by removing the content from the DetachedTab window,
    #  closing it, and placing the content back into the DetachableTabWidget
    #
    #  @param    contentWidget    the content widget from the DetachedTab window
    #  @param    name             the name of the detached tab
    #  @param    icon             the window icon for the detached tab
    #  @param    insertAt         insert the re-attached tab at the given index
    def attachTab(self, contentWidget, name, icon, insertAt=None):

        # Make the content widget a child of this widget
        contentWidget.setParent(self)


        # Remove the reference
        del self.detachedTabs[name]


        # Create an image from the given icon (for comparison)
        if not icon.isNull():
            try:
                tabIconPixmap = icon.pixmap(icon.availableSizes()[0])
                tabIconImage = tabIconPixmap.toImage()
            except IndexError:
                tabIconImage = None
        else:
            tabIconImage = None


        # Create an image of the main window icon (for comparison)
        if not icon.isNull():
            try:
                windowIconPixmap = self.window().windowIcon().pixmap(icon.availableSizes()[0])
                windowIconImage = windowIconPixmap.toImage()
            except IndexError:
                windowIconImage = None
        else:
            windowIconImage = None


        # Determine if the given image and the main window icon are the same.
        # If they are, then do not add the icon to the tab
        if tabIconImage == windowIconImage:
            if insertAt == None:
                index = self.addTab(contentWidget, name)
            else:
                index = self.insertTab(insertAt, contentWidget, name)
        else:
            if insertAt == None:
                index = self.addTab(contentWidget, icon, name)
            else:
                index = self.insertTab(insertAt, contentWidget, icon, name)


        # Make this tab the current tab
        if index > -1:
            self.setCurrentIndex(index)


    ##
    #  Remove the tab with the given name, even if it is detached
    #
    #  @param    name    the name of the tab to be removed
    def removeTabByName(self, name):

        # Remove the tab if it is attached
        attached = False
        for index in range(self.count()):
            if str(name) == str(self.tabText(index)):
                self.removeTab(index)
                attached = True
                break


        # If the tab is not attached, close it's window and
        # remove the reference to it
        if not attached:
            for key in self.detachedTabs:
                if str(name) == str(key):
                    self.detachedTabs[key].onCloseSignal.disconnect()
                    self.detachedTabs[key].close()
                    del self.detachedTabs[key]
                    break


    ##
    #  Handle dropping of a detached tab inside the DetachableTabWidget
    #
    #  @param    name     the name of the detached tab
    #  @param    index    the index of an existing tab (if the tab bar
    #                     determined that the drop occurred on an
    #                     existing tab)
    #  @param    dropPos  the mouse cursor position when the drop occurred
    @Slot(str, int, QPoint)
    def detachedTabDrop(self, name, index, dropPos):

        # If the drop occurred on an existing tab, insert the detached
        # tab at the existing tab's location
        if index > -1:

            # Create references to the detached tab's content and icon
            contentWidget = self.detachedTabs[name].contentWidget
            icon = self.detachedTabs[name].windowIcon()

            # Disconnect the detached tab's onCloseSignal so that it
            # does not try to re-attach automatically
            self.detachedTabs[name].onCloseSignal.disconnect()

            # Close the detached
            self.detachedTabs[name].close()

            # Re-attach the tab at the given index
            self.attachTab(contentWidget, name, icon, index)


        # If the drop did not occur on an existing tab, determine if the drop
        # occurred in the tab bar area (the area to the side of the QTabBar)
        else:

            # Find the drop position relative to the DetachableTabWidget
            tabDropPos = self.mapFromGlobal(dropPos)

            # If the drop position is inside the DetachableTabWidget...
            if self.rect().contains(tabDropPos):

                # If the drop position is inside the tab bar area (the
                # area to the side of the QTabBar) or there are not tabs
                # currently attached...
                if tabDropPos.y() < self.tabBar.height() or self.count() == 0:

                    # Close the detached tab and allow it to re-attach
                    # automatically
                    self.detachedTabs[name].close()


    ##
    #  Close all tabs that are currently detached.
    def closeDetachedTabs(self):
        listOfDetachedTabs = []

        for key in self.detachedTabs:
            listOfDetachedTabs.append(self.detachedTabs[key])

        for detachedTab in listOfDetachedTabs:
            detachedTab.close()


    ##
    #  When a tab is detached, the contents are placed into this QMainWindow.  The tab
    #  can be re-attached by closing the dialog or by dragging the window into the tab bar
    class DetachedTab(QMainWindow):
        onCloseSignal = Signal(QWidget, str, QIcon)
        onDropSignal = Signal(str, QPoint)

        def __init__(self, name, contentWidget):
            super().__init__()

            self.setObjectName(name)
            self.setWindowTitle(name)

            self.contentWidget = contentWidget
            self.setCentralWidget(self.contentWidget)
            self.contentWidget.show()

            self.windowDropFilter = self.WindowDropFilter()
            self.installEventFilter(self.windowDropFilter)
            self.windowDropFilter.onDropSignal.connect(self.windowDropSlot)


        ##
        #  Handle a window drop event
        #
        #  @param    dropPos    the mouse cursor position of the drop
        @Slot(QPoint)
        def windowDropSlot(self, dropPos):
            self.onDropSignal.emit(self.objectName(), dropPos)


        ##
        #  If the window is closed, emit the onCloseSignal and give the
        #  content widget back to the DetachableTabWidget
        #
        #  @param    event    a close event
        def closeEvent(self, event):
            self.onCloseSignal.emit(self.contentWidget, self.objectName(), self.windowIcon())


        ##
        #  An event filter class to detect a QMainWindow drop event
        class WindowDropFilter(QObject):
            onDropSignal = Signal(QPoint)

            def __init__(self):
                super().__init__()
                self.lastEvent = None


            ##
            #  Detect a QMainWindow drop event by looking for a NonClientAreaMouseMove (173)
            #  event that immediately follows a Move event
            #
            #  @param    obj    the object that generated the event
            #  @param    event  the current event
            def eventFilter(self, obj, event):

                # If a NonClientAreaMouseMove (173) event immediately follows a Move event...
                if self.lastEvent == QEvent.Move and event.type() == 173:

                    # Determine the position of the mouse cursor and emit it with the
                    # onDropSignal
                    mouseCursor = QCursor()
                    dropPos = mouseCursor.pos()
                    self.onDropSignal.emit(dropPos)
                    self.lastEvent = event.type()
                    return True

                else:
                    self.lastEvent = event.type()
                    return False


    ##
    #  The TabBar class re-implements some of the functionality of the QTabBar widget
    class TabBar(QTabBar):
        onDetachTabSignal = Signal(int, QPoint)
        onEmbedTabSignal = Signal(int, QPoint)
        onMoveTabSignal = Signal(int, int)
        detachedTabDropSignal = Signal(str, int, QPoint)

        def __init__(self, parent=None):
            QTabBar.__init__(self, parent)

            self.setAcceptDrops(True)
            self.setElideMode(Qt.ElideRight)
            self.setSelectionBehaviorOnRemove(QTabBar.SelectLeftTab)

            self.dragStartPos = QPoint()
            self.dragDropedPos = QPoint()
            self.mouseCursor = QCursor()
            self.dragInitiated = False


        ##
        #  Send the onDetachTabSignal when a tab is double clicked
        #
        #  @param    event    a mouse double click event
        def mouseDoubleClickEvent(self, event):
            event.accept()
            self.onDetachTabSignal.emit(self.tabAt(event.pos()), self.mouseCursor.pos())


        ##
        #  Set the starting position for a drag event when the mouse button is pressed
        #
        #  @param    event    a mouse press event
        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                self.dragStartPos = event.pos()

            self.dragDropedPos.setX(0)
            self.dragDropedPos.setY(0)

            self.dragInitiated = False

            QTabBar.mousePressEvent(self, event)


        ##
        #  Determine if the current movement is a drag.  If it is, convert it into a QDrag.  If the
        #  drag ends inside the tab bar, emit an onMoveTabSignal.  If the drag ends outside the tab
        #  bar, emit an onDetachTabSignal.
        #
        #  @param    event    a mouse move event
        def mouseMoveEvent(self, event: QMouseEvent):

            # Determine if the current movement is detected as a drag
            if not self.dragStartPos.isNull() and ((event.pos() - self.dragStartPos).manhattanLength() < QApplication.startDragDistance()):
                self.dragInitiated = True

            # If the current movement is a drag initiated by the left button
            if (((event.buttons() & Qt.LeftButton)) and self.dragInitiated):

                # Stop the move event
                finishMoveEvent = QMouseEvent(QEvent.MouseMove, event.pos(), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
                QTabBar.mouseMoveEvent(self, finishMoveEvent)

                # Convert the move event into a drag
                drag = QDrag(self)
                mimeData = QMimeData()
                # mimeData.setData('action', 'application/tab-detach')
                drag.setMimeData(mimeData)
                # screen = QScreen(self.parentWidget().currentWidget().winId())
                # Create the appearance of dragging the tab content
                pixmap = self.parent().widget(self.tabAt(self.dragStartPos)).grab()
                targetPixmap = QPixmap(pixmap.size())
                targetPixmap.fill(Qt.transparent)
                painter = QPainter(targetPixmap)
                painter.setOpacity(0.85)
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                drag.setPixmap(targetPixmap)

                # Initiate the drag
                dropAction = drag.exec_(Qt.MoveAction | Qt.CopyAction)


                # For Linux:  Here, drag.exec_() will not return MoveAction on Linux.  So it
                #             must be set manually
                if self.dragDropedPos.x() != 0 and self.dragDropedPos.y() != 0:
                    dropAction = Qt.MoveAction


                # If the drag completed outside of the tab bar, detach the tab and move
                # the content to the current cursor position
                if dropAction == Qt.IgnoreAction:
                    event.accept()
                    window: QMainWindow = self.parent().parent()
                    print(QRect(window.pos(), window.size()), window.mapFromGlobal(self.mouseCursor.pos()))
                    if window.rect().contains(window.mapFromGlobal(self.mouseCursor.pos())):
                        ...
                    else:
                        self.onDetachTabSignal.emit(self.tabAt(self.dragStartPos), self.mouseCursor.pos())

                # Else if the drag completed inside the tab bar, move the selected tab to the new position
                elif dropAction == Qt.MoveAction:
                    if not self.dragDropedPos.isNull():
                        event.accept()
                        self.onMoveTabSignal.emit(self.tabAt(self.dragStartPos), self.tabAt(self.dragDropedPos))
            else:
                QTabBar.mouseMoveEvent(self, event)


        ##
        #  Determine if the drag has entered a tab position from another tab position
        #
        #  @param    event    a drag enter event
        def dragEnterEvent(self, event):
            mimeData = event.mimeData()
            formats = mimeData.formats()

       #     if formats.contains('action') and mimeData.data('action') == 'application/tab-detach':
       #       event.acceptProposedAction()

            QTabBar.dragMoveEvent(self, event)


        ##
        #  Get the position of the end of the drag
        #
        #  @param    event    a drop event
        def dropEvent(self, event):
            self.dragDropedPos = event.pos()
            QTabBar.dropEvent(self, event)


        ##
        #  Determine if the detached tab drop event occurred on an existing tab,
        #  then send the event to the DetachableTabWidget
        def detachedTabDrop(self, name, dropPos):

            tabDropPos = self.mapFromGlobal(dropPos)

            index = self.tabAt(tabDropPos)

            self.detachedTabDropSignal.emit(name, index, dropPos)

class DynamicTabBar(QTabBar):
    becameEmpty: SignalInstance = Signal()
    tabGrabbed: SignalInstance = Signal(QMouseEvent, int)
    tabDropped: SignalInstance = Signal(QMouseEvent, int)
    tabExiting: SignalInstance = Signal(QMouseEvent)
    tabEntering: SignalInstance = Signal(QMouseEvent, int)

    class DragContainType(IntEnum):
        INSIDE = 0
        OUTSIDE = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.draggedPointOfsLeft = 0
        self.draggedPointOfsRight = 0
        self.draggedPointOfsUp = 0
        self.draggedPointOfsDown = 0
        self.dragContainType = DynamicTabBar.DragContainType.INSIDE
        self.dragStartIndex = -1
        self.dragImage: QPixmap = None

        self.setChangeCurrentOnDrag(True)
        self.setTabsClosable(True)
        self.setAcceptDrops(True)
        self.setDocumentMode(True)
        self.setMovable(True)

    def tabRemoved(self, index: int):
        super().tabRemoved(index)
        if self.count() <= 0:
            self.becameEmpty.emit()

    def mousePressEvent(self, e: QMouseEvent):
        super().mousePressEvent(e)

        if not (e.buttons() & Qt.LeftButton):
            return

        mousePos = e.pos()
        index = self.tabAt(mousePos)
        if index < 0:
            return

        tabRect = self.tabRect(index)
        self.draggedPointOfsLeft = tabRect.x() - mousePos.x()
        self.draggedPointOfsRight = self.draggedPointOfsLeft + tabRect.width()
        self.draggedPointOfsUp = tabRect.y() - mousePos.y()
        self.draggedPointOfsDown = self.draggedPointOfsUp + tabRect.height()
        self.dragContainType = DynamicTabBar.DragContainType.INSIDE
        self.dragStartIndex = index

        self.tabGrabbed.emit(e, index)

    def mouseReleaseEvent(self, e: QMouseEvent):
        super().mouseReleaseEvent(e)

        enterIndex = self.tabAt(QPoint(e.pos().x(), self.rect().y()))
        self.tabDropped.emit(e, enterIndex)

        self.draggedPointOfsLeft = 0
        self.draggedPointOfsRight = 0
        self.draggedPointOfsUp = 0
        self.draggedPointOfsDown = 0
        self.dragContainType = DynamicTabBar.DragContainType.INSIDE
        self.dragStartIndex = -1
        self.dragImage = None

    def mouseMoveEvent(self, e: QMouseEvent):
        super().mouseMoveEvent(e)

        self.isDragging = bool(e.buttons() & Qt.LeftButton) and self.currentIndex() != -1
        if not self.isDragging:
            return

        mousePos = e.pos()
        enterIndex = self.tabAt(QPoint(mousePos.x(), self.rect().y()))
        if enterIndex == self.dragStartIndex:
            return

        if self.dragContainType == DynamicTabBar.DragContainType.INSIDE:
            if not (0 <= mousePos.y() < 50):
                self.setCurrentIndex(enterIndex)
                self.tabExiting.emit(e)
                self.dragContainType = DynamicTabBar.DragContainType.OUTSIDE
            elif mousePos.x() + self.draggedPointOfsLeft < 0:
                self.setCurrentIndex(enterIndex)
                self.tabExiting.emit(e)
                self.dragContainType = DynamicTabBar.DragContainType.OUTSIDE
            elif mousePos.x() + self.draggedPointOfsRight > self.rect().width():
                self.setCurrentIndex(enterIndex)
                self.tabExiting.emit(e)
                self.dragContainType = DynamicTabBar.DragContainType.OUTSIDE
        else:
            if ((0 <= mousePos.y() < 50) and
                (mousePos.x() + self.draggedPointOfsLeft) >= 0 and
                (mousePos.x() + self.draggedPointOfsRight <= self.rect().width())):
                self.setCurrentIndex(enterIndex)
                self.tabEntering.emit(e, enterIndex)
                self.dragContainType = DynamicTabBar.DragContainType.INSIDE


            mimeData = QMimeData()

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setPixmap(self.dragImage)

            cursor = QCursor(Qt.OpenHandCursor)

            drag.setHotSpot(QPoint(-self.draggedPointOfsLeft, -self.draggedPointOfsUp))
            drag.setDragCursor(cursor.pixmap(),Qt.MoveAction)
            drag.exec_(Qt.MoveAction)

    def dragMoveEvent(self, event: QDragMoveEvent):
        print("**TAB** moving!")
        return super().dragMoveEvent(event)

    def dragEnterEvent(self, e: QDragEnterEvent):
        print("**TAB** entered!")
        super().dragEnterEvent(e)

    def dragLeaveEvent(self, e: QDragLeaveEvent):
        print("**TAB** leaving")
        super().dragLeaveEvent(e)

    def dropEvent(self, e: QDropEvent):
        print("**TAB** dropping")
        super().dropEvent(e)

class DynamicTabWidget(QTabWidget):
    """
    Tab widget capable of being merged with other tabs and relocated
    """

    def __init__(self, parent=None, parentLayout: QLayout = None, new: bool = None):
        super().__init__(parent)
        self.mainTabBar = DynamicTabBar(self)
        self.mainTabBar.setObjectName("mainTabBar")

        self.mainTabBar.becameEmpty.connect(lambda: self.leaveLayout())
        self.mainTabBar.tabGrabbed.connect(lambda e, index: self.grabTab(e, index))
        self.mainTabBar.tabDropped.connect(lambda e, index: self.dropTab(e, index))
        self.mainTabBar.tabEntering.connect(lambda e, index: self.connectTab(e, index))
        self.mainTabBar.tabExiting.connect(lambda e: self.disconnectTab(e))
        self.tabs = []
        self.parentLayout = parentLayout

        self.setTabBar(self.mainTabBar)
        self.setTabBarAutoHide(False)

        self.setAcceptDrops(True)
        #self.tabBar().setMouseTracking(True)
        self.setMovable(True)
        if new:
            self.setup()

    def __setstate__(self, data):
        self.__init__(new=False)
        self.setParent(data['parent'])
        for widget, tabname in data['tabs']:
            self.addTab(widget, tabname)
        self.setup()

    def __getstate__(self):
        data = {
            'parent' : self.parent(),
            'tabs' : [],
        }
        tab_list = data['tabs']
        for k in range(self.count()):
            tab_name = self.tabText(k)
            widget = self.widget(k)
            tab_list.append((widget, tab_name))
        return data

    def setup(self):
        self.prevTab = None

    """
    def mouseMoveEvent(self, e: QMouseEvent):
        print("joj")
        if e.buttons() != Qt.RightButton and e.buttons() != Qt.LeftButton:
            return

        globalPos = self.mapToGlobal(e.pos())
        tabBar = self.mainTabBar
        posInTab = tabBar.mapFromGlobal(globalPos)
        index = tabBar.tabAt(e.pos())
        if index < 0:
            return

        tabBar.draggedTab = self.widget(index)
        tabBar.draggedTabName = self.tabText(index)
        tabRect = tabBar.tabRect(index)

        pixmap = QPixmap(self.rect().size())
        pixmap.fill(QColor(0, 0, 0, 0))

        tabBar.render(pixmap, QPoint(), QRegion(tabRect))
        tabViewPoint = QPoint(0, tabBar.size().height())
        widgetTarget = self.rect()
        widgetTarget.translate(tabViewPoint)
        widgetTarget.setHeight(widgetTarget.height() - tabViewPoint.y())
        self.render(pixmap, tabViewPoint, widgetTarget)

        # Make transparent
        p = QPainter()
        p.begin(pixmap)
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.fillRect(pixmap.rect(), QColor(0, 0, 0, 120))
        p.end()

        mimeData = QMimeData()

        drag = QDrag(tabBar)
        drag.setMimeData(mimeData)
        drag.setPixmap(pixmap)

        cursor = QCursor(Qt.OpenHandCursor)

        drag.setHotSpot(e.pos() - posInTab)
        drag.setDragCursor(cursor.pixmap(),Qt.MoveAction)
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, e: QDragEnterEvent):
        print("entered!")
        print(e.source().parent())
        e.source().parent().addTab(self.mainTabBar.draggedTab, self.mainTabBar.draggedTabName)
        e.accept()

    def dragLeaveEvent(self, e: QDragLeaveEvent):
        print("leaving")
        e.accept()

    def dropEvent(self, e: QDropEvent):
        if e.source().parentWidget() == self:
            return

        print("dropping!")
        e.setDropAction(Qt.MoveAction)
        e.accept()
        tabBar: DynamicTabBar = e.source()
        self.addTab(tabBar.draggedTab, tabBar.draggedTabName)
    """

    def dragEnterEvent(self, e: QDragEnterEvent):
        print("**TAB** entered!")
        super().dragEnterEvent(e)

    def dragLeaveEvent(self, e: QDragLeaveEvent):
        print("**TAB** leaving")
        super().dragLeaveEvent(e)

    def dropEvent(self, e: QDropEvent):
        print("**TAB** dropping")
        super().dropEvent(e)

    @Slot()
    def leaveLayout(self):
        print("leaving layout!")
        #if self.parentLayout:
        #    self.parentLayout.removeWidget(self)
        #self.setVisible(False)

    @Slot(QMouseEvent, int)
    def grabTab(self, e: QMouseEvent, index: int):
        self.draggedTab = self.widget(index)
        self.draggedTabName = self.tabText(index)

        pixmap = QPixmap(self.rect().size())
        pixmap.fill(QColor(0, 0, 0, 0))

        self.mainTabBar.render(pixmap, QPoint(), QRegion(self.mainTabBar.tabRect(index)))
        tabViewPoint = QPoint(0, self.mainTabBar.size().height())
        widgetTarget = self.rect()
        widgetTarget.translate(tabViewPoint)
        widgetTarget.setHeight(widgetTarget.height() - tabViewPoint.y())
        self.render(pixmap, tabViewPoint, widgetTarget)

        # Make transparent
        p = QPainter()
        p.begin(pixmap)
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.fillRect(pixmap.rect(), QColor(0, 0, 0, 120))
        p.end()

        self.mainTabBar.dragImage = pixmap

        print(self.draggedTab, self.draggedTabName)

    @Slot(QMouseEvent, int)
    def dropTab(self, e: QMouseEvent, index: int):
        if index == self.mainTabBar.dragStartIndex:
            return

        if index == -1:
            index = 0 if e.pos().x() < self.mainTabBar.rect().x() else self.mainTabBar.count()

        self.insertTab(index, self.draggedTab, self.draggedTabName)
        self.setCurrentWidget(self.draggedTab)
        self.draggedTab = None
        self.draggedTabName = ""

    @Slot(QMouseEvent, int)
    def connectTab(self, e: QMouseEvent, index: int):
        print("connect", index, self.draggedTabName, self.draggedTab)
        self.insertTab(index, self.draggedTab, self.draggedTabName)
    
    @Slot(QMouseEvent)
    def disconnectTab(self, e: QMouseEvent):
        if self.mainTabBar.tabText(self.mainTabBar.currentIndex()) != self.draggedTabName:
            return

        print("disconnect")
        self.removeTab(self.mainTabBar.currentIndex())