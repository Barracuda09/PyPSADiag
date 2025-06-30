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

class PyPSADiagGUI(object):
    currentDir = os.path.dirname(os.path.abspath(__file__))
    mainWindow = None

    def setFilePathInWindowsTitle(self, path: str()):
        if path == "":
            self.mainWindow.setWindowTitle("PyPSADiag")
        else:
            self.mainWindow.setWindowTitle("PyPSADiag (" + path + ")")

    def setupGUi(self, MainWindow, scan: bool()):
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
        self.setupLanguages()

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

        self.translateUi(MainWindow);

        self.treeView = EcuZoneTreeView(None)
        if scan:
            self.scanTreeView = EcuZoneTreeView(None)

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
        self.languageHeaderLayout.setContentsMargins(0, 5, 0, 0)
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
        MainWindow.setCentralWidget(self.centralwidget)

    def setupLanguages(self):
        self.languageComboBox = QComboBox()
        self.languageComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.languageComboBox.setMinimumWidth(100)

        flags_path = os.path.join(self.currentDir, "localization", "flags")
        self.languageComboBox.addItem(QIcon(os.path.join(flags_path, "en.png")), "English", "en")
        self.languageComboBox.addItem(QIcon(os.path.join(flags_path, "ua.png")), "Українська", "ua")

    def translateUi(self, MainWindow):
        self.sendCommand.setText(QCoreApplication.translate("MainWindow", u"Send Command", None))
        self.openCSVFile.setText(QCoreApplication.translate("MainWindow", u"Open CSV File", None))
        self.saveCSVFile.setText(QCoreApplication.translate("MainWindow", u"Write CSV File", None))
        self.ConnectPort.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.SearchConnectPort.setText(QCoreApplication.translate("MainWindow", u"Search", None))
        self.DisconnectPort.setText(QCoreApplication.translate("MainWindow", u"Disconnect", None))
        self.openZoneFile.setText(QCoreApplication.translate("MainWindow", u"Open Zone File", None))
        self.readZone.setText(QCoreApplication.translate("MainWindow", u"Read", None))
        self.writeZone.setText(QCoreApplication.translate("MainWindow", u"Write", None))
        self.rebootEcu.setText(QCoreApplication.translate("MainWindow", u"Reboot ECU", None))
        self.readEcuFaults.setText(QCoreApplication.translate("MainWindow", u"Read ECU Faults", None))
        self.clearEcuFaults.setText(QCoreApplication.translate("MainWindow", u"Clear ECU Faults", None))
        self.writeSecureTraceability.setText(QCoreApplication.translate("MainWindow", u"Write Secure Traceability", None))
        self.hideNoResponseZone.setText(QCoreApplication.translate("MainWindow", u"Hide 'No Response' Zones", None))
#        self.useSketchSeedGenerator.setText(QCoreApplication.translate("MainWindow", u"Use Sketch Seed Generator", None))

        self.jsonZoneFileTitle = QCoreApplication.translate("MainWindow", "Open JSON Zone File")
        self.jsonZoneFileFilter = QCoreApplication.translate("MainWindow", "JSON Files (*.json)")
