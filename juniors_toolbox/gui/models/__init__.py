from typing import Union
from PySide6.QtCore import Qt, QAbstractItemModel, QAbstractListModel, QModelIndex, QPersistentModelIndex


class UniqueListModel(QAbstractListModel):
    def _resolve_name(self, name: str, filterItem: Union[QModelIndex, QPersistentModelIndex] = None) -> str:
        renameContext = 1
        ogName = name

        possibleNames = []
        for i in range(self.rowCount()):
            if renameContext > 100:
                raise FileExistsError(
                    "Name exists beyond 100 unique iterations!")
            item = self.index(i, 0)
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