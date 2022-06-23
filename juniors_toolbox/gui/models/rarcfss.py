from asyncore import read
from logging import root
import os
from pathlib import Path, PurePath
from typing import Optional, Union

from juniors_toolbox.utils.rarc import (ResourceArchive, ResourceDirectory,
                                        ResourceFile)
from PySide6.QtCore import (QAbstractItemModel, QByteArray, QDataStream, QFile, QDir, QAbstractProxyModel, QIdentityProxyModel,
                            QFileInfo, QIODevice, QMimeData, QModelIndex,
                            QObject, QPersistentModelIndex, QPoint, QRect,
                            QRectF, QRegularExpression, QSize,
                            QSortFilterProxyModel, Qt, Signal, Slot)
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QImage,
                           QIntValidator, QMouseEvent, QPainter, QPainterPath,
                           QPaintEvent, QPen, QPolygon, QStandardItem,
                           QStandardItemModel, QTextCursor, QTransform)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFileSystemModel,
                               QFileSystemModel, QFormLayout, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout,
                               QLineEdit, QMenu, QMenuBar, QPlainTextEdit,
                               QPushButton, QSizePolicy, QSplitter,
                               QVBoxLayout, QWidget)


class JSystemFSModel(QFileSystemModel):
    def hasChildren(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        if not parent.isValid():
            return False

        if super().hasChildren(parent):
            return True

        fp = self.filePath(parent)
        if not fp.endswith(".arc"):
            return False

        with open(fp, "rb") as f:
            isRARC = f.read(4) == b"RARC"

        return isRARC

    def index()