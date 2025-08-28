"""
   PyPSADiagGUI.py

   Copyright (C) 2024 - 2025 Marc Postema (mpostema09 -at- gmail.com)

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
   Or, point your browser to http://www.gnu.org/copyleft/gpl.html
"""

import os
from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QTextEdit, QVBoxLayout, QWidget)

from EcuZoneTreeView  import EcuZoneTreeView
from HistoryLineEdit import HistoryLineEdit
from i18n import i18n


class PyPSADiagGUI(object):
    currentDir = os.path.dirname(os.path.abspath(__file__))
    mainWindow = None

    def setFilePathInWindowsTitle(self, path: str()):
        if path == "":
            self.mainWindow.setWindowTitle("PyPSADiag")
        else:
            self.mainWindow.setWindowTitle("PyPSADiag (" + path + ")")

    def setupDarkMode(self):
        GRAY = QColor(130, 130, 130)
        DARK_GRAY = QColor(130, 130, 130)
        black = QColor(30, 30, 30)
        blue = QColor(42, 130, 218)
        backGround = DARK_GRAY.lighter(200)
        light = backGround.lighter(150)
        mid = backGround.darker(130)
        midLight = mid.lighter(110)
        dark = backGround.darker(150)
        base = black.lighter(200)
        altbase = DARK_GRAY.darker(125)

        darkPalette = QPalette()
        darkPalette.setColor(QPalette.Window, DARK_GRAY)
        darkPalette.setColor(QPalette.WindowText, Qt.white)
        darkPalette.setColor(QPalette.Base, base)
        darkPalette.setColor(QPalette.AlternateBase, altbase)
        darkPalette.setColor(QPalette.ToolTipBase, blue)
        darkPalette.setColor(QPalette.ToolTipText, Qt.white)
        darkPalette.setColor(QPalette.Text, Qt.white)
        darkPalette.setColor(QPalette.Button, DARK_GRAY)
        darkPalette.setColor(QPalette.ButtonText, Qt.white)
        darkPalette.setColor(QPalette.Link, blue)
        darkPalette.setColor(QPalette.Highlight, GRAY.darker(150))
        darkPalette.setColor(QPalette.HighlightedText, Qt.white)
        darkPalette.setColor(QPalette.Light, light)
        darkPalette.setColor(QPalette.Midlight, midLight)
        darkPalette.setColor(QPalette.Mid, mid)
        darkPalette.setColor(QPalette.Dark, dark)
        darkPalette.setColor(QPalette.Active, QPalette.Highlight, blue)
        darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, GRAY.lighter(125))
        darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, GRAY.lighter(125))
        darkPalette.setColor(QPalette.Disabled, QPalette.Text, GRAY.lighter(125))
        darkPalette.setColor(QPalette.Disabled, QPalette.Light, DARK_GRAY)
        QApplication.setPalette(darkPalette);

    def setupGUI(self, MainWindow, scan: bool(), lang_code: str):
        self.setupDarkMode()
        self.mainWindow = MainWindow
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1100, 700)
        MainWindow.setSizeIncrement(QSize(1, 1))
        self.setFilePathInWindowsTitle("")
        self.centralwidget = QWidget(MainWindow)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)

        self.command = HistoryLineEdit()
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        # Setup languages
        self.setupLanguages(lang_code)

        self.sendCommand = QPushButton()
        self.openCSVFile = QPushButton()
        self.saveCSVFile = QPushButton()

        self.portNameComboBox = QComboBox()
        self.ConnectPort = QPushButton()
        self.SearchConnectPort = QPushButton()

        self.DisconnectPort = QPushButton()
        self.openZoneFile = QPushButton()
        self.ecuComboBox = QComboBox()
        self.ecuKeyComboBox = QComboBox()
        self.readZone = QPushButton()
        self.writeZone = QPushButton()
        self.rebootEcu = QPushButton()
        self.readEcuFaults = QPushButton()
        self.clearEcuFaults = QPushButton()
        self.writeSecureTraceability = QCheckBox()
        self.virginWriteZone = QCheckBox()
        self.hideNoResponseZone = QCheckBox()
