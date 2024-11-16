"""
   UDSCommunication.py

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

import time
import queue
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QTextEdit

from SeedKeyAlgorithm import SeedKeyAlgorithm

class UDSCommunication(QThread):
    receivedPacketSignal = Signal(list, float)
    outputToTextEditSignal = Signal(str)
    updateZoneDataSignal = Signal(str, str, str)
    algo = SeedKeyAlgorithm()
    writeQ = queue.Queue()
    ecuReadZone = str()
    zoneName = str()
    formType = str()
    zoneActive = dict()

    def __init__(self, serialPort, simulation: bool):
        super(UDSCommunication, self).__init__()
        self.serialPort = serialPort
        self.simulation = simulation
        self.isRunning = False
        #self.algo.testCalculations()
        #receiveData = "670311BF5E67"
        #key = "D91C"
        #challenge = int(receiveData[4:12], 16)
        #seed = ("%0.8X" % self.algo.computeResponse(int(key, 16), challenge))
        #reply = "2704" + seed
        #print(reply)

    def stop(self):
        self.isRunning = False

    def __simulateAnswer(self, cmd: str):
        if cmd[:1] == ">":
            return "OK"
        if cmd[:1] == ":":
            return "6704"
        if cmd == "1003":
            return "500300C80014"
        if cmd == "1001":
            return "500100C80014"
        if cmd == "2703":
            return "67036B0A71E0"
        if cmd[:4] == "2704":
            return "6704"
        if cmd[:2] == "22":
            return "62" + cmd[2:6] + "0000"
        if cmd[:2] == "2E":
            return "6E" + cmd[2:6]
        return "Timeout"

    def writeToOutputView(self, text: str):
        self.outputToTextEditSignal.emit(text)

    def writeECUCommand(self, cmd: str):
        self.writeToOutputView("> " + cmd)
        receiveData = self.serialPort.sendReceive(cmd)
        if self.simulation and receiveData == "Timeout":
            receiveData = self.__simulateAnswer(cmd)
        self.writeToOutputView("< " + receiveData)
        return receiveData

    def writeZoneList(self, useSketchSeed: bool, ecuID: str, key: str, valueList: list, writeSecureTraceability: bool):
        if self.serialPort.isOpen():
            startDiagmode = "1003"
            stopDiagmode = "1001"
            sketchSeedSetup = ":" + key + ":03:03"
            unlockServiceConfig = "2703"
            unlockResponseConfig = "2704"
            readSsecureTraceability = "222901"
            secureTraceability = "2E2901FD000000010101"

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView("Selecting ECU: Failed")
                return

            receiveData = self.writeECUCommand(startDiagmode)
            if len(receiveData) != 12 or receiveData[:4] != "5003":
                self.writeToOutputView("Open Diagnostic session: Failed")
                return

            if useSketchSeed:
                receiveData = self.writeECUCommand(sketchSeedSetup)
                if len(receiveData) != 12 or receiveData[:4] != "6703":
                    self.writeToOutputView("ECU Seed Request: Failed")
                    receiveData = self.writeECUCommand(stopDiagmode)
                    return

                self.writeToOutputView("Waiting 1 Sec...")
                time.sleep(1)

            else:
                receiveData = self.writeECUCommand(unlockServiceConfig)
                if len(receiveData) != 12 or receiveData[:4] != "6703":
                    self.writeToOutputView("ECU Seed Request: Failed")
                    receiveData = self.writeECUCommand(stopDiagmode)
                    return

                challenge = int(receiveData[4:12], 16)
                seed = "%0.8X" % self.algo.computeResponse(int(key, 16), challenge)
                reply = unlockResponseConfig + seed

                receiveData = self.writeECUCommand("KU")
                if receiveData != "OK":
                    self.writeToOutputView("ECU Send keep-alive: Failed")
                    receiveData = self.writeECUCommand(stopDiagmode)
                    return

                self.writeToOutputView("Waiting 2 Sec...")
                time.sleep(2)

                receiveData = self.writeECUCommand(reply)
                if len(receiveData) != 4 or receiveData[:4] != "6704":
                    self.writeToOutputView("ECU unlock: Failed")
                    receiveData = self.writeECUCommand(stopDiagmode)
                    return

                receiveData = self.writeECUCommand("S")
                if receiveData != "OK":
                    self.writeToOutputView("Reset ECU Keep Alive: Failed")

            # Write Zones
            for tabList in valueList:
                for zone in tabList:
                    writeCmd = "2E" + zone[0] + zone[1]
                    readCmd = "22" + zone[0]
                    receiveData = self.writeECUCommand(readCmd)
                    receiveData = self.writeECUCommand(writeCmd)
                    if len(receiveData) != 6 or receiveData[:2] != "6E":
                        self.writeToOutputView("Configuration Write of Zone: Failed")
                    receiveData = self.writeECUCommand(readCmd)

            receiveData = self.writeECUCommand(readSsecureTraceability)
            if writeSecureTraceability:
                receiveData = self.writeECUCommand(secureTraceability)
                if len(receiveData) != 6 or receiveData[:2] != "6E":
                    self.writeToOutputView("Configuration Write of Secure Traceability Zone: Failed")
            else:
                self.writeToOutputView("NO Secure Traceability is Written!!")

            receiveData = self.writeECUCommand(stopDiagmode)
            if len(receiveData) != 12 or receiveData[:4] != "5001":
                self.writeToOutputView("Closing Diagnostic session: Failed")
                return

    def rebootEcu(self, ecuID: str):
        if self.serialPort.isOpen():
            self.writeToOutputView("Reboot ECU...")
            receiveData = self.serialPort.sendReceive(ecuID)
            if receiveData != "OK":
                self.writeToOutputView("ECU Not selected!")
                return

            receiveData = self.ecuZoneReaderThread.sendReceive("1103")
            if len(receiveData) != 4 or receiveData[:4] != "5103":
                self.writeToOutputView("Reboot: Failed")
                return

    def readEcuFaults(self, ecuID: str):
        if self.serialPort.isOpen():
            self.writeToOutputView("Read ECU Faults...")

            startDiagmode = "1003"
            stopDiagmode = "1001"
            readEcuFaults = "190209"

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView("ECU Not selected!")
                return

            receiveData = self.writeECUCommand(startDiagmode)
            if len(receiveData) != 12 or receiveData[:4] != "5003":
                self.writeToOutputView("Open Diagnostic session: Failed")
                return

            receiveData = self.writeECUCommand(readEcuFaults)
            if len(receiveData) < 4:
                self.writeToOutputView("Reading ECU Faults: Failed")

            receiveData = self.writeECUCommand(stopDiagmode)
            if len(receiveData) != 12 or receiveData[:4] != "5001":
                self.writeToOutputView("Closing Diagnostic session: Failed")
                return

    def setZonesToRead(self, ecuID: str, zoneList: dict):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit(["Serial Port Not Open", "", "", ""], time.time())
            return
        if self.isRunning == False:
            self.start();
        self.writeQ.put(ecuID)
        self.writeQ.put("1003")
        self.writeQ.put(zoneList)
        self.writeQ.put("1001")

    def readResponse(self):
        data = self.serialPort.readData()
        if len(data) == 0:
            self.receivedPacketSignal.emit([self.ecuReadZone, "Timeout", "string", "----", self.zoneName], time.time())
            return

        i = data.find(b"\r")
        decodedData = data[:i].decode("utf-8");
        if len(decodedData) > 4:
            if decodedData[0: + 2] == "62" and len(decodedData) > 6:
                # Get only responce data
                answerZone = decodedData[2: + 6]
                if answerZone.upper() != self.ecuReadZone.upper():
                    print(answerZone + " - " + self.ecuReadZone)
                    self.receivedPacketSignal.emit(["Requesed zone different from received zone", "", "", ""], time.time())
                    return
                answer = decodedData[6:]
                answerDecorated = answer
                valType = self.zoneActive["type"]

                # Check if we can find a "Decorated" answer from Combobox
                if self.formType == "combobox":
                    for paramObject in self.zoneActive["params"]:
                        if valType == "hex":
                            if int(paramObject["value"], 16) == int(answer, 16):
                                self.answerDecorated = str(paramObject["name"])

                self.receivedPacketSignal.emit([self.ecuReadZone, answer, valType, answerDecorated, self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, answer, valType)
            elif decodedData[0: + 4] == "5001":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Communication closed", "cmd answer", decodedData, self.zoneName], time.time())
            elif decodedData[0: + 4] == "5002":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Download session opened", "cmd answer", decodedData, self.zoneName], time.time())
            elif decodedData[0: + 4] == "5003":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Diagnostic session opened", "cmd answer", decodedData, self.zoneName], time.time())
            elif decodedData[0: + 4] == "6702":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unlocked successfully for download", "cmd answer", decodedData, self.zoneName], time.time())
            elif decodedData[0: + 4] == "6704":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unlocked successfully for configuration", "cmd answer", decodedData, self.zoneName], time.time())
            elif decodedData[0: + 2] == "7F":
                if len(decodedData) >= 6 and decodedData[0: + 6] == "7F2231":
                    self.receivedPacketSignal.emit([self.ecuReadZone, "Request out of range", "cmd answer", decodedData, self.zoneName], time.time())
                    self.updateZoneDataSignal.emit(self.ecuReadZone, "Request out of range", "cmd answer")
                else:
                    self.receivedPacketSignal.emit([self.ecuReadZone, "No Response", "cmd answer", decodedData, self.zoneName], time.time())
                    self.updateZoneDataSignal.emit(self.ecuReadZone, "No Response", "cmd answer")
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unkown Error", "cmd answer", decodedData, self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unkown Error", "cmd answer")
        elif len(decodedData) <= 2:
            if decodedData[0: + 2] == "OK":
                self.receivedPacketSignal.emit([self.ecuReadZone, "OK", "cmd answer", decodedData, self.zoneName], time.time())
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unkown Error", "cmd answer", decodedData, self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unkown Error", "cmd answer")

    def run(self):
        self.isRunning = True
        while self.isRunning:
            if not self.writeQ.empty():
                element = self.writeQ.get()
                if isinstance(element, dict):
                    for zoneIDObject in element:
                        self.ecuReadZone = str(zoneIDObject)
                        self.zoneActive = element[str(zoneIDObject)]
                        self.zoneName = str(self.zoneActive["name"])
                        self.formType = str(self.zoneActive["form_type"])

                        # Send and receive data
                        ecuReadZoneSend = "22" + str(zoneIDObject) + "\n"
                        self.serialPort.write(ecuReadZoneSend.encode("utf-8"))
                        self.readResponse();
                else:
                    print("Empty Zone")
                    # Just empty zone names
                    self.zoneName = ""
                    self.ecuReadZone = str(element)

                    # Send and receive data
                    command = str(element) + "\n";
                    self.serialPort.write(command.encode("utf-8"))
                    self.readResponse();
            else:
                self.msleep(100)
