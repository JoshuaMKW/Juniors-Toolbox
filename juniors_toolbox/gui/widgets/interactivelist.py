import time

from typing import List, Optional, Union

from PySide6.QtCore import QPoint, Qt, Slot, QMimeData, QItemSelectionModel
from PySide6.QtGui import QAction, QKeyEvent, QMouseEvent, QDragMoveEvent, QDragEnterEvent, QDragLeaveEvent, QDrag, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem,
                               QMenu, QWidget, QApplication)


class InteractiveListWidgetItem(QListWidgetItem):
    _prevName_: str
    _newItem_: bool

    def __init__(self, item: Union["InteractiveListWidgetItem", str], type: int = QListWidgetItem.Type):
        if isinstance(item, InteractiveListWidgetItem):
            super().__init__(item)
        else:
            super().__init__(item, type=type)
        self.setFlags(
            Qt.ItemIsSelectable |
            Qt.ItemIsEnabled |
            Qt.ItemIsEditable |
            Qt.ItemIsDragEnabled
        )

        self._prevName_ = ""
        self._newItem_ = True

    def clone(self) -> "InteractiveListWidgetItem":
        item = InteractiveListWidgetItem(self)
        return item


class InteractiveListWidget(QListWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.itemChanged.connect(self.rename_item)
        self.itemDoubleClicked.connect(self.__handle_double_click)
        self.customContextMenuRequested.connect(self.custom_context_menu)

        self.__dragHoverItem: InteractiveListWidgetItem = None
        self.__dragPreSelected = False

    def get_context_menu(self, point: QPoint) -> QMenu:
        # Infos about the node selected.
        item: InteractiveListWidgetItem = self.itemAt(point)
        if item is None:
            return

        # We build the menu.
        menu = QMenu(self)

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_items(self.selectedItems())
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item)
        )
        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_items(self.selectedItems())
        )

        menu.addAction(deleteAction)
        menu.addAction(renameAction)
        menu.addSeparator()
        menu.addAction(duplicateAction)

        return menu

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint):
        menu = self.get_context_menu(point)
        if menu is None:
            return
        menu.exec(self.mapToGlobal(point))

    def editItem(self, item: InteractiveListWidgetItem, new: bool = False):
        item._prevName_ = item.text()
        item._newItem_ = new
        super().editItem(item)

    @Slot(list)
    def delete_items(self, items: List[InteractiveListWidgetItem]):
        for item in items:
            self.takeItem(self.row(item))

    @Slot(InteractiveListWidgetItem, result=InteractiveListWidgetItem)
    def rename_item(self, item: InteractiveListWidgetItem) -> str:
        """
        Returns the new name of the item
        """
        if item is None:
            return ""

        name = item.text()
        if name == "":
            if item._newItem_:
                self.takeItem(self.row(item))
                return ""
            name = item._prevName_

        newName = self._resolve_name(name, item)

        self.blockSignals(True)
        item.setText(newName)
        self.blockSignals(False)

        self.setCurrentRow(self.row(item))

        item._newItem_ = False
        return newName

    @Slot(list, result=List[InteractiveListWidgetItem])
    def duplicate_items(self, items: List[InteractiveListWidgetItem]) -> InteractiveListWidgetItem:
        """
        Returns the new item
        """
        newItems = []
        for item in items:
            newName = self._resolve_name(item.text())

            self.blockSignals(True)
            newItem = item.clone()
            newItem.setText(newName)
            self.blockSignals(False)

            self.insertItem(self.row(item) + 1, newItem)
            newItems.append(newItem)
        return newItems

    def _resolve_name(self, name: str, filterItem: InteractiveListWidgetItem = None) -> str:
        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.count()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = self.item(i)
            if item == filterItem:
                continue
            if item.text().startswith(ogName):
                possibleNames.append(item.text())

        i = 0
        while True:
            if i >= len(possibleNames):
                break
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            if possibleNames[i] == name:
                name = f"{ogName}{renameContext}"
                renameContext += 1
                i = 0
            else:
                i += 1
        return name

    @Slot(InteractiveListWidgetItem)
    def __handle_double_click(self, item: InteractiveListWidgetItem):
        item._prevName_ = item.text()
        item._newItem_ = False

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent):
        self.setSelectionMode(QListWidget.MultiSelection)
        self.__dragHoverItem = self.itemAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverItem is None else self.__dragHoverItem.isSelected()
        event.acceptProposedAction()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent):
        item = self.itemAt(event.pos())
        if item != self.__dragHoverItem:
            if not self.__dragPreSelected:
                self.setSelection(
                    self.visualItemRect(self.__dragHoverItem),
                    QItemSelectionModel.Deselect
                )
            self.__dragHoverItem = item
            self.__dragPreSelected = False if item is None else item.isSelected()

        if not self.__dragHoverItem in self.selectedItems():
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Select
            )

        event.acceptProposedAction()

    @Slot(QDragLeaveEvent)
    def dragLeaveEvent(self, event: QDragLeaveEvent):
        if self.__dragHoverItem is None:
            event.accept()

        if not self.__dragPreSelected:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Deselect
            )
        self.__dragHoverItem = None
        self.__dragPreSelected = False
        self.setSelectionMode(QListWidget.SingleSelection)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        mouseButton = event.button()
        modifiers = QApplication.keyboardModifiers()
        if mouseButton == Qt.LeftButton:
            if modifiers == Qt.ShiftModifier:
                event.accept()
                return
            elif modifiers == Qt.ControlModifier:
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        mouseButton = event.button()
        mousePos = event.pos()
        modifiers = QApplication.keyboardModifiers()
        item = self.itemAt(mousePos)
        if mouseButton == Qt.LeftButton:
            if modifiers == Qt.ShiftModifier:
                self.__handle_shift_click(item)
                event.accept()
                return
            elif modifiers == Qt.ControlModifier:
                self.__handle_ctrl_click(item)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete:
            self.delete_items(self.selectedItems())
            event.accept()
            return

        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_C:
                names = [i.text() for i in self.selectedItems()]
                QApplication.clipboard().setText("__items__\n" + "\n".join(names))
            elif key == Qt.Key_V:
                text = QApplication.clipboard().text()
                names = text.split("\n")
                if names[0] != "__items__":
                    return
                for name in names:
                    items = self.findItems(name, Qt.MatchExactly)
                    if len(items) == 0:
                        continue
                    self.duplicate_items(items)
        event.accept()

    def __handle_shift_click(self, item: InteractiveListWidgetItem):
        if item is None or item.isSelected():
            return

        selectedIndexes: List[InteractiveListWidgetItem] = self.selectedIndexes(
        )
        if len(selectedIndexes) == 0:
            self.setCurrentItem(item)
            return

        curIndex = self.currentRow()
        selectedIndex = self.row(item)

        if selectedIndex < curIndex:
            rows = range(selectedIndex, curIndex+1)
        else:
            rows = range(curIndex, selectedIndex+1)

        for row in range(self.count()):
            item = self.item(row)
            item.setSelected(row in rows)

    def __handle_ctrl_click(self, item: InteractiveListWidgetItem):
        if item is None or item.isSelected():
            return

        selectedIndexes: List[InteractiveListWidgetItem] = self.selectedIndexes(
        )
        if len(selectedIndexes) == 0:
            self.setCurrentItem(item)
            return

        if item.isSelected():
            return

        item.setSelected(True)
