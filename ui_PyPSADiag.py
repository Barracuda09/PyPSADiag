# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'PyPSADiag.ui'
##
## Created by: Qt User Interface Compiler version 6.8.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QHBoxLayout, QLayout, QLineEdit, QMainWindow,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QTextEdit, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1062, 773)
        MainWindow.setSizeIncrement(QSize(1, 1))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.sendCommand = QPushButton(self.centralwidget)
        self.sendCommand.setObjectName(u"sendCommand")

        self.gridLayout.addWidget(self.sendCommand, 1, 1, 1, 1)

        self.command = QLineEdit(self.centralwidget)
        self.command.setObjectName(u"command")

        self.gridLayout.addWidget(self.command, 1, 0, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(700, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.horizontalSpacer_2, 0, 0, 1, 1)

        self.horizontalSpacer = QSpacerItem(100, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.horizontalSpacer, 0, 1, 1, 1)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.openZoneFile = QPushButton(self.centralwidget)
        self.openZoneFile.setObjectName(u"openZoneFile")

        self.verticalLayout.addWidget(self.openZoneFile)

        self.ecuComboBox = QComboBox(self.centralwidget)
        self.ecuComboBox.setObjectName(u"ecuComboBox")

        self.verticalLayout.addWidget(self.ecuComboBox)

        self.ecuKeyComboBox = QComboBox(self.centralwidget)
        self.ecuKeyComboBox.setObjectName(u"ecuKeyComboBox")

        self.verticalLayout.addWidget(self.ecuKeyComboBox)

        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_5)

        self.readZone = QPushButton(self.centralwidget)
        self.readZone.setObjectName(u"readZone")

        self.verticalLayout.addWidget(self.readZone)

        self.writeZone = QPushButton(self.centralwidget)
        self.writeZone.setObjectName(u"writeZone")

        self.verticalLayout.addWidget(self.writeZone)

        self.rebootEcu = QPushButton(self.centralwidget)
        self.rebootEcu.setObjectName(u"rebootEcu")

        self.verticalLayout.addWidget(self.rebootEcu)

        self.writeSecureTraceability = QCheckBox(self.centralwidget)
        self.writeSecureTraceability.setObjectName(u"writeSecureTraceability")

        self.verticalLayout.addWidget(self.writeSecureTraceability)

        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)


        self.gridLayout.addLayout(self.verticalLayout, 5, 1, 1, 1)

        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.output = QTextEdit(self.centralwidget)
        self.output.setObjectName(u"output")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(1)
        sizePolicy1.setHeightForWidth(self.output.sizePolicy().hasHeightForWidth())
        self.output.setSizePolicy(sizePolicy1)
        self.output.setReadOnly(True)

        self.verticalLayout_3.addWidget(self.output)


        self.gridLayout.addLayout(self.verticalLayout_3, 4, 0, 1, 1)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_4 = QVBoxLayout()
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_4)

        self.openCSVFile = QPushButton(self.centralwidget)
        self.openCSVFile.setObjectName(u"openCSVFile")

        self.verticalLayout_4.addWidget(self.openCSVFile)

        self.saveCSVFile = QPushButton(self.centralwidget)
        self.saveCSVFile.setObjectName(u"saveCSVFile")

        self.verticalLayout_4.addWidget(self.saveCSVFile)


        self.verticalLayout_2.addLayout(self.verticalLayout_4)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer_2)

        self.portNameComboBox = QComboBox(self.centralwidget)
        self.portNameComboBox.setObjectName(u"portNameComboBox")

        self.verticalLayout_2.addWidget(self.portNameComboBox)

        self.ConnectPort = QPushButton(self.centralwidget)
        self.ConnectPort.setObjectName(u"ConnectPort")

        self.verticalLayout_2.addWidget(self.ConnectPort)

        self.DisconnectPort = QPushButton(self.centralwidget)
        self.DisconnectPort.setObjectName(u"DisconnectPort")

        self.verticalLayout_2.addWidget(self.DisconnectPort)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.gridLayout.addLayout(self.verticalLayout_2, 4, 1, 1, 1)

        self.gridLayout.setColumnStretch(0, 1)

        self.horizontalLayout.addLayout(self.gridLayout)

        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        sizePolicy.setHeightForWidth(self.statusbar.sizePolicy().hasHeightForWidth())
        self.statusbar.setSizePolicy(sizePolicy)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"PyPSADiag", None))
        self.sendCommand.setText(QCoreApplication.translate("MainWindow", u"Send Command", None))
        self.openZoneFile.setText(QCoreApplication.translate("MainWindow", u"Open Zone File", None))
        self.readZone.setText(QCoreApplication.translate("MainWindow", u"Read", None))
        self.writeZone.setText(QCoreApplication.translate("MainWindow", u"Write", None))
        self.rebootEcu.setText(QCoreApplication.translate("MainWindow", u"Reboot ECU", None))
        self.writeSecureTraceability.setText(QCoreApplication.translate("MainWindow", u"Write Secure Traceability", None))
        self.openCSVFile.setText(QCoreApplication.translate("MainWindow", u"Open CSV File", None))
        self.saveCSVFile.setText(QCoreApplication.translate("MainWindow", u"Write CSV File", None))
        self.ConnectPort.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.DisconnectPort.setText(QCoreApplication.translate("MainWindow", u"Disconnect", None))
    # retranslateUi

