"""
   main.py

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

import sys
import random
import json
import csv
import time
from PySide6.QtCore import Qt, Slot, QIODevice
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

import serial.tools.list_ports

from ui_PyPSADiag import Ui_MainWindow
import EcuZoneReader
import FileLoader
from EcuZoneTable import EcuZoneTableView
from EcuZoneTreeView  import EcuZoneTreeView

"""
  - pyside6-designer PyPSADiag.ui
  - pyside6-uic PyPSADiag.ui -o ui_PyPSADiag.py
  - python main.py
"""
class MainWindow(QMainWindow):
    portNameList = list()
    ui = Ui_MainWindow()
    ecuObjectList = dict()

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui.setupUi(self)

        # Setup TreeView
        self.treeView = EcuZoneTreeView(self.ui.centralwidget)
        self.ui.gridLayout.addWidget(self.treeView, 5, 0, 1, 1)

        # Connect button signals to slots
        self.ui.sendCommand.clicked.connect(self.sendCommand)
        self.ui.openCSVFile.clicked.connect(self.openCSVFile)
        self.ui.saveCSVFile.clicked.connect(self.saveCSVFile)
        self.ui.openZoneFile.clicked.connect(self.openZoneFile)
        self.ui.readZone.clicked.connect(self.readZone)
        self.ui.writeZone.clicked.connect(self.writeZone)
        self.ui.rebootEcu.clicked.connect(self.rebootEcu)
        self.ui.ConnectPort.clicked.connect(self.connectPort)
        self.ui.DisconnectPort.clicked.connect(self.disconnectPort)

        # Get available Serial ports and put it in Combobox
        self.ui.portNameComboBox.clear()
        comPorts = serial.tools.list_ports.comports()
        nameList = list(port.device for port in comPorts)
        for name in nameList:
            self.ui.portNameComboBox.addItem(name)

        # Setup serial controller
        self.serialController = serial.Serial()

        # Set initial button states
        self.ui.DisconnectPort.setEnabled(False)
        self.ui.readZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.rebootEcu.setEnabled(False)
        self.ui.writeSecureTraceability.setCheckState(Qt.Checked)

        #
        self.ecuZoneReaderThread = EcuZoneReader.EcuZoneReaderThread(self.serialController)
        self.ecuZoneReaderThread.receivedPacketSignal.connect(self.serialPacketReceiverCallback)
        self.ecuZoneReaderThread.updateZoneDataSignal.connect(self.updateZoneDataback)

        # Open CSV reader, load file with method "enable(path)"
        self.fileLoaderThread = FileLoader.FileLoaderThread()
        self.fileLoaderThread.newRowSignal.connect(self.csvReadCallback)

    # Update ECU Combobox and Zone Tree view with "new" Zone file
    def updateEcuZones(self, ecuObjectList: dict):
        self.ui.ecuComboBox.clear()
        self.ui.ecuComboBox.addItem(ecuObjectList["name"])
        zoneObjectList = ecuObjectList["zones"]
        for zoneObject in zoneObjectList:
            self.ui.ecuComboBox.addItem(str(zoneObject))

        self.treeView.updateView(ecuObjectList)

    @Slot()
    def connectPort(self):
        try:
            self.serialController.port = self.ui.portNameComboBox.currentText()
            self.serialController.baudrate = 115200
            self.serialController.open()
            self.serialController.setDTR(True)
            # Set button states
            self.ui.ConnectPort.setEnabled(False)
            self.ui.DisconnectPort.setEnabled(True)
            self.ui.readZone.setEnabled(True)
            self.ui.writeZone.setEnabled(True)
            self.ui.writeZone.setEnabled(True)
        except serial.SerialException as e:
            print('Error opening port: ' + str(e))

    @Slot()
    def disconnectPort(self):
        self.stream.close()
        self.serialController.close()
        self.ui.ConnectPort.setEnabled(True)
        self.ui.DisconnectPort.setEnabled(False)
        self.ui.readZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)

    @Slot()
    def sendCommand(self):
        if self.serialController.isOpen():
            cmd = self.ui.command.text() + "\n"
            self.ui.output.append(cmd)
            self.receiveData = self.ecuZoneReaderThread.sendReceive(cmd)
            self.ui.output.append(self.receiveData)
        else:
            self.ui.output.append("Port not open!")

    @Slot()
    def openCSVFile(self):
        fileName = QFileDialog.getOpenFileName(self, "Open CSV Zone File", "./csv", "CSV Files (*.csv)")
        if fileName[0] == "":
            return
        self.fileLoaderThread.enable(fileName[0], 0);

    @Slot()
    def saveCSVFile(self):
        fileName = QFileDialog.getSaveFileName(self, "Save CSV Zone File", "./csv", "CSV Files (*.csv)")
        #self.fileLoaderThread.enable(fileName[0], 0);
        self.treeView.getValuesAsCSV()

    @Slot()
    def openZoneFile(self):
        fileName = QFileDialog.getOpenFileName(self, "Open JSON Zone File", "./json", "JSON Files (*.json)")
        if fileName[0] == "":
            return
        file = open(fileName[0], 'r', encoding='utf-8')
        jsonFile = file.read()
        self.ecuObjectList = json.loads(jsonFile.encode("utf-8"))
        self.updateEcuZones(self.ecuObjectList)

    @Slot()
    def readZone(self):
        if self.serialController.isOpen():
            fileName = QFileDialog.getSaveFileName(self, "Save CSV Zone File", "./csv", "CSV Files (*.csv)")
            if fileName[0] == "":
                return

            # Open CSV for writing
            self.stream = open(fileName[0], 'w', newline='')
            self.csvWriter = csv.writer(self.stream)

            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]
            startDiagmode = "1003"
            stopDiagmode = "1001"
            # Read Requested Zone or ALL Zones from ECU
            if self.ui.ecuComboBox.currentIndex() == 0:
                self.ecuZoneReaderThread.setZonesToRead(ecu, startDiagmode, self.ecuObjectList["zones"], stopDiagmode)
            else:
                zone = dict()
                zone[self.ui.ecuComboBox.currentText()] = self.ecuObjectList["zones"][self.ui.ecuComboBox.currentText()];
                self.ecuZoneReaderThread.setZonesToRead(ecu, startDiagmode, zone, stopDiagmode)

    @Slot()
    def writeZone(self):
        if self.serialController.isOpen():
            # Setup text of changed zones and put it into MessageBox
            text = ""
            changeCount = 0
            valueList = self.treeView.getZoneListOfHexValue()
            for tabList in valueList:
                for zone in tabList:
                    text += str(zone) + "\r\n"
                    changeCount += 1
            if changeCount == 0:
                self.ui.output.append("Nothing changed")
                return
            if QMessageBox.Cancel == QMessageBox.question(self, "Write zone(s) to ECU", text, QMessageBox.Save, QMessageBox.Cancel):
                return
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]
            if self.ecuObjectList["protocol"] == "uds":
                startDiagmode = "1003"
                stopDiagmode = "1001"
            else:
                self.ui.output.append("Protocal not supported yet!")
                return
            # Get the corresponding ECU Key
            keyType = self.ecuObjectList["key_type"]
            if keyType == "single":
                key = ":" + self.ecuObjectList["keys"] + ":03:03"
            else:
                key = ":" + self.ecuObjectList["keys"]["BSI_2010_EVO"] + ":03:03"
                self.ui.output.append("Mutli KEY should be implemented Beter!!")

            secureTraceability = "2E2901FD00000010101"

            receiveData = self.ecuZoneReaderThread.sendReceive(ecu)
            print(receiveData)

            receiveData = self.ecuZoneReaderThread.sendReceive(startDiagmode)
            print(receiveData)

            receiveData = self.ecuZoneReaderThread.sendReceive(key)
            print(receiveData)

            for tabList in valueList:
                for zone in tabList:
                    writeCmd = "2E" + zone[0] + zone[1]
                    readCmd = "22" + zone[0]

                    receiveData = self.ecuZoneReaderThread.sendReceive(readCmd)
                    print(receiveData)

                    receiveData = self.ecuZoneReaderThread.sendReceive(writeCmd)
                    print(receiveData)

                    receiveData = self.ecuZoneReaderThread.sendReceive(readCmd)
                    print(receiveData)

            if self.ui.writeSecureTraceability.isChecked():
                self.receiveData = self.ecuZoneReaderThread.sendReceive(secureTraceability)
                print(receiveData)
            else:
                self.ui.output.append("NO Secure Traceability is Written!!")

            receiveData = self.ecuZoneReaderThread.sendReceive(stopDiagmode)
            print(receiveData)

    @Slot()
    def rebootEcu(self):
        if self.serialController.isOpen():
            print("Reboot ECU")
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"] + "\n"
            rebootECU = "1103\n"

            receiveData = self.ecuZoneReaderThread.sendReceive(ecu)
            print(receiveData)

            receiveData = self.ecuZoneReaderThread.sendReceive(rebootECU)
            print(receiveData)

    @Slot()
    def csvReadCallback(self, value: list):
        self.treeView.changeZoneOption(value[0], value[1], value[2]);

    @Slot()
    def updateZoneDataback(self, zoneData: str, value: str, valueType: str):
        self.treeView.changeZoneOption(zoneData, value, valueType)

    @Slot()
    def serialPacketReceiverCallback(self, packet: list, time: float):
        self.ui.output.append(str(packet))
        self.csvWriter.writerow(packet)
        self.stream.flush()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
