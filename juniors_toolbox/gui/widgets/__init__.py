from abc import ABCMeta

from PySide6.QtWidgets import QWidget


class ABCMetaWidget(ABCMeta, type(QWidget)):
    """
    Metaclass designed for QWidgets
    """
    ...
