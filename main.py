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
from datetime import datetime
from PySide6.QtCore import Qt, Slot, QIODevice
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

from PyPSADiagGUI import PyPSADiagGUI
import FileLoader
from UDSCommunication import UDSCommunication
from SeedKeyAlgorithm import SeedKeyAlgorithm
from SerialPort import SerialPort
from FileConverter import FileConverter
from EcuZoneTable import EcuZoneTableView
from EcuZoneTreeView  import EcuZoneTreeView

"""
  - Change GUI in: PyPSADiagGUI.py
  - Run with: python main.py
"""
class MainWindow(QMainWindow):
    ui = PyPSADiagGUI()
    ecuObjectList = dict()
    simulation = False
    stream = None
    csvWriter = None

    def __init__(self):
        super(MainWindow, self).__init__()
        if len(sys.argv) >= 2:
            for arg in sys.argv:
                if arg == "--simu":
                    self.simulation = True
                if arg == "--checkcalc":
                    calc = SeedKeyAlgorithm()
                    calc.testCalculations()
                    exit()
                if arg == "--help":
                    print("Use --simu   For simulation")
                    exit()

        self.ui.setupGUi(self)

        #converter = FileConverter()
        #converter.convertNAC("./json/test_nac_original.json", "./json/test_nac_conv.json")
        #converter.convertCIROCCO("./json/test_CIROCCO_original.json", "./json/test_CIROCCO_conv.json")

        # Connect button signals to slots
        self.ui.sendCommand.clicked.connect(self.sendCommand)
        self.ui.openCSVFile.clicked.connect(self.openCSVFile)
        self.ui.saveCSVFile.clicked.connect(self.saveCSVFile)
        self.ui.openZoneFile.clicked.connect(self.openZoneFile)
        self.ui.readZone.clicked.connect(self.readZone)
        self.ui.writeZone.clicked.connect(self.writeZone)
        self.ui.rebootEcu.clicked.connect(self.rebootEcu)
        self.ui.readEcuFaults.clicked.connect(self.readEcuFaults)
        self.ui.ConnectPort.clicked.connect(self.connectPort)
        self.ui.DisconnectPort.clicked.connect(self.disconnectPort)

        # Setup serial controller
        self.serialController = SerialPort()
        self.serialController.fillPortNameCombobox(self.ui.portNameComboBox)

        # Set initial button states
        self.ui.DisconnectPort.setEnabled(False)
        self.ui.readZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.rebootEcu.setEnabled(False)
        self.ui.readEcuFaults.setEnabled(False)
        self.ui.writeSecureTraceability.setCheckState(Qt.Checked)
#        self.ui.useSketchSeedGenerator.setCheckState(Qt.Unchecked)

        #
        self.udsCommunication = UDSCommunication(self.serialController, self.simulation)
        self.udsCommunication.receivedPacketSignal.connect(self.serialPacketReceiverCallback)
        self.udsCommunication.outputToTextEditSignal.connect(self.outputToTextEditCallback)
        self.udsCommunication.updateZoneDataSignal.connect(self.updateZoneDataback)

        # Open CSV reader, load file with method "enable(path)"
        self.fileLoaderThread = FileLoader.FileLoaderThread()
        self.fileLoaderThread.newRowSignal.connect(self.csvReadCallback)

    # Update ECU Combobox and Zone Tree view with "new" Zone file
    def updateEcuZonesAndKeys(self, ecuObjectList: dict):
        # Update ECU Zone ComboBox
        self.ui.ecuComboBox.clear()
        name = ecuObjectList["name"]
        self.ui.ecuComboBox.addItem(name)
        if "zones" in ecuObjectList:
            zoneObjectList = ecuObjectList["zones"]
            # Update ECU Key ComboBox
            self.ui.ecuKeyComboBox.clear()
            keyType = ecuObjectList["key_type"]
            if keyType == "single":
                key = str(ecuObjectList["keys"])
                item = name + " - " + key
                self.ui.ecuKeyComboBox.addItem(item, key)
            elif keyType == "multi":
                for keyItem in ecuObjectList["keys"]:
                    key = str(ecuObjectList["keys"][keyItem])
                    item = str(keyItem) + " - " + key
                    self.ui.ecuKeyComboBox.addItem(item, key)
        elif "ecu" in ecuObjectList:
            zoneObjectList = ecuObjectList["ecu"]
        else:
            self.writeToOutputView("Not correct JSON file")
            return;

        for zoneObject in zoneObjectList:
            self.ui.ecuComboBox.addItem(str(zoneObject))

        self.ui.treeView.updateView(ecuObjectList)

    def writeToOutputView(self, text: str):
        self.ui.output.append(str(datetime.now()) + " --|  " + text)
        self.ui.output.viewport().repaint()

    @Slot()
    def connectPort(self):
        self.serialController.open(self.ui.portNameComboBox.currentText(), 115200)

        # Set button states
        self.ui.ConnectPort.setEnabled(False)
        self.ui.DisconnectPort.setEnabled(True)

    @Slot()
    def disconnectPort(self):
        if self.stream != None:
            self.stream.close()
        self.serialController.close()
        self.ui.ConnectPort.setEnabled(True)
        self.ui.DisconnectPort.setEnabled(False)
        self.ui.readZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.readEcuFaults.setEnabled(False)
        self.ui.rebootEcu.setEnabled(False)
