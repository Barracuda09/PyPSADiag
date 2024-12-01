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
        emptyQueue()

    def emptyQueue(self):
        while not self.writeQ.empty():
            try:
                self.writeQ.get(block=False)
            except:
                continue

    def __simulateAnswer(self, cmd: str):
        if cmd[:1] == ">":
            return "OK"
        if cmd == "KU":
            return "OK"
        if cmd == "S":
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
            if cmd[2:6] == "F0FE":
                return "62" + cmd[2:6] + "FFFF000006E030082202061300FFFFFF0002000002948185"
            elif cmd[2:6] == "F080":
                return "62" + cmd[2:6] + "9807513880000698261526801900FFFFFF01FFFFFFFF"
            return "62" + cmd[2:6] + "12345679"
        if cmd[:2] == "2E":
            return "6E" + cmd[2:6]
        return "Timeout"

    def writeToOutputView(self, text: str, reply: str = None):
        if reply != None:
            text = text + " (" + reply + ")"
        self.outputToTextEditSignal.emit(text)

    def writeECUCommand(self, cmd: str):
        self.writeToOutputView("> " + cmd)
        receiveData = self.serialPort.sendReceive(cmd)
        if self.simulation and receiveData == "Timeout":
            receiveData = self.__simulateAnswer(cmd)
        # Check response we need to retry reading
        # 7F3E03 (Custom error)
        # 7Fxx78 (Request Correctly Received - Response Pending)
        while receiveData == "7F3E03" or (len(receiveData) == 6 and receiveData[:2] == "7F" and receiveData[4:6] == "78"):
            self.writeToOutputView("< " + receiveData + "  ** Skipping **")
            time.sleep(0.2)
            receiveData = self.serialPort.readData()
        self.writeToOutputView("< " + receiveData)
        return receiveData

    def startSendingKeepAlive(self):
        receiveData = self.writeECUCommand("KU")
        if receiveData != "OK":
            self.writeToOutputView("ECU Send keep-alive: Failed", receiveData)
            return False
        return True

    def stopSendingKeepAlive(self):
        receiveData = self.writeECUCommand("S")
        if receiveData != "OK":
            self.writeToOutputView("Reset ECU Keep Alive: Failed", receiveData)
            return False
        return True

    def startDiagnosticMode(self):
        startDiagmode = "1003"
        receiveData = self.writeECUCommand(startDiagmode)
        if len(receiveData) != 12 or receiveData[:4] != "5003":
            self.writeToOutputView("Open Diagnostic session: Failed", receiveData)
            return False
        return True

    def stopDiagnosticMode(self):
        self.stopSendingKeepAlive()
        stopDiagmode = "1001"
        receiveData = self.writeECUCommand(stopDiagmode)
        if len(receiveData) != 12 or receiveData[:4] != "5001":
            self.writeToOutputView("Closing Diagnostic session: Failed", receiveData)
            return False
        return True

    def setupSketchSeedForDiagnoticMode(self, key: str):
        sketchSeedSetup = ":" + key + ":03:03"
        receiveData = self.writeECUCommand(sketchSeedSetup)
        tryCnt = 8
        while len(receiveData) >= 4 and receiveData[:4] != "6704":
            self.writeToOutputView("ECU Seed Request: Waiting", receiveData)
            receiveData = self.serialPort.readData()
            time.sleep(2)
            tryCnt -= 1
            if tryCnt == 0:
                self.writeToOutputView("Write Configuration Zone: Failed", receiveData)
                return False
        return True

    def unlockingServiceForConfiguration(self, key: str):
        unlockServiceConfig = "2703"
        tryCnt = 8
        while tryCnt:
            receiveData = self.writeECUCommand(unlockServiceConfig)
            if len(receiveData) != 12:
                if len(receiveData) >= 6:
                    # Unlocking - Required time delay not expired
                    if receiveData[:6] == "7F2737" or receiveData == "7F3E03":
                        self.writeToOutputView("ECU Unlock Request: Retrying in 2 Seconds", receiveData)
                        tryCnt -= 1;
                        time.sleep(2)
                    else:
                        tryCnt = 0
                else:
                    tryCnt = 0
            elif len(receiveData) == 12 and receiveData[:4] == "6703":
                break;

        if tryCnt == 0:
            self.writeToOutputView("ECU Unlock Request: Failed", receiveData)
            return ""

        challenge = int(receiveData[4:12], 16)
        seed = "%0.8X" % self.algo.computeResponse(int(key, 16), challenge)
        return seed

    def sendUnlockingResponseForConfiguration(self, seed: str):
        unlockResponseConfig = "2704"
        reply = unlockResponseConfig + seed
        receiveData = self.writeECUCommand(reply)
        if len(receiveData) != 4 or receiveData[:4] != "6704":
            self.writeToOutputView("ECU unlock: Failed", receiveData)
            return False
        return True

    def writeZoneConfigurationCommand(self, cmd: str):
        receiveData = self.writeECUCommand(cmd)
        if len(receiveData) == 6 and receiveData[:2] == "6E":
            return True

        # Is Configuration Write in progress? then wait untill finished
        if len(receiveData) == 6 and (receiveData == "7F2E78" or receiveData == "7F3E03"):
            self.writeToOutputView("Write Configuration Zone in progress", receiveData)
            tryCnt = 32
            while len(receiveData) == 6 and (receiveData == "7F2E78" or receiveData == "7F3E03"):
                receiveData = self.serialPort.readData()
                tryCnt -= 1
                if tryCnt == 0:
                    self.writeToOutputView("Write Configuration Zone: Failed", receiveData)
                    return False
            self.writeToOutputView("Write Configuration Zone: Ok", receiveData)
            return True
        else:
            self.writeToOutputView("Write Configuration Zone: Failed", receiveData)
            return False

    def writeZoneList(self, useSketchSeed: bool, ecuID: str, lin: str, key: str, valueList: list, writeSecureTraceability: bool):
        if self.serialPort.isOpen():
            readSecureTraceability = "222901"
            secureTraceability = "2E2901FD000000010101"

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView("Selecting ECU: Failed", receiveData)
                return

            if lin != None and len(lin) > 1:
                receiveData = self.writeECUCommand(lin)
                if receiveData != "OK":
                    self.writeToOutputView("Selecting LIN ECU: Failed")
                    return

            if not self.stopDiagnosticMode():
                return

            time.sleep(0.5)

            if not self.startSendingKeepAlive():
                return

            if not self.startDiagnosticMode():
                return

            time.sleep(0.5)

            if useSketchSeed:
                if not self.setupSketchSeedForDiagnoticMode(key):
                    self.stopDiagnosticMode()
                    return

            else:
                seed = self.unlockingServiceForConfiguration(key)
                if len(seed) == 0:
                    self.stopDiagnosticMode()
                    return

                self.writeToOutputView("Waiting 2 Sec...")
                time.sleep(2)

                if not self.sendUnlockingResponseForConfiguration(seed):
                    self.stopDiagnosticMode()
                    return

                if not self.stopSendingKeepAlive():
                    return

            # Write Zones
            for tabList in valueList:
                for zone in tabList:
                    time.sleep(0.2)
                    writeCmd = "2E" + zone[0] + zone[1]
                    readCmd = "22" + zone[0]
                    time.sleep(0.2)
                    receiveData = self.writeECUCommand(readCmd)
                    time.sleep(0.2)
                    self.writeZoneConfigurationCommand(writeCmd)
                    time.sleep(0.2)
                    receiveData = self.writeECUCommand(readCmd)

            receiveData = self.writeECUCommand(readSecureTraceability)
            if writeSecureTraceability:
                receiveData = self.writeECUCommand(secureTraceability)
                if len(receiveData) != 6 or receiveData[:2] != "6E":
                    self.writeToOutputView("Configuration Write of Secure Traceability Zone: Failed", receiveData)
            else:
                self.writeToOutputView("NO Secure Traceability is Written!!")

            if not self.stopDiagnosticMode():
                return

            self.writeToOutputView("Write Successful")

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

    def setZonesToRead(self, ecuID: str, lin: str, zoneList: dict):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit(["Serial Port Not Open", "", "", ""], time.time())
            return
        if self.isRunning == False:
            self.start();

        startDiagmode = "1003"
        stopDiagmode = "1001"

        self.writeQ.put(ecuID)
        if lin != None and len(lin) > 1:
            self.writeQ.put(lin)
        self.writeQ.put(startDiagmode)
        self.writeQ.put(zoneList)
        self.writeQ.put(stopDiagmode)

    def parseReadResponse(self, data: str):
        if len(data) == 0:
            self.receivedPacketSignal.emit([self.ecuReadZone, "Timeout", "string", "----", self.zoneName], time.time())
            return data

        decodedData = data;
        if len(decodedData) > 4:
            if decodedData[0: + 2] == "62" and len(decodedData) > 6:
                # Get only response data
                answerZone = decodedData[2: + 6]
                if answerZone.upper() != self.ecuReadZone.upper():
                    self.receivedPacketSignal.emit([self.ecuReadZone, "Requesed zone different from received zone", "", ""], time.time())
                    return data
                answer = decodedData[6:]
                answerDecorated = answer
                valType = "None"
                if type in self.zoneActive:
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
        return data

    def run(self):
        self.isRunning = True
        while self.isRunning:
            if not self.writeQ.empty():
                element = self.writeQ.get()
                if isinstance(element, dict):
                    for zoneIDObject in element:
                        self.ecuReadZone = str(zoneIDObject).upper()
                        self.zoneActive = element[str(zoneIDObject)]
                        self.zoneName = str(self.zoneActive["name"])
                        self.formType = str(self.zoneActive["form_type"])

                        # Send and receive data
                        ecuReadZoneSend = "22" + self.ecuReadZone
                        receiveData = self.writeECUCommand(ecuReadZoneSend)
                        self.parseReadResponse(receiveData);
                        self.msleep(100)
                else:
                    # Just empty zone names
                    self.zoneName = ""
                    self.ecuReadZone = str(element).upper()

                    # Send and receive data
                    command = str(element);
                    receiveData = self.writeECUCommand(command)

                    # Timeout on open Diag Mode, No ECU? then stop reading
                    if element == "1003" and receiveData == "Timeout":
                        self.writeToOutputView("Open Diagnostic session: Failed/Stopping", receiveData)
                        self.emptyQueue()
            else:
                self.msleep(100)
