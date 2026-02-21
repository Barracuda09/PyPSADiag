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

import os, json
from datetime import datetime
from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QTextEdit, QVBoxLayout, QWidget, QStyleFactory)

from EcuZoneTreeView  import EcuZoneTreeView
from HistoryLineEdit import HistoryLineEdit
from i18n import i18n
from version import VERSION


class PyPSADiagGUI(object):
    currentDir = os.path.dirname(os.path.abspath(__file__))
    mainWindow = None

    def setFilePathInWindowsTitle(self, path: str()):
        if path == "":
            self.mainWindow.setWindowTitle("PyPSADiag")
        else:
            self.mainWindow.setWindowTitle("PyPSADiag (" + path + ")")

    def setupGlobalColors(self):
        # Global Color variables – 2026 modern palette
        global RED
        global DARK_RED
        global DARK_GREEN
        global ORANGE
        global ERROR_COLOR
        global SUCCESS_COLOR
        global WARNING_COLOR

        ERROR_COLOR = QColor(233, 69, 96)       # coral-red
        SUCCESS_COLOR = QColor(0, 214, 143)      # teal-green
        WARNING_COLOR = QColor(255, 170, 0)      # warm amber

        RED = ERROR_COLOR
        DARK_RED = ERROR_COLOR.darker(130)
        DARK_GREEN = SUCCESS_COLOR.darker(140)
        ORANGE = WARNING_COLOR

    def setupDarkMode(self, app: QApplication):
        # Global Color variables – 2026 modern palette
        global BASE_COLOR
        global BUTTON_COLOR

        # Core palette colors
        window_bg   = QColor(0x1A, 0x1A, 0x2E)   # deep navy-charcoal
        surface     = QColor(0x16, 0x21, 0x3E)   # card / surface
        base        = QColor(0x0F, 0x34, 0x60)   # inputs / tree bg
        alt_base    = QColor(0x0D, 0x2D, 0x54)   # alternate row
        accent      = QColor(0xE9, 0x45, 0x60)   # coral-red accent
        text_main   = QColor(0xE0, 0xE0, 0xE0)   # primary text
        text_muted  = QColor(0xA0, 0xA0, 0xB0)   # secondary text
        disabled_fg = QColor(0x55, 0x55, 0x68)   # disabled text

        BASE_COLOR   = base
        BUTTON_COLOR = surface

        darkPalette = QPalette()
        darkPalette.setColor(QPalette.Window, window_bg)
        darkPalette.setColor(QPalette.WindowText, text_main)
        darkPalette.setColor(QPalette.Base, base)
        darkPalette.setColor(QPalette.AlternateBase, alt_base)
        darkPalette.setColor(QPalette.ToolTipBase, surface)
        darkPalette.setColor(QPalette.ToolTipText, text_main)
        darkPalette.setColor(QPalette.Text, text_main)
        darkPalette.setColor(QPalette.Button, surface)
        darkPalette.setColor(QPalette.ButtonText, text_main)
        darkPalette.setColor(QPalette.Link, accent)
        darkPalette.setColor(QPalette.Highlight, accent)
        darkPalette.setColor(QPalette.HighlightedText, Qt.white)
        darkPalette.setColor(QPalette.Light, surface.lighter(150))
        darkPalette.setColor(QPalette.Midlight, surface.lighter(120))
        darkPalette.setColor(QPalette.Mid, surface.darker(130))
        darkPalette.setColor(QPalette.Dark, window_bg.darker(150))
        darkPalette.setColor(QPalette.Active, QPalette.Highlight, accent)
        darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_fg)
        darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_fg)
        darkPalette.setColor(QPalette.Disabled, QPalette.Text, disabled_fg)
        darkPalette.setColor(QPalette.Disabled, QPalette.Light, window_bg)
        darkPalette.setColor(QPalette.Disabled, QPalette.Button, surface.darker(120))
        app.setPalette(darkPalette)

        # Load external QSS stylesheet
        qssPath = os.path.join(self.currentDir, "style.qss")
        if os.path.exists(qssPath):
            with open(qssPath, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())

    def setupGUI(self, app: QApplication, MainWindow, scan: bool(), lang_code: str):
        self.mainWindow = MainWindow
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1300, 780)
        MainWindow.setSizeIncrement(QSize(1, 1))
        self.setFilePathInWindowsTitle("")
        self.centralwidget = QWidget(MainWindow)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)

        app.setStyle(QStyleFactory.create('Fusion'))

        self.setupGlobalColors()

        self.setupDarkMode(app)

        self.command = HistoryLineEdit()
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        # Setup languages
        self.setupLanguages(lang_code)

        self.syncZoneFiles = QPushButton()

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
        self.flashEcu = QPushButton()
        self.rebootEcu = QPushButton()
        self.readEcuFaults = QPushButton()
        self.clearEcuFaults = QPushButton()
        self.writeSecureTraceability = QCheckBox()
        self.virginWriteZone = QCheckBox()
        self.hideNoResponseZone = QCheckBox()
