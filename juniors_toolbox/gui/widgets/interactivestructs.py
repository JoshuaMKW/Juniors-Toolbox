import time

from typing import Any, List, Optional, Sequence, Union

from PySide6.QtCore import QPoint, Qt, Slot, Signal, QMimeData, QAbstractListModel, QAbstractItemModel, QItemSelectionModel, QModelIndex, QPersistentModelIndex, QItemSelection
from PySide6.QtGui import QAction, QKeyEvent, QMouseEvent, QDragMoveEvent, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QContextMenuEvent, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QListView, QTreeView,
                               QMenu, QWidget, QApplication)

from juniors_toolbox.utils import A_Clonable


AnyModelIndex = QModelIndex | QPersistentModelIndex


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
        self._prevName_ = ""
        self._newItem_ = True
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

    def copy(self, *, deep: bool = False) -> "InteractiveTreeWidgetItem":
        item = InteractiveTreeWidgetItem(self)
        for i in range(self.childCount()):
            child: InteractiveTreeWidgetItem = self.child(i)
            item.addChild(child.copy(deep=deep))
        item.setText(0, self.text(0))
        return item


class InteractiveListWidget(QListWidget):
    itemCreated = Signal(InteractiveListWidgetItem, int)
    itemDeleted = Signal(InteractiveListWidgetItem, int)

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
            row = self.row(item)
            self.itemDeleted.emit(item, row)
            self.takeItem(row)

    @Slot(InteractiveListWidgetItem)
    def rename_item(self, item: Optional[InteractiveListWidgetItem] = None) -> str:
        """
        Returns the new name of the item
        """
        if item is None:
            return ""

        row = self.row(item)
        name = item.text()
        if name == "":
            if item._newItem_:
                self.takeItem(row)
                return ""
            name = item._prevName_

        newName = self._resolve_name(name, item)

        self.blockSignals(True)
        item.setText(newName)
        self.blockSignals(False)

        self.setCurrentRow(row)

        if item._newItem_:
            self.itemCreated.emit(item, row)

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
    itemCreated = Signal(InteractiveTreeWidgetItem, int)
    itemDeleted = Signal(InteractiveTreeWidgetItem, int)

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
            raise TypeError(
                "InteractiveTreeWidget requires InteractiveTreeWidgetItem")
        item._prevName_ = item.text(column)
        item._newItem_ = new
        super().editItem(item)

    @Slot(list)
    def delete_items(self, items: List[InteractiveTreeWidgetItem]):
        for item in items:
            self.itemDeleted.emit(item, item.parent().indexOfChild(item))
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

        if item._newItem_:
            self.itemCreated.emit(item, item.parent().indexOfChild(item))

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


