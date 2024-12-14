"""
   DiagnosticCommunication.py

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
from CalcCRC16X25 import CalcCRC16X25

class DiagnosticCommunication(QThread):
    receivedPacketSignal = Signal(list, float)
    outputToTextEditSignal = Signal(str)
    updateZoneDataSignal = Signal(str, str)
    algo = SeedKeyAlgorithm()
    crcx25 = CalcCRC16X25()
    writeQ = queue.Queue()
    ecuReadZone = ""
    zoneName = ""
    zoneActive = {}
    protocol = ""
    keepAlive = ""
    stopKeepAlive = ""
    startDiagmode = ""
    stopDiagmode = ""
    unlockServiceConfig = ""
    unlockResponseConfig = ""
    readSecureTraceability = ""
    secureTraceability = ""
    readEcuFaultsMode = ""
    readZoneTag = ""
    writeZoneTag = ""

    def __init__(self, serialPort, protocol: str(), simulation: bool()):
        super(DiagnosticCommunication, self).__init__()
        self.serialPort = serialPort
        self.simulation = simulation
        self.isRunning = False
        self.protocol = protocol
        if self.protocol == "uds":
            #self.crcx25.testCrc()
            self.keepAlive = "KU"
            self.stopKeepAlive = "S"
            self.startDiagmode = "1003"
            self.stopDiagmode = "1001"
            self.unlockServiceConfig = "2703"
            self.unlockResponseConfig = "2704"
            self.readSecureTraceability = "222901"
            self.secureTraceability = "2E2901FD000000010101"
            self.readEcuFaultsMode = "190209"
            self.readZoneTag = "22"
            self.writeZoneTag = "2E"
        elif self.protocol == "kwp_is":
            self.keepAlive = "KK"
            self.stopKeepAlive = "S"
            self.startDiagmode = "81"
            self.stopDiagmode = "82"
            self.unlockServiceConfig = "2783"
            self.unlockResponseConfig = "2784"
            self.readSecureTraceability = ""
            self.secureTraceability = ""
            self.readEcuFaultsMode = "190209"
            self.readZoneTag = "21"
            self.writeZoneTag = "34"
        else:
            print("Incorrect protocol: " + protocol)
            exit()

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
            if  cmd[2:6] == "2901":
                 return "62" + cmd[2:6] + "FD000000010101"
            elif cmd[2:6] == "F0FE":
                return "62" + cmd[2:6] + "FFFF000006E0280220032812000D03140002000002940165"
            elif cmd[2:6] == "F080":
                return "62" + cmd[2:6] + "9807513880000698261534801800FFFFFF01FFFFFFFF"
            elif cmd[2:6] == "F190":
                return "62" + cmd[2:6] + "56584B5550484E4B4B4C34323431383933"
            elif cmd[2:6] == "F18B":
                return "62" + cmd[2:6] + "090314"
            elif cmd[2:6] == "F18C":
                return "62" + cmd[2:6] + "29400895"
            return "62" + cmd[2:6] + "12345679"
        if cmd[:2] == "2E":
            return "6E" + cmd[2:6]
        if cmd == "KK":
            return "OK"
        if cmd == "81":
            return "C1D08F"
        if cmd == "82":
            return "C2"
        if cmd == "2783":
            return "67836B0A71E0"
        if cmd[:4] == "2784":
            return "6784"
        if cmd[:2] == "21":
            if cmd[2:4] == "FE":
                return "61" + cmd[2:4] + "FFFF000006E030082202061300FFFFFF0002000002948185"
            elif cmd[2:4] == "A0":
                return "61" + cmd[2:4] + "05C0FB0002000001"
            elif cmd[2:4] == "80":
                return "61" + cmd[2:4] + "9807513880000698261526801900FFFFFF01FFFFFFFF"
            elif cmd[2:4] == "90":
                return "61" + cmd[2:4] + "56584B5550484E4B4B4C34323431383933"
            elif cmd[2:4] == "8B":
                return "61" + cmd[2:4] + "090314"
            elif cmd[2:4] == "8C":
                return "61" + cmd[2:4] + "29400895"
            return "61" + cmd[2:4] + "12345679"
        if cmd[:2] == "34":
            return "6E" + cmd[2:4]
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
        receiveData = self.writeECUCommand(self.keepAlive)
        if receiveData != "OK":
            self.writeToOutputView("ECU Send keep-alive: Failed", receiveData)
            return False
        return True

    def stopSendingKeepAlive(self):
        receiveData = self.writeECUCommand(self.stopKeepAlive)
        if receiveData != "OK":
            self.writeToOutputView("Reset ECU Keep Alive: Failed", receiveData)
            return False
        return True

    def startDiagnosticMode(self):
        receiveData = self.writeECUCommand(self.startDiagmode)
        if len(receiveData) == 12 and receiveData[:4] == "5003":
            return True
        elif len(receiveData) == 6 and receiveData[:2] == "C1":
            return True
        self.writeToOutputView("Open Diagnostic session: Failed", receiveData)
        return False

    def stopDiagnosticMode(self):
        self.stopSendingKeepAlive()
        receiveData = self.writeECUCommand(self.stopDiagmode)
        if len(receiveData) == 12 and receiveData[:4] == "5001":
            return True
        elif len(receiveData) == 2 and receiveData[:2] == "C2":
            return True
        self.writeToOutputView("Closing Diagnostic session: Failed", receiveData)
        return False

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
        tryCnt = 8
        while tryCnt:
            receiveData = self.writeECUCommand(self.unlockServiceConfig)
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
            elif len(receiveData) == 12:
                if receiveData[:4] == "6703" or receiveData[:4] == "6783":
                    break;

        if tryCnt == 0:
            self.writeToOutputView("ECU Unlock Request: Failed", receiveData)
            return ""

        challenge = int(receiveData[4:12], 16)
        seed = "%0.8X" % self.algo.computeResponse(int(key, 16), challenge)
        return seed

    def sendUnlockingResponseForConfiguration(self, seed: str):
        reply = self.unlockResponseConfig + seed
        receiveData = self.writeECUCommand(reply)
        if len(receiveData) == 4:
            if receiveData[:4] == "6704" or receiveData[:4] == "6784":
                return True

        if receiveData == "7F2735":
            self.writeToOutputView("ECU unlock: Failed, ECU Reports Invalid Key", receiveData)
        else:
            self.writeToOutputView("ECU unlock: Failed", receiveData)
        return False

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
            if self.protocol == "kwp_is" and not(self.simulation):
                self.writeToOutputView("Writing KWP ECU: Not Supported yet!", receiveData)
                return

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
                    writeCmd = self.writeZoneTag + zone[0] + zone[1]
                    readCmd = self.readZoneTag + zone[0]
                    time.sleep(0.2)
                    receiveData = self.writeECUCommand(readCmd)
                    time.sleep(0.2)
                    self.writeZoneConfigurationCommand(writeCmd)
                    time.sleep(0.2)
                    receiveData = self.writeECUCommand(readCmd)

            receiveData = self.writeECUCommand(self.readSecureTraceability)
            if writeSecureTraceability:
                receiveData = self.writeECUCommand(self.secureTraceability)
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

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView("ECU Not selected!")
                return

            if not self.startDiagnosticMode():
                return

            receiveData = self.writeECUCommand(self.readEcuFaultsMode)
            if len(receiveData) < 4:
                self.writeToOutputView("Reading ECU Faults: Failed")

            if not self.stopDiagnosticMode():
                return

            self.writeToOutputView("Reading ECU Faults: Successful")

    def setZonesToRead(self, ecuID: str, lin: str, zoneList: dict):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit(["Serial Port Not Open", "", ""], time.time())
            return
        if self.isRunning == False:
            self.start();

        self.writeQ.put(ecuID)
        if lin != None and len(lin) > 1:
            self.writeQ.put(lin)
        self.writeQ.put(self.keepAlive)
        self.writeQ.put(self.startDiagmode)
        self.writeQ.put(zoneList)
        self.writeQ.put(self.stopKeepAlive)
        self.writeQ.put(self.stopDiagmode)

    def parseReadResponse(self, data: str):
        if len(data) == 0:
            self.receivedPacketSignal.emit([self.ecuReadZone, "Timeout", self.zoneName], time.time())
            return data

        decodedData = data;
        if len(decodedData) > 4:
            if (decodedData[0:2] == "62" or decodedData[0:2] == "61") and len(decodedData) > 6:
                # Get only response data
                answerZone = ""
                answer = ""
                if decodedData[0:2] == "62":
                    answerZone = decodedData[2:6]
                    answer = decodedData[6:]
                elif decodedData[0:2] == "61":
                    answerZone = decodedData[2:4]
                    answer = decodedData[4:]

                if answerZone.upper() != self.ecuReadZone.upper():
                    self.receivedPacketSignal.emit([self.ecuReadZone, "Requesed zone different from received zone", decodedData], time.time())
                    return data

                self.receivedPacketSignal.emit([self.ecuReadZone, answer, self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, answer)
            elif decodedData[0: + 4] == "5001":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Communication closed", self.zoneName], time.time())
            elif decodedData[0: + 4] == "5002":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Download session opened", self.zoneName], time.time())
            elif decodedData[0: + 4] == "5003":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Diagnostic session opened", self.zoneName], time.time())
            elif decodedData[0: + 4] == "6702":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unlocked successfully for download", self.zoneName], time.time())
            elif decodedData[0: + 4] == "6704":
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unlocked successfully for configuration", self.zoneName], time.time())
            elif decodedData[0: + 2] == "7F":
                if len(decodedData) >= 6 and decodedData[0: + 6] == "7F2231":
                    self.receivedPacketSignal.emit([self.ecuReadZone, "Request out of range", self.zoneName], time.time())
                    self.updateZoneDataSignal.emit(self.ecuReadZone, "Request out of range")
                else:
                    self.receivedPacketSignal.emit([self.ecuReadZone, "No Response", self.zoneName], time.time())
                    self.updateZoneDataSignal.emit(self.ecuReadZone, "No Response")
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unkown Error", self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unkown Error")
        elif len(decodedData) <= 2:
            if decodedData[0:2] == "OK":
                self.receivedPacketSignal.emit([self.ecuReadZone, "OK", self.zoneName], time.time())
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unkown Error", self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unkown Error")
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

                        # Send and receive data
                        ecuReadZoneSend = self.readZoneTag + self.ecuReadZone
                        receiveData = self.writeECUCommand(ecuReadZoneSend)
                        self.parseReadResponse(receiveData);
                        self.msleep(100)
                else:
                    # Just empty zone names
                    self.zoneName = ""
                    self.ecuReadZone = str(element).upper()

                    # Send and receive data
                    if self.ecuReadZone == self.startDiagmode:
                        # Timeout on open Diag Mode, No ECU? then stop reading
                        if not self.startDiagnosticMode():
                            self.writeToOutputView("Open Diagnostic session: Failed/Stopping", receiveData)
                            self.emptyQueue()
                            self.isRunning = False
                    elif self.ecuReadZone == self.stopDiagmode:
                        self.stopDiagnosticMode()
                    elif self.ecuReadZone == self.keepAlive:
                        self.startSendingKeepAlive()
                    elif self.ecuReadZone == self.stopKeepAlive:
                        self.stopSendingKeepAlive()
                    else:
                        receiveData = self.writeECUCommand(self.ecuReadZone)

            else:
                self.writeToOutputView("Reading ECU Zones: Successful")
                self.isRunning = False