#        self.useSketchSeedGenerator = QCheckBox()
        self.ecuTxRxLabel = QLabel()
        self.statusbar = QStatusBar()
        self.statusbar.addPermanentWidget(self.ecuTxRxLabel)

        self.treeView = EcuZoneTreeView(None)
        if scan:
            self.scanTreeView = EcuZoneTreeView(None)

        self.translateGUI(self)

        ###################################################
        # Setup Top Left Layout
        self.topLeftLayout = QVBoxLayout()
        self.topLeftLayout.setSpacing(6)
        self.topLeftLayout.addWidget(self.command)
        self.topLeftLayout.addWidget(self.output)
        ###################################################

        ###################################################
        # Setup Top Button Header Layout
        self.topButtonHeaderLayout = QHBoxLayout()

        self.topButtonHeaderLayout.addStretch()
        self.topButtonHeaderLayout.setContentsMargins(16, 12, 16, 0)
        self.topButtonHeaderLayout.addWidget(self.syncZoneFiles)
        self.topButtonHeaderLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        self.topButtonHeaderLayout.addWidget(self.languageComboBox)

        ###################################################
        # Setup Top Right Layout
        self.topRightLayout = QVBoxLayout()
        self.topRightLayout.setSpacing(6)
        self.topRightLayout.addWidget(self.sendCommand)
        self.topRightLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.topRightLayout.addWidget(self.openCSVFile)
        self.topRightLayout.addWidget(self.saveCSVFile)
        self.topRightLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        # -- Connection section --
        self.connectionLabel = QLabel(i18n().tr("Connection"))
        self.connectionLabel.setProperty("class", "section-header")
        self.topRightLayout.addWidget(self.connectionLabel)
        self.topRightLayout.addWidget(self.portNameComboBox)
        self.topRightLayout.addWidget(self.SearchConnectPort)
        self.topRightLayout.addWidget(self.ConnectPort)
        self.topRightLayout.addWidget(self.DisconnectPort)
        self.topRightLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        ###################################################

        ###################################################
        # Setup Bottom Left Layout (TreeView)
        self.bottomLeftLayout = QVBoxLayout()
        self.bottomLeftLayout.addWidget(self.treeView)
        ###################################################

        ###################################################
        # Setup Bottom Right Layout (Buttons)
        self.bottomRightLayout = QVBoxLayout()
        self.bottomRightLayout.setSpacing(6)
        self.bottomRightLayout.addWidget(self.openZoneFile)
        self.bottomRightLayout.addWidget(self.ecuComboBox)
        self.bottomRightLayout.addWidget(self.ecuKeyComboBox)
        # -- ECU Operations section --
        self.ecuOpsLabel = QLabel(i18n().tr("ECU Operations"))
        self.ecuOpsLabel.setProperty("class", "section-header")
        self.bottomRightLayout.addWidget(self.ecuOpsLabel)
        self.bottomRightLayout.addWidget(self.readZone)
        self.bottomRightLayout.addWidget(self.writeZone)
        self.bottomRightLayout.addWidget(self.flashEcu)
        self.bottomRightLayout.addWidget(self.readEcuFaults)
        self.bottomRightLayout.addWidget(self.clearEcuFaults)
        self.bottomRightLayout.addWidget(self.rebootEcu)
        # -- Options section --
        self.optionsLabel = QLabel(i18n().tr("Options"))
        self.optionsLabel.setProperty("class", "section-header")
        self.bottomRightLayout.addWidget(self.optionsLabel)
        self.bottomRightLayout.addWidget(self.virginWriteZone)
        self.bottomRightLayout.addWidget(self.writeSecureTraceability)
        self.bottomRightLayout.addWidget(self.hideNoResponseZone)
