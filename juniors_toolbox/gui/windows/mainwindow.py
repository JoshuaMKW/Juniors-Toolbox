import pickle
import subprocess
import sys
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, Iterable, List, Union

from PySide2.QtCore import QCoreApplication, QEvent, QMetaObject, QMimeData, QObject, QRect, QSize, Qt, Signal, SignalInstance
from PySide2.QtGui import QDrag, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QFont, QIcon, QMouseEvent
from PySide2.QtWidgets import (QAction, QApplication, QDialog, QFileDialog,
                               QFrame, QGridLayout, QHBoxLayout, QMainWindow, QMenu, QMenuBar, QMessageBox, QScrollArea, QSizePolicy,
                               QTabWidget, QVBoxLayout, QWidget)
from juniors_toolbox import __name__, __version__
from juniors_toolbox.gui.tabs import TabWidgetManager
from juniors_toolbox.gui.tabs.object import (ObjectHierarchyWidget, ObjectPropertiesWidget,
                                               ObjectHierarchyWidgetItem)
from juniors_toolbox.gui.tabs.rail import RailListWidget
from juniors_toolbox.utils.filesystem import get_program_folder, resource_path

class ExplicitMenuAction(QAction):
    clicked: SignalInstance = Signal(str, bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.triggered.connect(self._named_trigger)
        self.toggled.connect(self._named_toggle)

    def _named_trigger(self):
        self.clicked.emit(self.text(), self.isChecked() if self.isCheckable() else True)

    def _named_toggle(self):
        self.clicked.emit(self.text(), self.isChecked())


class MainWindow(QMainWindow):
    class Themes(IntEnum):
        LIGHT = 0
        DARK = 1

    tabActionRequested: SignalInstance = Signal(str, bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName(self.__class__.__name__)
        self.setAnimated(True)
        self.setTabShape(QTabWidget.Rounded)

        self.resize(494, 575)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMinimumSize(QSize(694, 675))

        self.target = None
        self.setAcceptDrops(True)

        self.reset_ui()

    def reset_ui(self):
        self.centerWidget = QWidget(self)
        self.centerWidget.setObjectName("centerWidget")

        self.setCentralWidget(self.centerWidget)

        self.mainLayout = QGridLayout()
        self.centerWidget.setLayout(self.mainLayout)

        self.setWindowIcon(QIcon(str(resource_path("gui/icons/program.ico"))))

        # -- MENUBAR -- #
        self.actionEmptyMap = QAction(self)
        self.actionEmptyMap.setObjectName(u"actionEmptyMap")
        self.actionMakeArray = QAction(self)
        self.actionMakeArray.setObjectName(u"actionMakeArray")
        self.actionMoveToCamera = QAction(self)
        self.actionMoveToCamera.setObjectName(u"actionMoveToCamera")
        self.actionMoveToMario = QAction(self)
        self.actionMoveToMario.setObjectName(u"actionMoveToMario")
        self.actionMoveToGround = QAction(self)
        self.actionMoveToGround.setObjectName(u"actionMoveToGround")
        self.actionFindDiscrepancy = QAction(self)
        self.actionFindDiscrepancy.setObjectName(u"actionFindDiscrepancy")
        self.actionRepairScene = QAction(self)
        self.actionRepairScene.setObjectName(u"actionRepairScene")
        self.actionNew = QAction(self)
        self.actionNew.setObjectName(u"actionNew")
        self.actionOpen = QAction(self)
        self.actionOpen.setObjectName(u"actionOpen")
        self.actionSave = QAction(self)
        self.actionSave.setObjectName(u"actionSave")
        self.actionSaveAs = QAction(self)
        self.actionSaveAs.setObjectName(u"actionSaveAs")
        self.actionClose = QAction(self)
        self.actionClose.setObjectName(u"actionClose")
        self.actionObjectHierarchy = ExplicitMenuAction(self)
        self.actionObjectHierarchy.setObjectName(u"actionObjectHierarchy")
        self.actionObjectProperties = ExplicitMenuAction(self)
        self.actionObjectProperties.setObjectName(u"actionObjectProperties")
        self.actionRailList = ExplicitMenuAction(self)
        self.actionRailList.setObjectName(u"actionRailList")
        self.actionRailEditor = ExplicitMenuAction(self)
        self.actionRailEditor.setObjectName(u"actionRailEditor")
        self.actionBMGEditor = ExplicitMenuAction(self)
        self.actionBMGEditor.setObjectName(u"actionBMGEditor")
        self.actionPRMEditor = ExplicitMenuAction(self)
        self.actionPRMEditor.setObjectName(u"actionPRMEditor")
        self.actionDemoEditor = ExplicitMenuAction(self)
        self.actionDemoEditor.setObjectName(u"actionDemoEditor")
        self.actionRawDataViewer = ExplicitMenuAction(self)
        self.actionRawDataViewer.setObjectName(u"actionRawDataViewer")
        self.actionSceneRenderer = ExplicitMenuAction(self)
        self.actionSceneRenderer.setObjectName(u"actionSceneRenderer")
        self.actionCheckUpdate = QAction(self)
        self.actionCheckUpdate.setObjectName(u"actionCheckUpdate")
        self.actionTutorial = QAction(self)
        self.actionTutorial.setObjectName(u"actionTutorial")
        self.actionReportBug = QAction(self)
        self.actionReportBug.setObjectName(u"actionReportBug")
        self.actionAbout = QAction(self)
        self.actionAbout.setObjectName(u"actionAbout")

        self.menubar = QMenuBar(self)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1009, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuEdit = QMenu(self.menubar)
        self.menuEdit.setObjectName(u"menuEdit")
        self.menuObject = QMenu(self.menuEdit)
        self.menuObject.setObjectName(u"menuObject")
        self.menuTools = QMenu(self.menubar)
        self.menuTools.setObjectName(u"menuTools")
        self.menuWizard = QMenu(self.menubar)
        self.menuWizard.setObjectName(u"menuWizard")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        self.menuWindow = QMenu(self.menubar)
        self.menuWindow.setObjectName(u"menuWindow")
        self.setMenuBar(self.menubar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuWizard.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menubar.addAction(self.menuWindow.menuAction())
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSaveAs)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionClose)
        self.menuEdit.addAction(self.actionEmptyMap)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.menuObject.menuAction())
        self.menuObject.addAction(self.actionMakeArray)
        self.menuObject.addSeparator()
        self.menuObject.addAction(self.actionMoveToCamera)
        self.menuObject.addAction(self.actionMoveToMario)
        self.menuObject.addAction(self.actionMoveToGround)
        self.menuTools.addAction(self.actionFindDiscrepancy)
        self.menuTools.addAction(self.actionRepairScene)
        self.menuHelp.addAction(self.actionCheckUpdate)
        self.menuHelp.addAction(self.actionReportBug)
        self.menuHelp.addSeparator()
        self.menuHelp.addAction(self.actionTutorial)
        self.menuHelp.addSeparator()
        self.menuHelp.addAction(self.actionAbout)
        self.menuWindow.addAction(self.actionObjectHierarchy)
        self.menuWindow.addAction(self.actionObjectProperties)
        self.menuWindow.addAction(self.actionRailList)
        self.menuWindow.addAction(self.actionRailEditor)
        self.menuWindow.addAction(self.actionBMGEditor)
        self.menuWindow.addAction(self.actionPRMEditor)
        self.menuWindow.addAction(self.actionDemoEditor)
        self.menuWindow.addAction(self.actionRawDataViewer)
        self.menuWindow.addAction(self.actionSceneRenderer)

        for action in self.menuWindow.actions():
            action.clicked.connect(self.tabActionRequested)
        
        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def eventFilter(self, watched, event: QEvent):
        if event.type() == QEvent.MouseButtonPress:
            self.mousePressEvent(event)
        elif event.type() == QEvent.MouseMove:
            self.mouseMoveEvent(event)
        elif event.type() == QEvent.MouseButtonRelease:
            self.mouseReleaseEvent(event)
        return super().eventFilter(watched, event)

    def get_index(self, pos):
        for i in range(self.mainLayout.count()):
            if self.mainLayout.itemAt(i).geometry().contains(pos) and i != self.target:
                return i

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.target = self.get_index(event.windowPos().toPoint())
        else:
            self.target = None

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and issubclass(self.target.__class__, QObject):
            drag = QDrag(self.mainLayout.itemAt(self.target))
            pix = self.mainLayout.itemAt(self.target).itemAt(0).widget().grab()
            mimedata = QMimeData()
            mimedata.setImageData(pix)
            drag.setMimeData(mimedata)
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec_()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.target = None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasImage():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not event.source().geometry().contains(event.pos()):
            source = self.get_index(event.pos())
            if source is None:
                return

            i, j = max(self.target, source), min(self.target, source)
            p1, p2 = self.mainLayout.getItemPosition(i), self.mainLayout.getItemPosition(j)

            self.mainLayout.addItem(self.mainLayout.takeAt(i), *p2)
            self.mainLayout.addItem(self.mainLayout.takeAt(j), *p1)

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionEmptyMap.setText(QCoreApplication.translate("MainWindow", u"Clear Scene", None))
        self.actionMakeArray.setText(QCoreApplication.translate("MainWindow", u"Make Array", None))
        self.actionMoveToCamera.setText(QCoreApplication.translate("MainWindow", u"Move to Camera", None))
        self.actionMoveToMario.setText(QCoreApplication.translate("MainWindow", u"Move to Mario", None))
        self.actionMoveToGround.setText(QCoreApplication.translate("MainWindow", u"Move to Ground", None))
        self.actionFindDiscrepancy.setText(QCoreApplication.translate("MainWindow", u"Find Discrepancy", None))
        self.actionRepairScene.setText(QCoreApplication.translate("MainWindow", u"Repair Scene", None))
        self.actionNew.setText(QCoreApplication.translate("MainWindow", u"New", None))
        self.actionOpen.setText(QCoreApplication.translate("MainWindow", u"Open...", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.actionSaveAs.setText(QCoreApplication.translate("MainWindow", u"Save As...", None))
        self.actionClose.setText(QCoreApplication.translate("MainWindow", u"Close", None))
        self.actionObjectHierarchy.setText(QCoreApplication.translate("MainWindow", u"Object Hierarchy", None))
        self.actionObjectProperties.setText(QCoreApplication.translate("MainWindow", u"Object Properties", None))
        self.actionRailList.setText(QCoreApplication.translate("MainWindow", u"Rail List", None))
        self.actionRailEditor.setText(QCoreApplication.translate("MainWindow", u"Rail Editor", None))
        self.actionBMGEditor.setText(QCoreApplication.translate("MainWindow", u"BMG Editor", None))
        self.actionPRMEditor.setText(QCoreApplication.translate("MainWindow", u"PRM Editor", None))
        self.actionDemoEditor.setText(QCoreApplication.translate("MainWindow", u"Demo Editor", None))
        self.actionRawDataViewer.setText(QCoreApplication.translate("MainWindow", u"Data Viewer", None))
        self.actionSceneRenderer.setText(QCoreApplication.translate("MainWindow", u"Scene Renderer", None))
        self.actionCheckUpdate.setText(QCoreApplication.translate("MainWindow", u"Check Update", None))
        self.actionTutorial.setText(QCoreApplication.translate("MainWindow", u"Tutorial", None))
        self.actionReportBug.setText(QCoreApplication.translate("MainWindow", u"Report Bug", None))
        self.actionAbout.setText(QCoreApplication.translate("MainWindow", u"About", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuEdit.setTitle(QCoreApplication.translate("MainWindow", u"Edit", None))
        self.menuObject.setTitle(QCoreApplication.translate("MainWindow", u"Object", None))
        self.menuTools.setTitle(QCoreApplication.translate("MainWindow", u"Tools", None))
        self.menuWizard.setTitle(QCoreApplication.translate("MainWindow", u"Wizard", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
        self.menuWindow.setTitle(QCoreApplication.translate("MainWindow", u"Window", None))
    # retranslateUi