#        self.ui.useSketchSeedGenerator.setCheckState(Qt.Unchecked)
#        self.ui.useSketchSeedGenerator.setEnabled(True)

    @Slot()
    def sendCommand(self):
        if self.serialController.isOpen():
            cmd = self.ui.command.text()
            self.writeToOutputView(cmd)
            self.receiveData = self.serialController.sendReceive(cmd)
            self.writeToOutputView(self.receiveData)
        else:
            self.writeToOutputView("Port not open!")

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
        self.ui.treeView.getValuesAsCSV()

    @Slot()
    def openZoneFile(self):
        fileName = QFileDialog.getOpenFileName(self, "Open JSON Zone File", "./json", "JSON Files (*.json)")
        if fileName[0] == "":
            return
        file = open(fileName[0], 'r', encoding='utf-8')
        jsonFile = file.read()
        self.ecuObjectList = json.loads(jsonFile.encode("utf-8"))
        self.updateEcuZonesAndKeys(self.ecuObjectList)
        self.ui.readZone.setEnabled(True)
        self.ui.writeZone.setEnabled(True)
        self.ui.writeZone.setEnabled(True)
        self.ui.readEcuFaults.setEnabled(True)
        self.ui.rebootEcu.setEnabled(True)

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

            # Setup LIN_ID if present
            lin = ""
            if "lin_id" in self.ecuObjectList:
                lin = "L" + self.ecuObjectList["lin_id"]

            if self.ecuObjectList["protocol"] == "uds":
                # Read Requested Zone or ALL Zones from ECU
                if self.ui.ecuComboBox.currentIndex() == 0:
                    self.udsCommunication.setZonesToRead(ecu, lin, self.ecuObjectList["zones"])
                else:
                    zone = dict()
                    zone[self.ui.ecuComboBox.currentText()] = self.ecuObjectList["zones"][self.ui.ecuComboBox.currentText()];
                    self.udsCommunication.setZonesToRead(ecu, lin, zone)
            else:
                self.writeToOutputView("Protocol not supported yet!")
                return
        else:
            self.writeToOutputView("Port not open!")


    @Slot()
    def writeZone(self):
        if self.serialController.isOpen():
            # Setup text of changed zones and put it into MessageBox
            text = ""
            changeCount = 0
            valueList = self.ui.treeView.getZoneListOfHexValue()
            for tabList in valueList:
                for zone in tabList:
                    text += str(zone) + "\r\n"
                    changeCount += 1
            if changeCount == 0:
                self.writeToOutputView("Nothing changed")
                return

            # Give some option to check values and to cancel the write
            if QMessageBox.Cancel == QMessageBox.question(self, "Write zone(s) to ECU", text, QMessageBox.Save, QMessageBox.Cancel):
                return

            # Get the corresponding ECU Key from Combobox
            index = self.ui.ecuKeyComboBox.currentIndex()
            key = self.ui.ecuKeyComboBox.itemData(index)
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            # Setup LIN_ID if present
            lin = ""
            if "lin_id" in self.ecuObjectList:
                lin = "L" + self.ecuObjectList["lin_id"]

            if self.ecuObjectList["protocol"] == "uds":
#                self.udsCommunication.writeZoneList(self.ui.useSketchSeedGenerator.isChecked(), ecu, lin, key, valueList, self.ui.writeSecureTraceability.isChecked())
                self.udsCommunication.writeZoneList(False, ecu, lin, key, valueList, self.ui.writeSecureTraceability.isChecked())
            else:
                self.writeToOutputView("Protocol not supported yet!")
                return
        else:
            self.writeToOutputView("Port not open!")


    @Slot()
    def rebootEcu(self):
        if self.serialController.isOpen():
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            if self.ecuObjectList["protocol"] == "uds":
                self.udsCommunication.rebootEcu(ecu)
            else:
                self.writeToOutputView("Protocol not supported yet!")
                return
        else:
            self.writeToOutputView("Port not open!")

    @Slot()
    def readEcuFaults(self):
        if self.serialController.isOpen():
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            if self.ecuObjectList["protocol"] == "uds":
                self.udsCommunication.readEcuFaults(ecu)
            else:
                self.writeToOutputView("Protocol not supported yet!")
                return
        else:
            self.writeToOutputView("Port not open!")

    @Slot()
    def csvReadCallback(self, value: list):
        self.ui.treeView.changeZoneOption(value[0], value[1], value[2]);

    @Slot()
    def updateZoneDataback(self, zoneData: str, value: str, valueType: str):
        self.ui.treeView.changeZoneOption(zoneData, value, valueType)

    @Slot()
    def outputToTextEditCallback(self, text: str):
        self.writeToOutputView(text)

    @Slot()
    def serialPacketReceiverCallback(self, packet: list, time: float):
        self.writeToOutputView(str(packet))
        if self.stream != None:
            self.csvWriter.writerow(packet)
            self.stream.flush()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
