import time

from typing import List, Optional, Union

from PySide6.QtCore import QPoint, Qt, Slot, QMimeData, QItemSelectionModel
from PySide6.QtGui import QAction, QKeyEvent, QMouseEvent, QDragMoveEvent, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QDrag, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                               QMenu, QWidget, QApplication)

from juniors_toolbox.utils import A_Clonable


class InteractiveListWidgetItem(QListWidgetItem):
    _prevName_: str
    _newItem_: bool

    def __init__(self, item: Union["InteractiveListWidgetItem", str], type: int = 0) -> None:
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

    def copy(self, *, deep: bool = False) -> "InteractiveListWidgetItem":
        item = InteractiveListWidgetItem(self)
        return item


class InteractiveTreeWidgetItem(QTreeWidgetItem):
    _prevName_: str
    _newItem_: bool

    def __init__(self, item: Union["InteractiveTreeWidgetItem", str], type: int = 0) -> None:
        if isinstance(item, InteractiveTreeWidgetItem):
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

    def copy(self, *, deep: bool = False) -> "InteractiveTreeWidgetItem":
        item = InteractiveTreeWidgetItem(self)
        return item


class InteractiveListWidget(QListWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.itemChanged.connect(self.rename_item)
        self.itemDoubleClicked.connect(self.__handle_double_click)
        self.customContextMenuRequested.connect(self.custom_context_menu)

        self.__selectedItems: List[InteractiveListWidgetItem] = []
        self.__dragHoverItem: Optional[InteractiveListWidgetItem] = None
        self.__dragPreSelected = False

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        item: Optional[InteractiveListWidgetItem] = self.itemAt(point)
        if item is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_items(self.selectedItems())
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item)
        )
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_items(self.selectedItems())
        )

        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(renameAction)
        menu.addAction(deleteAction)

        return menu

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint) -> None:
        menu = self.get_context_menu(point)
        if menu is None:
            return
        menu.exec(self.mapToGlobal(point))

    def editItem(self, item: InteractiveListWidgetItem, new: bool = False) -> None:
        item._prevName_ = item.text()
        item._newItem_ = new
        super().editItem(item)

    @Slot(list)
    def delete_items(self, items: List[InteractiveListWidgetItem]):
        for item in items:
            self.takeItem(self.row(item))

    @Slot(InteractiveListWidgetItem)
    def rename_item(self, item: Optional[InteractiveListWidgetItem] = None) -> str:
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

    @Slot(list)
    def duplicate_items(self, items: List[InteractiveListWidgetItem]) -> List[InteractiveListWidgetItem]:
        """
        Returns the new item
        """
        newItems = []
        for item in items:
            newName = self._resolve_name(item.text())

            self.blockSignals(True)
            newItem = item.copy()
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
    def __handle_double_click(self, item: InteractiveListWidgetItem) -> None:
        item._prevName_ = item.text()
        item._newItem_ = False

    @Slot(Qt.DropActions)
    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        self.__selectedItems = self.selectedItems()
        super().startDrag(supportedActions)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.__selectionMode = self.selectionMode()
        self.__selectedItems = self.selectedItems()
        self.__dragHoverItem = self.itemAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverItem is None else self.__dragHoverItem.isSelected()
        self.setSelectionMode(QListWidget.MultiSelection)
        event.acceptProposedAction()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        item = self.itemAt(event.pos())
        if item != self.__dragHoverItem:
            if not self.__dragPreSelected and self.__dragHoverItem:
                self.setSelection(
                    self.visualItemRect(self.__dragHoverItem),
                    QItemSelectionModel.Deselect
                )
            self.__dragHoverItem = item
            self.__dragPreSelected = False if item is None else item.isSelected()

        if not self.__dragHoverItem in self.__selectedItems:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Select
            )
        else:
            event.ignore()
            return

        event.acceptProposedAction()

    @Slot(QDragLeaveEvent)
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        if self.__dragHoverItem is None:
            event.accept()

        if not self.__dragPreSelected and self.__dragHoverItem:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Deselect
            )

        self.__dragHoverItem = None
        self.__dragPreSelected = False
        self.setSelectionMode(self.__selectionMode)
        event.accept()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        if self.__dragHoverItem and not self.__dragPreSelected:
            self.__dragHoverItem.setSelected(False)
        self.__dragHoverItem = None
        self.__dragPreSelected = False
        self.setSelectionMode(self.__selectionMode)
        super().dropEvent(event)

    @Slot(QMouseEvent)
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

    @Slot(QMouseEvent)
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

    @Slot(QMouseEvent)
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
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

    def __handle_shift_click(self, item: InteractiveListWidgetItem) -> None:
        if item is None or item.isSelected():
            return

        selectedIndexes = self.selectedIndexes()
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

    def __handle_ctrl_click(self, item: InteractiveListWidgetItem) -> None:
        if item is None or item.isSelected():
            return

        selectedIndexes = self.selectedIndexes()
        if len(selectedIndexes) == 0:
            self.setCurrentItem(item)
            return

        if item.isSelected():
            return

        item.setSelected(True)