#        self.useSketchSeedGenerator = QCheckBox()

        self.treeView = EcuZoneTreeView(None)
        if scan:
            self.scanTreeView = EcuZoneTreeView(None)

        self.translateGUI(self)

        ###################################################
        # Setup Top Left Layout
        self.topLeftLayout = QVBoxLayout()
        self.topLeftLayout.addWidget(self.command)
        self.topLeftLayout.addWidget(self.output)
        ###################################################

        ###################################################
        # Setup Language Header Layout
        self.languageHeaderLayout = QHBoxLayout()

        self.languageHeaderLayout.addStretch()
        self.languageHeaderLayout.setContentsMargins(0, 10, 10, 0)
        self.languageHeaderLayout.addWidget(self.languageComboBox)

        ###################################################
        # Setup Top Right Layout
        self.topRightLayout = QVBoxLayout()
        self.topRightLayout.addWidget(self.sendCommand)
        self.topRightLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.topRightLayout.addWidget(self.openCSVFile)
        self.topRightLayout.addWidget(self.saveCSVFile)
        self.topRightLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.topRightLayout.addWidget(self.portNameComboBox)
        self.topRightLayout.addWidget(self.SearchConnectPort)
        self.topRightLayout.addWidget(self.ConnectPort)
        self.topRightLayout.addWidget(self.DisconnectPort)
        self.topRightLayout.addWidget(self.languageComboBox)
        self.topRightLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        ###################################################

        ###################################################
        # Setup Bottom Left Layout (TreeView)
        self.bottomLeftLayout = QVBoxLayout()
        self.bottomLeftLayout.addWidget(self.treeView)
        ###################################################

        ###################################################
        # Setup Bottom Right Layout (Buttons)
        self.bottomRightLayout = QVBoxLayout()
        self.bottomRightLayout.addWidget(self.openZoneFile)
        self.bottomRightLayout.addWidget(self.ecuComboBox)
        self.bottomRightLayout.addWidget(self.ecuKeyComboBox)
        self.bottomRightLayout.addWidget(self.readZone)
        self.bottomRightLayout.addWidget(self.writeZone)
        self.bottomRightLayout.addWidget(self.readEcuFaults)
        self.bottomRightLayout.addWidget(self.clearEcuFaults)
        self.bottomRightLayout.addWidget(self.rebootEcu)
        self.bottomRightLayout.addWidget(self.virginWriteZone)
        self.bottomRightLayout.addWidget(self.writeSecureTraceability)
        self.bottomRightLayout.addWidget(self.hideNoResponseZone)
