from typing import Optional, Union

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem,
                               QMenu, QWidget)


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
        self.itemChanged.connect(self.rename_item)
        self.itemDoubleClicked.connect(self.__handle_double_click)
        self.customContextMenuRequested.connect(self.custom_context_menu)

    def get_context_menu(self, point: QPoint) -> QMenu:
        # Infos about the node selected.
        item: InteractiveListWidgetItem = self.itemAt(point)
        if item is None:
            return

        # We build the menu.
        menu = QMenu(self)

        deleteAction = QAction("Delete", self)
        deleteAction.triggered.connect(
            lambda clicked=None: self.takeItem(self.row(item))
        )
        renameAction = QAction("Rename", self)
        renameAction.triggered.connect(
            lambda clicked=None: self.editItem(item)
        )
        duplicateAction = QAction("Duplicate", self)
        duplicateAction.triggered.connect(
            lambda clicked=None: self.duplicate_item(item)
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

    @Slot(InteractiveListWidgetItem, result=str)
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

    @Slot(InteractiveListWidgetItem, result=str)
    def duplicate_item(self, item: InteractiveListWidgetItem) -> InteractiveListWidgetItem:
        """
        Returns the new item
        """
        if item is None:
            return None

        newName = self._resolve_name(item.text())

        self.blockSignals(True)
        newItem = item.clone()
        newItem.setText(newName)
        self.blockSignals(False)

        self.insertItem(self.row(item) + 1, newItem)

        return newItem

    def _resolve_name(self, name: str, filterItem: InteractiveListWidgetItem = None) -> str:
        # for i, char in enumerate(name[::-1]):
        #    if not char.isdecimal():
        #        name = name[:len(name)-i]
        #        break

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

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete:
            self.takeItem(self.currentRow())