class InteractiveListView(QListView):
    indexCreated = Signal(QModelIndex)
    indexEdited = Signal(QModelIndex)
    indexDeleted = Signal(QModelIndex)
    currentSelectionChanged = Signal(QItemSelection, QItemSelection)

    PrevNameRole = Qt.UserRole + 1
    NewItemRole = Qt.UserRole + 2

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModel(QStandardItemModel())

        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.doubleClicked.connect(self.__handle_double_click)

        self.__selectedIndexes: List[int] = []
        self.__dragHoverIndex: Optional[AnyModelIndex] = None
        self.__dragPreSelected = False

    def get_context_menu(self, point: QPoint) -> Optional[QMenu]:
        # Infos about the node selected.
        index: Optional[InteractiveListWidgetItem] = self.indexAt(point)
        if index is None:
            return None

        # We build the menu.
        menu = QMenu(self)

        model = self.model()
        selectedRows = self.selectedIndexes()
        selectedIndexes: List[QModelIndex] = []
        for i in selectedRows:
            selectedIndexes.append(model.index(i, 0))

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_indexes(selectedIndexes)
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.edit(index)
        )
        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.delete_indexes(selectedIndexes)
        )

        menu.addAction(duplicateAction)
        menu.addSeparator()
        menu.addAction(renameAction)
        menu.addAction(deleteAction)

        return menu

    def create_row(self, row: int, name: str, userData: Optional[Any] = None) -> bool:
        model = self.model()
        if not model.insertRow(row):
            return False
        
        index = model.index(row, 0)
        model.setData(index, name, Qt.DisplayRole)
        model.setData(index, userData, Qt.UserRole)
        model.setData(index, name, self.PrevNameRole)
        model.setData(index, True, self.NewItemRole)
        self.selectionModel().select(index, QItemSelectionModel.ClearAndSelect)

        return True

    def clear(self) -> None:
        model = self.model()
        model.removeRows(0, model.rowCount())

    @Slot(InteractiveListWidgetItem)
    def rename_index(self, index: QModelIndex) -> str:
        """
        Returns the new name of the item
        """
        model = self.model()

        name = index.data(Qt.DisplayRole)
        isNew = index.data(self.NewItemRole)
        oldName = index.data(self.PrevNameRole)

        if name == "":
            if isNew:
                model.removeRow(index.row())
                return ""
            name = oldName

        newName = self._resolve_name(name, index)

        model.blockSignals(True)
        model.setData(index, newName, Qt.DisplayRole)
        model.blockSignals(False)

        self.selectionModel().select(index, QItemSelectionModel.ClearAndSelect)

        if isNew:
            self.indexCreated.emit(index)

        model.setData(index, False, self.NewItemRole)
        return newName

    @Slot(list)
    def duplicate_indexes(self, indexes: List[AnyModelIndex]) -> List[AnyModelIndex]:
        """
        Returns the new item
        """
        model = self.model()
        model.blockSignals(True)

        newIndexes: list[AnyModelIndex] = []
        for index in indexes:
            newName = self._resolve_name(index.data(Qt.DisplayRole))
            userData: A_Clonable = index.data(Qt.UserRole)

            newIndex = model.sibling(index.row() + 1, 0, index)
            model.setData(newIndex, newName, Qt.DisplayRole)
            model.setData(newIndex, userData.copy(deep=True), Qt.UserRole)
            model.setData(newIndex, False, self.NewItemRole)
            model.setData(newIndex, newIndex.data(
                Qt.DisplayRole), self.PrevNameRole)

            newIndexes.append(newIndex)

        model.blockSignals(False)
        return newIndexes

    @Slot(list)
    def delete_indexes(self, indexes: List[AnyModelIndex]):
        model = self.model()
        persistentIndexes: List[QPersistentModelIndex] = []
        for index in indexes:
            persistentIndexes.append(QPersistentModelIndex(index))
        for pindex in persistentIndexes:
            self.indexDeleted.emit(pindex)
            model.removeRow(pindex.row())

    def _resolve_name(self, name: str, filterItem: AnyModelIndex = None) -> str:
        model = self.model()

        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(model.rowCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = model.index(i, 0)
            if item == filterItem:
                continue
            itemText: str = item.data(Qt.DisplayRole)
            if itemText.startswith(ogName):
                possibleNames.append(itemText)

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

    @Slot(QModelIndex)
    def __handle_double_click(self, index: AnyModelIndex) -> None:
        model = self.model()
        model.setData(index, index.data(Qt.DisplayRole), self.PrevNameRole)
        model.setData(index, False, self.NewItemRole)

    @Slot(QModelIndex, int, int)
    def rowsInserted(self, parent: AnyModelIndex, start: int, end: int) -> None:
        super().rowsInserted(parent, start, end)
        for i in range(start, end+1):
            self.indexCreated.emit(self.model().index(i, 0))

    @Slot(QModelIndex, int, int)
    def rowsAboutToBeRemoved(self, parent: AnyModelIndex, start: int, end: int) -> None:
        for i in range(start, end+1):
            self.indexDeleted.emit(self.model().index(i, 0))
        super().rowsAboutToBeRemoved(parent, start, end)

    @Slot(QItemSelection, QItemSelection)
    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        super().selectionChanged(selected, deselected)
        self.currentSelectionChanged.emit(selected, deselected)

    @Slot(QModelIndex, QModelIndex, list)
    def dataChanged(self, topLeft: AnyModelIndex, bottomRight: AnyModelIndex, roles: Sequence[int] = None) -> None:
        if roles is None:
            roles = []
        super().dataChanged(topLeft, bottomRight, roles)
        for i in range(topLeft.row(), bottomRight.row()+1):
            index = self.model().index(i, 0)
            if Qt.DisplayRole in roles:
                self.rename_index(index)
            self.indexEdited.emit(index)

    @Slot(QContextMenuEvent)
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.get_context_menu(event.pos())
        if menu is None:
            return
        menu.exec(event.globalPos())

    @Slot(Qt.DropActions)
    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        self.__selectedIndexes = self.selectedIndexes()
        super().startDrag(supportedActions)

    @Slot(QDragEnterEvent)
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.__selectionMode = self.selectionMode()
        self.__selectedIndexes = self.selectedIndexes()
        self.__dragHoverIndex = self.indexAt(event.pos())
        self.__dragPreSelected = False if self.__dragHoverIndex is None else self.selectionModel().isSelected(self.__dragHoverIndex)
        self.setSelectionMode(QListWidget.MultiSelection)
        event.acceptProposedAction()

    @Slot(QDragEnterEvent)
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        index = self.indexAt(event.pos())
        if index != self.__dragHoverIndex:
            if not self.__dragPreSelected and self.__dragHoverIndex:
                self.setSelection(
                    self.visualRect(self.__dragHoverIndex),
                    QItemSelectionModel.Deselect
                )
            self.__dragHoverIndex = index
            self.__dragPreSelected = False if index is None else self.selectionModel().isSelected(index)

        if not self.__dragHoverIndex in self.__selectedIndexes:
            self.setSelection(
                self.visualRect(self.__dragHoverIndex),
                QItemSelectionModel.Select
            )
        else:
            event.ignore()
            return

        event.acceptProposedAction()

    @Slot(QDragLeaveEvent)
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        if self.__dragHoverIndex is None:
            event.accept()

        if not self.__dragPreSelected and self.__dragHoverIndex:
            self.setSelection(
                self.visualRect(self.__dragHoverIndex),
                QItemSelectionModel.Deselect
            )

        self.__dragHoverIndex = None
        self.__dragPreSelected = False
        self.setSelectionMode(self.__selectionMode)
        event.accept()

    @Slot(QDropEvent)
    def dropEvent(self, event: QDropEvent) -> None:
        if self.__dragHoverIndex and not self.__dragPreSelected:
            self.selectionModel().select(self.__dragHoverIndex, QItemSelectionModel.Deselect)
        self.__dragHoverIndex = None
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
        index = self.indexAt(mousePos)
        if mouseButton == Qt.LeftButton:
            if modifiers == Qt.ShiftModifier:
                self.__handle_shift_click(index)
                event.accept()
                return
            elif modifiers == Qt.ControlModifier:
                self.__handle_ctrl_click(index)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    @Slot(QMouseEvent)
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        model = self.model()
        selectedRows = self.selectedIndexes()
        selectedIndexes: List[QModelIndex] = []
        for i in selectedRows:
            selectedIndexes.append(model.index(i, 0))
        if event.key() == Qt.Key_Delete:
            self.delete_indexes(selectedIndexes)
            event.accept()
            return

        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_C:
                names = [index.data(Qt.DisplayRole)
                         for index in selectedIndexes]
                QApplication.clipboard().setText("__indexes__\n" + "\n".join(names))
            elif key == Qt.Key_V:
                text = QApplication.clipboard().text()
                names = text.split("\n")
                if names[0] != "__indexes__":
                    return
                indexes: list[QModelIndex] = []
                for row in range(model.rowCount()):
                    index = model.index(row, 0)
                    if index.data(Qt.DisplayRole) in names:
                        indexes.append(index)
                if len(indexes) == 0:
                    event.ignore()
                    return
                self.duplicate_indexes(indexes)
        event.accept()

    def __handle_shift_click(self, index: QModelIndex) -> None:
        model = self.model()
        selectionModel = self.selectionModel()

        if index is None or selectionModel.isSelected(index):
            return

        selectedIndexes = self.selectedIndexes()
        if len(selectedIndexes) == 0:
            self.setCurrentIndex(index)
            return

        curIndex = self.currentIndex()
        if index.row() < curIndex.row():
            rows = range(index.row(), curIndex+1)
        else:
            rows = range(curIndex, index.row() + 1)

        for row in range(model.rowCount()):
            selectionModel.select(
                index,
                QItemSelectionModel.Select if row in rows else QItemSelectionModel.Deselect
            )

    def __handle_ctrl_click(self, index: QModelIndex) -> None:
        selectionModel = self.selectionModel()
        if index is None or selectionModel.isSelected(index):
            return

        selectedIndexes = self.selectedIndexes()
        if len(selectedIndexes) == 0:
            self.setCurrentIndex(index)
            return

        if selectionModel.isSelected(index):
            return

        selectionModel.select(index, QItemSelectionModel.Select)
