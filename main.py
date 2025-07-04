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
import os
from datetime import datetime
from PySide6.QtCore import Qt, Slot, QIODevice, QTranslator
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

from PyPSADiagGUI import PyPSADiagGUI
import FileLoader
from DiagnosticCommunication import DiagnosticCommunication
from SeedKeyAlgorithm import SeedKeyAlgorithm
from SerialPort import SerialPort
from FileConverter import FileConverter
from EcuZoneTreeView  import EcuZoneTreeView
from MessageDialog  import MessageDialog
from i18n import i18n


"""
  - Change GUI in: PyPSADiagGUI.py
  - Run with: python main.py
"""
class MainWindow(QMainWindow):
    ui = PyPSADiagGUI()
    ecuObjectList = {}
    simulation = False
    scan = False
    stream = None
    csvWriter = None

    def __init__(self):
        super(MainWindow, self).__init__()
        self.lang_code = ""
        self.lang = False
        if len(sys.argv) >= 2:
            for arg in sys.argv:
                if arg == "--lang":
                    self.lang = True
                elif self.lang:
                    self.lang = False
                    self.lang_code = str(arg)
                elif arg == "--simu":
                    self.simulation = True
                elif arg == "--scan":
                    self.scan = True
                elif arg == "--checkcalc":
                    calc = SeedKeyAlgorithm()
                    calc.testCalculations()
                    exit()
                elif arg == "--help":
                    print("Use --simu      For simulation")
                    print("Use --lang nl   For NL translation")
                    exit()

        self.translator = QTranslator()
        qm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n", "translations", f"PyPSADiag_{self.lang_code}.qm")
        self.translator.load(qm_path)
        QApplication.instance().installTranslator(self.translator)

        self.ui.setupGUI(self, self.scan)

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
        self.ui.clearEcuFaults.clicked.connect(self.clearEcuFaults)
        self.ui.SearchConnectPort.clicked.connect(self.searchConnectPort)
        self.ui.ConnectPort.clicked.connect(self.connectPort)
        self.ui.DisconnectPort.clicked.connect(self.disconnectPort)
        self.ui.hideNoResponseZone.stateChanged.connect(self.hideNoResponseZones)

        # Connect Other/General signals to slots
        self.ui.command.returnPressed.connect(self.sendCommand)

        # Setup serial controller
        self.serialController = SerialPort(self.simulation)
        self.serialController.fillPortNameCombobox(self.ui.portNameComboBox)

        # Set initial button states
        self.ui.DisconnectPort.setEnabled(False)
        self.ui.readZone.setEnabled(False)
        self.ui.writeZone.setEnabled(False)
        self.ui.rebootEcu.setEnabled(False)
        self.ui.clearEcuFaults.setEnabled(False)
        self.ui.readEcuFaults.setEnabled(False)
        self.ui.virginWriteZone.setCheckState(Qt.Unchecked)
        self.ui.writeSecureTraceability.setCheckState(Qt.Checked)
#        self.ui.useSketchSeedGenerator.setCheckState(Qt.Unchecked)

        # UDS
        self.udsCommunication = DiagnosticCommunication(self.serialController, "uds")
        self.udsCommunication.receivedPacketSignal.connect(self.serialPacketReceiverCallback)
        self.udsCommunication.outputToTextEditSignal.connect(self.outputToTextEditCallback)
        self.udsCommunication.updateZoneDataSignal.connect(self.updateZoneDataback)

        # KWP_IS
        self.kwpisCommunication = DiagnosticCommunication(self.serialController, "kwp_is")
        self.kwpisCommunication.receivedPacketSignal.connect(self.serialPacketReceiverCallback)
        self.kwpisCommunication.outputToTextEditSignal.connect(self.outputToTextEditCallback)
        self.kwpisCommunication.updateZoneDataSignal.connect(self.updateZoneDataback)

        # KWP_HAB
        self.kwphabCommunication = DiagnosticCommunication(self.serialController, "kwp_hab")
        self.kwphabCommunication.receivedPacketSignal.connect(self.serialPacketReceiverCallback)
        self.kwphabCommunication.outputToTextEditSignal.connect(self.outputToTextEditCallback)
        self.kwphabCommunication.updateZoneDataSignal.connect(self.updateZoneDataback)

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
            self.writeToOutputView(i18n().tr("Not correct JSON file"))
            return;

        for zoneObject in zoneObjectList:
            self.ui.ecuComboBox.addItem(str(zoneObject))

        self.ui.treeView.updateView(ecuObjectList)

    def writeToOutputView(self, text: str):
        self.ui.output.append(str(datetime.now()) + " --|  " + text)
        self.ui.output.viewport().repaint()

    @Slot()
    def searchConnectPort(self):
        self.serialController.fillPortNameCombobox(self.ui.portNameComboBox)

    @Slot()
    def connectPort(self):
        self.serialController.open(self.ui.portNameComboBox.currentText(), 115200)
        # Set button states
        self.ui.ConnectPort.setEnabled(False)
        self.ui.DisconnectPort.setEnabled(True)
        # First send an Reset command
        cmd = "R"
        self.writeToOutputView("> " + cmd)
        receiveData = self.serialController.sendReceive(cmd)
        self.writeToOutputView("< " + receiveData)

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
        self.ui.clearEcuFaults.setEnabled(False)
        self.ui.readEcuFaults.setEnabled(False)
        self.ui.rebootEcu.setEnabled(False)