class InteractiveTreeWidget(QTreeWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.itemChanged.connect(self.rename_item)
        self.itemDoubleClicked.connect(self.__handle_double_click)
        self.customContextMenuRequested.connect(self.custom_context_menu)

        self.__selectedItems: List[InteractiveTreeWidgetItem] = []
        self.__dragHoverItem: Optional[InteractiveTreeWidgetItem] = None
        self.__dragPreSelected = False

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        item: Optional[InteractiveTreeWidgetItem] = self.itemAt(point)
        if item is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_items(self.selectedItems())
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item, 0)
        )
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_items(self.selectedItems())
        )

        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(renameAction)
        menu.addAction(deleteAction)

        return menu

    @Slot(QPoint)
    def custom_context_menu(self, point: QPoint) -> None:
        menu = self.get_context_menu(point)
        if menu is None:
            return
        menu.exec(self.mapToGlobal(point))

    def editItem(self, item: QTreeWidgetItem, column: int = 0, new: bool = False) -> None:
        if not isinstance(item, InteractiveTreeWidgetItem):
            raise TypeError("InteractiveTreeWidget requires InteractiveTreeWidgetItem")
        item._prevName_ = item.text(column)
        item._newItem_ = new
        super().editItem(item)

    @Slot(list)
    def delete_items(self, items: List[InteractiveTreeWidgetItem]):
        for item in items:
            item.parent().removeChild(item)

    @Slot(InteractiveTreeWidgetItem)
    def rename_item(self, item: Optional[InteractiveTreeWidgetItem] = None) -> str:
        """
        Returns the new name of the item
        """
        if item is None:
            return ""

        name = item.text(0)
        if name == "":
            if item._newItem_:
                item.parent().removeChild(item)
                return ""
            item.setText(0, item._prevName_)

        newName = self._resolve_name(item, item)

        self.blockSignals(True)
        item.setText(0, newName)
        self.blockSignals(False)

        item.setSelected(True)

        item._newItem_ = False
        return newName

    @Slot(list)
    def duplicate_items(self, items: List[InteractiveTreeWidgetItem]) -> List[InteractiveTreeWidgetItem]:
        """
        Returns the new item
        """
        newItems = []
        for item in items:
            newName = self._resolve_name(item)

            self.blockSignals(True)
            newItem = item.copy()
            newItem.setText(0, newName)
            self.blockSignals(False)

            parent = item.parent()
            parent.insertChild(parent.indexOfChild(item) + 1, newItem)
            newItems.append(newItem)
        return newItems

    def _resolve_name(self, item: InteractiveTreeWidgetItem, filterItem: InteractiveTreeWidgetItem = None) -> str:
        renameContext = 1
        name = item.text(0)
        ogName = name

        possibleNames = []
        for i in range(item.parent().childCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            _item = item.parent().child(i)
            if _item == filterItem:
                continue
            if _item.text(0).startswith(ogName):
                possibleNames.append(_item.text(0))

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

    @Slot(InteractiveTreeWidgetItem)
    def __handle_double_click(self, item: InteractiveTreeWidgetItem) -> None:
        item._prevName_ = item.text(0)
        item._newItem_ = False

    @Slot(Qt.DropActions)
    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        self.__selectedItems = self.selectedItems()
        super().startDrag(supportedActions)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.__selectionMode = self.selectionMode()
        self.__selectedItems = self.selectedItems()
        self.__dragHoverItem = self.itemAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverItem is None else self.__dragHoverItem.isSelected()
        self.setSelectionMode(QListWidget.MultiSelection)
        event.acceptProposedAction()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        item = self.itemAt(event.pos())
        if item != self.__dragHoverItem:
            if not self.__dragPreSelected and self.__dragHoverItem:
                self.setSelection(
                    self.visualItemRect(self.__dragHoverItem),
                    QItemSelectionModel.Deselect
                )
            self.__dragHoverItem = item
            self.__dragPreSelected = False if item is None else item.isSelected()

        if not self.__dragHoverItem in self.__selectedItems:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Select
            )
        else:
            event.ignore()
            return

        event.acceptProposedAction()

    @Slot(QDragLeaveEvent)
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        if self.__dragHoverItem is None:
            event.accept()

        if not self.__dragPreSelected and self.__dragHoverItem:
            self.setSelection(
                self.visualItemRect(self.__dragHoverItem),
                QItemSelectionModel.Deselect
            )

        self.__dragHoverItem = None
        self.__dragPreSelected = False
        self.setSelectionMode(self.__selectionMode)
        event.accept()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        if self.__dragHoverItem and not self.__dragPreSelected:
            self.__dragHoverItem.setSelected(False)
        self.__dragHoverItem = None
        self.__dragPreSelected = False
        self.setSelectionMode(self.__selectionMode)
        super().dropEvent(event)

    @Slot(QMouseEvent)
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Delete:
            self.delete_items(self.selectedItems())
            event.accept()
            return

        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_C:
                names = [i.text(0) for i in self.selectedItems()]
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