#        self.bottomRightLayout.addWidget(self.useSketchSeedGenerator)
        self.bottomRightLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        ###################################################

        ###################################################
        # Add Top Left, Right Layout -> Main Top Layout
        self.topLayout = QHBoxLayout()
        self.topLayout.addLayout(self.topLeftLayout)
        self.topLayout.addLayout(self.topRightLayout)
        ###################################################

        ###################################################
        # Add Bottom Left, Right Layout -> Main Bottom Layout
        self.bottomLayout = QHBoxLayout()
        self.bottomLayout.addLayout(self.bottomLeftLayout)
        self.bottomLayout.addLayout(self.bottomRightLayout)
        ###################################################

        ###################################################
        # Setup splitter Vertical (Top-Bottom)
        self.splitterTopBottom = QSplitter()
        self.splitterTopBottom.setStyleSheet("QSplitter::handle {background: gray;}")
        self.splitterTopBottom.setOrientation(Qt.Orientation.Vertical)

        self.topWidget = QWidget()
        self.topWidget.setLayout(self.topLayout)
        self.splitterTopBottom.addWidget(self.topWidget)

        self.bottomWidget = QWidget()
        self.bottomWidget.setLayout(self.bottomLayout)
        self.splitterTopBottom.addWidget(self.bottomWidget)
        ###################################################

        if scan:
            ###################################################
            # Setup Main Left Layout
            self.mainLeftLayout = QHBoxLayout()
            self.mainLeftLayout.addWidget(self.scanTreeView)
            ###################################################

            ###################################################
            # Setup Main Right Layout
            self.mainRightLayout = QHBoxLayout()
            self.mainRightLayout.addWidget(self.splitterTopBottom)
            ###################################################

            ###################################################
            # Setup splitter Horizontal (Left-Right)
            self.splitterLeftRight = QSplitter()
            self.splitterLeftRight.setOrientation(Qt.Orientation.Horizontal)

            self.mainLeftWidget = QWidget()
            self.mainLeftWidget.setLayout(self.mainLeftLayout)
            self.splitterLeftRight.addWidget(self.mainLeftWidget)

            self.mainRightWidget = QWidget()
            self.mainRightWidget.setLayout(self.mainRightLayout)
            self.splitterLeftRight.addWidget(self.mainRightWidget)
            ###################################################

        self.frame = QFrame(self.centralwidget)
        self.frame.setContentsMargins(10, 0, 10, 10)
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)

        self.frameLayout = QHBoxLayout()
        if scan:
            self.frameLayout.addWidget(self.splitterLeftRight)
        else:
            self.frameLayout.addWidget(self.splitterTopBottom)
        self.frame.setLayout(self.frameLayout)

        # Setup language Widget
        self.languageWidget = QWidget()
        self.languageWidget.setLayout(self.languageHeaderLayout)

        # Setup Main Frame
        self.mainLayout = QVBoxLayout()
        self.mainLayout.setSpacing(0)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.mainLayout.addWidget(self.languageWidget)
        self.mainLayout.addWidget(self.frame)
        self.centralwidget.setLayout(self.mainLayout)

        self.statusbar = QStatusBar()
        self.mainLayout.addWidget(self.statusbar)
        self.statusbar.showMessage("PyPSADiag  -  Copyright \u00A9 2025 by Barracuda09")

        MainWindow.setCentralWidget(self.centralwidget)


    def setupLanguages(self, lang_code: str):
        self.languageComboBox = QComboBox()
        self.languageComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.languageComboBox.setMinimumWidth(100)

        flags_path = os.path.join(self.currentDir, "i18n", "flags")

        languages = [
            ("en", "English"),
            ("it", "Italiano"),
            ("de", "Deutsch"),
            ("nl", "Nederlands"),
            ("pl", "Polski"),
            ("uk", "Українська"),
        ]

        for code, name in languages:
            icon_path = os.path.join(flags_path, f"{code}.png")
            self.languageComboBox.addItem(QIcon(icon_path), name, code)

        index = self.languageComboBox.findData(lang_code)
        if index != -1:
            self.languageComboBox.setCurrentIndex(index)

    def translateGUI(self, MainWindow):
        self.sendCommand.setText(i18n().tr("Send Command"))
        self.openCSVFile.setText(i18n().tr("Open CSV File"))
        self.saveCSVFile.setText(i18n().tr("Write CSV File"))
        self.ConnectPort.setText(i18n().tr("Connect"))
        self.SearchConnectPort.setText(i18n().tr("Search"))
        self.DisconnectPort.setText(i18n().tr("Disconnect"))
        self.openZoneFile.setText(i18n().tr("Open Zone File"))
        self.readZone.setText(i18n().tr("Read"))
        self.writeZone.setText(i18n().tr("Write"))
        self.rebootEcu.setText(i18n().tr("Reboot ECU"))
        self.readEcuFaults.setText(i18n().tr("Read ECU Faults"))
        self.clearEcuFaults.setText(i18n().tr("Clear ECU Faults"))
        self.writeSecureTraceability.setText(i18n().tr("Write Secure Traceability"))
        self.virginWriteZone.setText(i18n().tr("Virgin Write"))
        self.hideNoResponseZone.setText(i18n().tr("Hide 'No Response' Zones"))
#        self.useSketchSeedGenerator.setText(i18n().tr("Use Sketch Seed Generator"))