#        self.ui.useSketchSeedGenerator.setCheckState(Qt.Unchecked)
#        self.ui.useSketchSeedGenerator.setEnabled(True)

    @Slot()
    def hideNoResponseZones(self, state):
        self.ui.treeView.hideNoResponseZones(state == 2)

    @Slot()
    def sendCommand(self):
        if self.serialController.isOpen():
            cmd = self.ui.command.text()
            self.ui.command.clear()
            self.writeToOutputView(cmd)
            self.receiveData = self.serialController.sendReceive(cmd)
            self.writeToOutputView(self.receiveData)
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))

    @Slot()
    def openCSVFile(self):
        path = os.path.join(os.path.dirname(__file__), "csv")
        fileName = QFileDialog.getOpenFileName(self, i18n().tr("Open CSV Zone File"), path, i18n().tr("CSV Files") + "(*.csv)")
        if fileName[0] == "":
            return

        self.ui.treeView.clearZoneListValues()
        self.ui.setFilePathInWindowsTitle(fileName[0])
        self.fileLoaderThread.enable(fileName[0], 0)

    @Slot()
    def saveCSVFile(self):
        path = os.path.join(os.path.dirname(__file__), "csv")
        fileName = QFileDialog.getSaveFileName(self, i18n().tr("Save CSV Zone File"), path, i18n().tr("CSV Files") + "(*.csv)")
        if fileName[0] == "":
            return

        # Open CSV for writing
        self.ui.setFilePathInWindowsTitle(fileName[0])
        self.stream = open(fileName[0], 'w', newline='')
        self.csvWriter = csv.writer(self.stream)
        if self.stream != None:
            valueList = self.ui.treeView.getValuesAsCSV()
            for tabList in valueList:
                for zone in tabList:
                    self.csvWriter.writerow(zone)
            self.stream.flush()

    @Slot()
    def openZoneFile(self):
        path = os.path.join(os.path.dirname(__file__), "json")
        fileName = QFileDialog.getOpenFileName(self, i18n().tr("Open JSON Zone File"), path, i18n().tr("JSON Files") + "(*.json)")
        if fileName[0] == "":
            return
        file = open(fileName[0], 'r', encoding='utf-8')
        jsonFile = file.read()
        self.ecuObjectList = json.loads(jsonFile.encode("utf-8"))
        # Do we need to include a JSON File and attach it to 'zones'
        if "include_zone_object" in self.ecuObjectList:
            includeZonePath = os.path.join(os.path.dirname(__file__), self.ecuObjectList["include_zone_object"])
            if os.path.exists(includeZonePath):
                includeZoneFile = open(includeZonePath, 'r', encoding='utf-8')
                includeJsonFile = includeZoneFile.read()
                includeObjectList = json.loads(includeJsonFile.encode("utf-8"))
                self.ecuObjectList["zones"].update(includeObjectList)
            else:
                self.writeToOutputView(i18n().tr("Include Zone file not found: ") + includeZonePath)

        self.updateEcuZonesAndKeys(self.ecuObjectList)
        self.ui.setFilePathInWindowsTitle("")
        self.ui.readZone.setEnabled(True)
        self.ui.writeZone.setEnabled(True)
        self.ui.writeZone.setEnabled(True)
        self.ui.clearEcuFaults.setEnabled(True)
        self.ui.readEcuFaults.setEnabled(True)
        self.ui.rebootEcu.setEnabled(True)

    @Slot()
    def readZone(self):
        if self.serialController.isOpen():
            path = os.path.join(os.path.dirname(__file__), "csv")
            fileName = QFileDialog.getSaveFileName(self, i18n().tr("Save CSV Zone File"), path, i18n().tr("CSV Files") + "(*.csv)")
            if fileName[0] == "":
                return

            # Open CSV for writing
            self.ui.setFilePathInWindowsTitle(fileName[0])
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
                    zone = {}
                    zone[self.ui.ecuComboBox.currentText()] = self.ecuObjectList["zones"][self.ui.ecuComboBox.currentText()];
                    self.udsCommunication.setZonesToRead(ecu, lin, zone)
            elif self.ecuObjectList["protocol"] == "kwp_is":
                # Read Requested Zone or ALL Zones from ECU
                if self.ui.ecuComboBox.currentIndex() == 0:
                    self.kwpisCommunication.setZonesToRead(ecu, lin, self.ecuObjectList["zones"])
                else:
                    zone = {}
                    zone[self.ui.ecuComboBox.currentText()] = self.ecuObjectList["zones"][self.ui.ecuComboBox.currentText()];
                    self.kwpisCommunication.setZonesToRead(ecu, lin, zone)
            elif self.ecuObjectList["protocol"] == "kwp_hab":
                # Read Requested Zone or ALL Zones from ECU
                if self.ui.ecuComboBox.currentIndex() == 0:
                    self.kwphabCommunication.setZonesToRead(ecu, lin, self.ecuObjectList["zones"])
                else:
                    zone = {}
                    zone[self.ui.ecuComboBox.currentText()] = self.ecuObjectList["zones"][self.ui.ecuComboBox.currentText()];
                    self.kwphabCommunication.setZonesToRead(ecu, lin, zone)
            else:
                self.writeToOutputView(i18n().tr("Protocol not supported yet!"))
                return
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))


    @Slot()
    def writeZone(self):
        if self.serialController.isOpen():
            # Setup text of changed zones and put it into MessageBox
            virginWrite = self.ui.virginWriteZone.isChecked()
            self.ui.virginWriteZone.setCheckState(Qt.Unchecked)
            text = ""
            changeCount = 0
            valueList = self.ui.treeView.getZoneListOfHexValue(virginWrite)
            for tabList in valueList:
                for zone in tabList:
                    text += str(zone) + "\r\n"
                    changeCount += 1
            if changeCount == 0:
                self.writeToOutputView(i18n().tr("Nothing changed"))
                return

            # Give some option to check values and to cancel the write
            changedialog = MessageDialog(self, i18n().tr("Write zone(s) to ECU"), i18n().tr("Write"), text)
            if MessageDialog.Rejected == changedialog.exec():
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
            elif self.ecuObjectList["protocol"] == "kwp_is":
                self.kwpisCommunication.writeZoneList(False, ecu, lin, key, valueList, self.ui.writeSecureTraceability.isChecked())
            elif self.ecuObjectList["protocol"] == "kwp_hab":
                self.kwphabCommunication.writeZoneList(False, ecu, lin, key, valueList, self.ui.writeSecureTraceability.isChecked())
            else:
                self.writeToOutputView(i18n().tr("Protocol not supported yet!"))
                return
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))


    @Slot()
    def rebootEcu(self):
        if self.serialController.isOpen():
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            if self.ecuObjectList["protocol"] == "uds":
                self.udsCommunication.rebootEcu(ecu)
            elif self.ecuObjectList["protocol"] == "kwp_hab":
                self.kwphabCommunication.rebootEcu(ecu)
            else:
                self.writeToOutputView(i18n().tr("Protocol not supported yet!"))
                return
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))

    @Slot()
    def readEcuFaults(self):
        if self.serialController.isOpen():
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            if self.ecuObjectList["protocol"] == "uds":
                self.udsCommunication.readEcuFaults(ecu)
            else:
                self.writeToOutputView(i18n().tr("Protocol not supported yet!"))
                return
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))

    @Slot()
    def clearEcuFaults(self):
        if self.serialController.isOpen():
            # Setup CAN_EMIT_ID
            ecu = ">" + self.ecuObjectList["tx_id"] + ":" + self.ecuObjectList["rx_id"]

            # Give some option to cancel the Clear Fault Codes
            changedialog = MessageDialog(self, i18n().tr("Clearing Fault Codes of ECU:"), i18n().tr("Ok"), ecu)
            if MessageDialog.Rejected == changedialog.exec():
                return

            if self.ecuObjectList["protocol"] == "uds":
                self.udsCommunication.clearEcuFaults(ecu)
            else:
                self.writeToOutputView(i18n().tr("Protocol not supported yet!"))
                return
        else:
            self.writeToOutputView(i18n().tr("Port not open!"))

    @Slot()
    def csvReadCallback(self, value: list):
        # Did we had an empty line in CSV? Then skip it.
        if len(value) >= 2:
            self.ui.treeView.changeZoneOption(value[0], value[1]);

    @Slot()
    def updateZoneDataback(self, zoneData: str, value: str):
        self.ui.treeView.changeZoneOption(zoneData, value)

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