#        self.bottomRightLayout.addWidget(self.useSketchSeedGenerator)
        self.bottomRightLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
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
        self.frame.setContentsMargins(16, 8, 16, 16)
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)

        self.frameLayout = QHBoxLayout()
        if scan:
            self.frameLayout.addWidget(self.splitterLeftRight)
        else:
            self.frameLayout.addWidget(self.splitterTopBottom)
        self.frame.setLayout(self.frameLayout)

        # Setup Top Button Widget
        self.topButtonWidget = QWidget()
        self.topButtonWidget.setLayout(self.topButtonHeaderLayout)

        # Setup Main Frame
        self.mainLayout = QVBoxLayout()
        self.mainLayout.setSpacing(0)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        self.mainLayout.addWidget(self.topButtonWidget)
        self.mainLayout.addWidget(self.frame)
        self.centralwidget.setLayout(self.mainLayout)

        self.mainLayout.addWidget(self.statusbar)
        self.statusbar.showMessage(f"PyPSADiag {VERSION} - Copyright \u00A9 {datetime.now().year} by Barracuda09")

        MainWindow.setCentralWidget(self.centralwidget)


    def setupLanguages(self, lang_code: str):
        self.languageComboBox = QComboBox()
        self.languageComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.languageComboBox.setMinimumWidth(100)

        languagesPath = os.path.join(self.currentDir, "i18n", "Languages.json")
        flagsPath = os.path.join(self.currentDir, "i18n", "flags")

        # Read the languages from json file
        file = open(languagesPath, 'r', encoding='utf-8')
        jsonFile = file.read()
        languagesList = json.loads(jsonFile.encode("utf-8"))
        languages = []
        for language in languagesList:
            languages.append((language ,languagesList[language]["name"]))

        for code, name in languages:
            iconPath = os.path.join(flagsPath, f"{code}.png")
            self.languageComboBox.addItem(QIcon(iconPath), name, code)

        index = self.languageComboBox.findData(lang_code)
        if index != -1:
            self.languageComboBox.setCurrentIndex(index)

    def translateGUI(self, MainWindow):
        self.syncZoneFiles.setText(i18n().tr("Sync Zone Files"))
        self.sendCommand.setText(i18n().tr("Send Command"))
        self.openCSVFile.setText(i18n().tr("Open CSV File"))
        self.saveCSVFile.setText(i18n().tr("Write CSV File"))
        self.ConnectPort.setText(i18n().tr("Connect"))
        self.SearchConnectPort.setText(i18n().tr("Search"))
        self.DisconnectPort.setText(i18n().tr("Disconnect"))
        self.openZoneFile.setText(i18n().tr("Open Zone File"))
        self.readZone.setText(i18n().tr("Read"))
        self.writeZone.setText(i18n().tr("Write"))
        self.flashEcu.setText(i18n().tr("Flash CAL/ULP"))
        self.rebootEcu.setText(i18n().tr("Reboot ECU"))
        self.readEcuFaults.setText(i18n().tr("Read ECU Faults") + " " + i18n().tr("(DTC)"))
        self.clearEcuFaults.setText(i18n().tr("Clear ECU Faults") + " " + i18n().tr(" (DTC)"))
        self.writeSecureTraceability.setText(i18n().tr("Write Secure Traceability"))
        self.virginWriteZone.setText(i18n().tr("Virgin Write"))
        self.hideNoResponseZone.setText(i18n().tr("Hide 'No Response' Zones"))
#        self.useSketchSeedGenerator.setText(i18n().tr("Use Sketch Seed Generator"))
        self.setEcuTxRxText("-", "-", "-")

    def setEcuTxRxText(self, txId: str, rxId: str, protocol: str):
        self.ecuTxRxLabel.setText("TX: " + str(txId) + " | RX: " + str(rxId) + " | protocol: " + str(protocol))
