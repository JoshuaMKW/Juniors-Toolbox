from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, Iterable, List, Union

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, Signal, Slot
from PySide6.QtGui import QIcon, QResizeEvent, QAction
from PySide6.QtWidgets import (QMainWindow, QMenu, QMenuBar,
                               QTabWidget)
from juniors_toolbox import __name__, __version__
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.filesystem import get_program_folder, resource_path

class TabMenuAction(QAction):
    clicked = Signal(str, bool)

    def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs) -> None:
        super().__init__(*args, **kwargs)
        self.triggered.connect(self._named_trigger)
        self.toggled.connect(self._named_toggle)

    def _named_trigger(self) -> None:
        self.clicked.emit(self.text(), self.isChecked() if self.isCheckable() else True)

    def _named_toggle(self) -> None:
        self.clicked.emit(self.text(), self.isChecked())


class MainWindow(QMainWindow):
    class Theme(IntEnum):
        LIGHT = 0
        DARK = 1

    tabActionRequested = Signal(str, bool)
    themeChanged = Signal(Theme)
    resized = Signal(QResizeEvent)

    def __init__(self, *args: VariadicArgs, **kwargs: VariadicKwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName(self.__class__.__name__)
        self.setAnimated(True)
        self.setTabShape(QTabWidget.Rounded)

        self.resize(400, 500)

        self.target = None
        self.setAcceptDrops(True)
        self.setDockNestingEnabled(True)

        self.reset_ui()

    @Slot(bool)
    def signal_theme(self, darkTheme: bool):
        if darkTheme:
            self.themeChanged.emit(MainWindow.Theme.DARK)
        else:
            self.themeChanged.emit(MainWindow.Theme.LIGHT)


    def reset_ui(self):
        self.setWindowIcon(QIcon(str(resource_path("gui/icons/program.png"))))

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
        self.actionDarkTheme = QAction(self)
        self.actionDarkTheme.setCheckable(True)
        self.actionDarkTheme.setObjectName(u"actionDarkTheme")
        self.actionProjectViewer = TabMenuAction(self)
        self.actionProjectViewer.setObjectName(u"actionProjectViewer")
        self.actionObjectHierarchy = TabMenuAction(self)
        self.actionObjectHierarchy.setObjectName(u"actionObjectHierarchy")
        self.actionObjectProperties = TabMenuAction(self)
        self.actionObjectProperties.setObjectName(u"actionObjectProperties")
        self.actionRailList = TabMenuAction(self)
        self.actionRailList.setObjectName(u"actionRailList")
        self.actionRailEditor = TabMenuAction(self)
        self.actionRailEditor.setObjectName(u"actionRailEditor")
        self.actionBMGEditor = TabMenuAction(self)
        self.actionBMGEditor.setObjectName(u"actionBMGEditor")
        self.actionPRMEditor = TabMenuAction(self)
        self.actionPRMEditor.setObjectName(u"actionPRMEditor")
        self.actionDemoEditor = TabMenuAction(self)
        self.actionDemoEditor.setObjectName(u"actionDemoEditor")
        self.actionRawDataViewer = TabMenuAction(self)
        self.actionRawDataViewer.setObjectName(u"actionRawDataViewer")
        self.actionSceneRenderer = TabMenuAction(self)
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
        self.menuWindow.addAction(self.actionDarkTheme)
        self.menuWindow.addSeparator()
        self.menuWindow.addAction(self.actionProjectViewer)
        self.menuWindow.addAction(self.actionObjectHierarchy)
        self.menuWindow.addAction(self.actionObjectProperties)
        self.menuWindow.addAction(self.actionRailList)
        self.menuWindow.addAction(self.actionRailEditor)
        self.menuWindow.addAction(self.actionBMGEditor)
        self.menuWindow.addAction(self.actionPRMEditor)
        self.menuWindow.addAction(self.actionDemoEditor)
        self.menuWindow.addAction(self.actionRawDataViewer)
        self.menuWindow.addAction(self.actionSceneRenderer)

        self.actionDarkTheme.toggled.connect(self.signal_theme)
        for action in self.menuWindow.actions():
            if isinstance(action, TabMenuAction):
                action.clicked.connect(self.tabActionRequested.emit)
        
        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.resized.emit(event)

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
        self.actionDarkTheme.setText(QCoreApplication.translate("MainWindow", u"Dark Theme", None))
        self.actionProjectViewer.setText(QCoreApplication.translate("MainWindow", u"Project Viewer", None))
        self.actionObjectHierarchy.setText(QCoreApplication.translate("MainWindow", u"Scene Hierarchy", None))
        self.actionObjectProperties.setText(QCoreApplication.translate("MainWindow", u"Selected Properties", None))
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