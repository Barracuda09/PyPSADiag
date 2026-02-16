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

import time, datetime
import queue
import json
import os
from PySide6.QtCore import Qt, QThread, Signal, QEventLoop
from PySide6.QtWidgets import QApplication, QTextEdit

from SeedKeyAlgorithm import SeedKeyAlgorithm
from CalcCRC16X25 import CalcCRC16X25
from i18n import i18n
from DecodeCalUlpFile import DecodeCalUlpFile

class DiagnosticCommunication(QThread):
    receivedPacketSignal = Signal(list, float)
    outputToTextEditSignal = Signal(str)
    updateZoneDataSignal = Signal(str, str)
    readZoneListDoneSignal = Signal()
    algo = SeedKeyAlgorithm()
    crcx25 = CalcCRC16X25()
    writeQ = queue.Queue()
    ecuReadZone = ""
    zoneName = ""
    zoneActive = {}
    protocol = ""
    keepAlive = ""
    stopKeepAlive = ""
    startDownmode = ""
    startDiagmode = ""
    stopDiagmode = ""
    rebootECU = ""
    unlockServiceConfig = ""
    unlockResponseConfig = ""
    readSecureTraceability = ""
    secureTraceability = ""
    readEcuFaultsMode = ""
    clearEcuFaultsMode = ""
    readZoneTag = ""
    writeZoneTag = ""

    def __init__(self, serialPort, protocol: str()):
        super(DiagnosticCommunication, self).__init__()
        self.serialPort = serialPort
        self.isRunning = False
        self.protocol = protocol
        if self.protocol == "uds":
            #self.crcx25.testCrc()
            self.keepAlive = "KU"
            self.stopKeepAlive = "S"
            self.startDownmode = "1002"
            self.startDiagmode = "1003"
            self.stopDiagmode = "1001"
            self.rebootECU = "1103"
            self.unlockServiceDownload = "2701"
            self.unlockResponseDownload = "2702"
            self.unlockServiceConfig = "2703"
            self.unlockResponseConfig = "2704"
            self.readSecureTraceability = "222901"
            self.secureTraceability = "2E2901FD000000010101"
            self.readEcuFaultsMode = "190209"
            self.clearEcuFaultsMode = "14FFFFFF"
            self.readZoneTag = "22"
            self.writeZoneTag = "2E"
        elif self.protocol == "kwp_is":
            self.keepAlive = "KK"
            self.stopKeepAlive = "S"
            self.startDiagmode = "81"
            self.stopDiagmode = "82"
            self.rebootECU = ""
            self.unlockServiceDownload = "2781"
            self.unlockResponseDownload = "2782"
            self.unlockServiceConfig = "2783"
            self.unlockResponseConfig = "2784"
            self.readSecureTraceability = ""
            self.secureTraceability = ""
            self.readEcuFaultsMode = "17FF00"
            self.clearEcuFaultsMode = "14FF00"
            self.readZoneTag = "21"
            self.writeZoneTag = "34"
        elif self.protocol == "kwp_hab":
            self.keepAlive = "KK"
            self.stopKeepAlive = "S"
            self.startDiagmode = "10C0"
            self.stopDiagmode = "1081"
            self.rebootECU = "31A800"
            self.unlockServiceDownload = "2781"
            self.unlockResponseDownload = "2782"
            self.unlockServiceConfig = "2783"
            self.unlockResponseConfig = "2784"
            self.readSecureTraceability = ""
            self.secureTraceability = ""
            self.readEcuFaultsMode = "17FF00"
            self.clearEcuFaultsMode = "14FF00"
            self.readZoneTag = "21"
            self.writeZoneTag = "3B"
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

    def __openErrorResponseTranslated(self):
        fileName = os.path.join(os.path.dirname(__file__), "data/ErrorResponse.json")
        file = open(fileName, 'r', encoding='utf-8')
        jsonFile = file.read()
        responseList = json.loads(jsonFile.encode("utf-8"))
        # Build translated Error Dictionary
        errorList = {}
        for response in responseList:
            errorList[response] = i18n().tr(responseList[response]["name"])
        return errorList

    def stop(self):
        self.isRunning = False
        self.emptyQueue()

    def emptyQueue(self):
        while not self.writeQ.empty():
            try:
                self.writeQ.get(block=False)
            except:
                continue

    def writeToOutputView(self, text: str, reply: str = None):
        if reply != None:
            text = text + " (" + reply + ")"
        self.outputToTextEditSignal.emit(text)

    def writeECUCommand(self, cmd: str, log=True):
        if log:
            self.writeToOutputView("> " + cmd)
        receiveData = self.serialPort.sendReceive(cmd)
        # Check response we need to retry reading
        # 7F3E03 (Custom error)
        # 7Fxx78 (Request Correctly Received - Response Pending)
        if len(receiveData) >= 6:
            i = receiveData.find("7F3E03")
            while i >= 0 or (receiveData[:2] == "7F" and receiveData[4:6] == "78"):
                self.writeToOutputView("< " + receiveData + "  " +  i18n().tr("** Skipping/Stripping **"))
                time.sleep(0.2)
                if i > 0:
                    # Custom Error '7F3E03' is not at first position, so strip it from reply.
                    # And add next reply to receive buffer.
                    receiveData = receiveData[:i]
                    self.writeToOutputView("< " + receiveData + "  " + i18n().tr("** Stripping **"))
                    receiveData += self.serialPort.readData()
                else:
                    receiveData = self.serialPort.readData()

                # Check did we receive again the custom error
                i = receiveData.find("7F3E03")

        if log:
            self.writeToOutputView("< " + receiveData)
        return receiveData

    def startSendingKeepAlive(self):
        receiveData = self.writeECUCommand(self.keepAlive)
        if receiveData != "OK":
            self.writeToOutputView(i18n().tr("ECU Send keep-alive: Failed"), receiveData)
            return False
        return True

    def stopSendingKeepAlive(self):
        receiveData = self.writeECUCommand(self.stopKeepAlive)
        if receiveData != "OK":
            self.writeToOutputView(i18n().tr("Reset ECU Keep Alive: Failed"), receiveData)
            return False
        return True

    def startDiagnosticMode(self):
        receiveData = self.writeECUCommand(self.startDiagmode)
        if len(receiveData) >= 4 and receiveData[:4] == "5003":
            return True
        elif len(receiveData) == 6 and receiveData[:2] == "C1":
            return True
        elif len(receiveData) == 4 and receiveData[:4] == "50C0":
            return True
        self.writeToOutputView(i18n().tr("Open Diagnostic session: Failed"), receiveData)
        return False

    def startDownloadMode(self):
        receiveData = self.writeECUCommand(self.startDownmode)
        if len(receiveData) >= 4 and receiveData[:4] == "5002":
            return True
        self.writeToOutputView(i18n().tr("Open Download session: Failed"), receiveData)
        return False

    def stopDiagnosticMode(self):
        self.stopSendingKeepAlive()
        receiveData = self.writeECUCommand(self.stopDiagmode)
        if len(receiveData) >= 4 and receiveData[:4] == "5001":
            return True
        elif len(receiveData) == 2 and receiveData[:2] == "C2":
            return True
        elif len(receiveData) == 4 and receiveData[:4] == "5081":
            return True
        self.writeToOutputView(i18n().tr("Closing Diagnostic session: Failed"), receiveData)
        return False

    def setupSketchSeedForDiagnoticMode(self, key: str):
        sketchSeedSetup = ":" + key + ":03:03"
        receiveData = self.writeECUCommand(sketchSeedSetup)
        tryCnt = 8
        while len(receiveData) >= 4 and receiveData[:4] != "6704":
            self.writeToOutputView(i18n().tr("ECU Seed Request: Waiting"), receiveData)
            receiveData = self.serialPort.readData()
            time.sleep(2)
            tryCnt -= 1
            if tryCnt == 0:
                self.writeToOutputView(i18n().tr("Write Configuration Zone: Failed"), receiveData)
                return False
        return True

    def unlockingServiceForConfiguration(self, key: str):
        return self.__unlockingServiceWith(self.unlockServiceConfig, key)

    def unlockingServiceForDownload(self, key: str):
        return self.__unlockingServiceWith(self.unlockServiceDownload, key)

    def __unlockingServiceWith(self, service: str, key: str):
        tryCnt = 8
        while tryCnt:
            receiveData = self.writeECUCommand(service)
            if len(receiveData) != 12:
                if len(receiveData) >= 6:
                    # Unlocking - Required time delay not expired
                    if receiveData[:6] == "7F2737" or receiveData == "7F3E03":
                        self.writeToOutputView(i18n().tr("ECU Unlock Request: Retrying in 2 Seconds"), receiveData)
                        tryCnt -= 1;
                        time.sleep(2)
                    else:
                        tryCnt = 0
                else:
                    tryCnt = 0
            elif len(receiveData) == 12:
                serviceID = int(service, 16) | 0x4000
                responseID = int(receiveData[:4], 16)
                if serviceID == responseID:
                    break;
                else:
                    tryCnt = 0
            else:
                tryCnt = 0

        if tryCnt == 0:
            error = i18n().tr("ECU Unlock Failed:")
            if len(receiveData) >= 6 and receiveData[:2] == "7F":
                errorResponseList = self.__openErrorResponseTranslated()
                error = receiveData[4:6]
                cmd = receiveData[2:4]
                if error in errorResponseList:
                    error = i18n().tr("ECU Unlock Failed") + " (" + cmd + "): " + errorResponseList[error]

            self.writeToOutputView(error, receiveData)
            return ""

        challenge = int(receiveData[4:12], 16)
        seed = "%0.8X" % self.algo.computeResponse(int(key, 16), challenge)
        return seed

    def sendUnlockingResponseForConfiguration(self, seed: str):
        return self.__sendUnlockingResponseWith(self.unlockResponseConfig, seed)

    def sendUnlockingResponseForDownload(self, seed: str):
        return self.__sendUnlockingResponseWith(self.unlockResponseDownload, seed)

    def __sendUnlockingResponseWith(self, service: str, seed: str):
        reply = service + seed
        receiveData = self.writeECUCommand(reply)
        if len(receiveData) == 4:
            serviceID = int(service, 16) | 0x4000
            responseID = int(receiveData[:4], 16)
            if serviceID == responseID:
                return True

        error = i18n().tr("ECU Unlock Failed:")
        if len(receiveData) >= 6 and receiveData[:2] == "7F":
            errorResponseList = self.__openErrorResponseTranslated()
            error = receiveData[4:6]
            cmd = receiveData[2:4]
            if error in errorResponseList:
                error = i18n().tr("ECU Unlock Failed") + " (" + cmd + "): " + errorResponseList[error]

        self.writeToOutputView(error, receiveData)
        return False

    def __eraseEcuFlash(self, flashType: str):
        if len(flashType) != 2:
            return False
        flashErase = "3101FF00"
        receiveData = self.writeECUCommand(flashErase + flashType + "F05A")
        tryCnt = 80
        while tryCnt:
            if len(receiveData) >= 10:
                if receiveData[:10] == "7101FF0001" or receiveData[:10] == "7103FF0001":
                    time.sleep(0.5)
                    flashErase = "3103FF00"
                    receiveData = self.writeECUCommand(flashErase)
                elif receiveData[:10] == "7103FF0002":
                    return True
            tryCnt -= 1

        return False

    def __prepareEcuFlash(self, flashType: str):
        if len(flashType) != 2:
            return False
        receiveData = self.writeECUCommand("34" + flashType + "110000")
        tryCnt = 5
        while tryCnt:
            if len(receiveData) >= 6:
                if receiveData[:6] == "741000":
                    return True
            time.sleep(0.5)
            tryCnt -= 1

        return False

    def __eraseZI(self):
        receiveData = self.writeECUCommand("3101FF04")
        tryCnt = 80
        while tryCnt:
            if len(receiveData) >= 10:
                if receiveData[:10] == "7101FF0401" or receiveData[:10] == "7103FF0401":
                    time.sleep(0.5)
                    receiveData = self.writeECUCommand("3103FF04")
                elif receiveData[:10] == "7103FF0402":
                    return True
            tryCnt -= 1

        return False

    def __flashAutoControl(self):
        receiveData = self.writeECUCommand("37")
        if len(receiveData) >= 2:
            if receiveData == "77":
                return True

        return False

    def writeUDSZoneConfigurationCommand(self, zone: str(), data: str()):
        writeCmd = self.writeZoneTag + zone + data
        receiveData = self.writeECUCommand(writeCmd)
        if len(receiveData) == 6 and receiveData[:2] == "6E":
            return True

        # Is Configuration Write in progress? then wait untill finished
        if len(receiveData) == 6 and (receiveData == "7F2E78" or receiveData == "7F3E03"):
            self.writeToOutputView(i18n().tr("Write Configuration Zone in progress"), receiveData)
            tryCnt = 32
            while len(receiveData) == 6 and (receiveData == "7F2E78" or receiveData == "7F3E03"):
                receiveData = self.serialPort.readData()
                tryCnt -= 1
                if tryCnt == 0:
                    self.writeToOutputView(i18n().tr("Write Configuration Zone: Failed"), receiveData)
                    return False
            self.writeToOutputView(i18n().tr("Write Configuration Zone: Ok"), receiveData)
            return True
        else:
            message = i18n().tr("Write Configuration Zone: Failed")
            if len(receiveData) >= 6 and receiveData[:2] == "7F":
                errorResponseList = self.__openErrorResponseTranslated()
                error = receiveData[4:6]
                cmd = receiveData[2:4]
                if error in errorResponseList:
                    message = message + " (" + error + ") " + errorResponseList[error]

            self.writeToOutputView(message, receiveData)
            return False

    def writeKWPisZoneConfigurationCommand(self, zone: str(), data: str()):
        addrHigh = "00"
        addrMid = "00"
        addrLow = "00"
        address = addrHigh + addrMid + addrLow
        securedTraceability = "FD000000"
        indexTelecodage = data[0:2]
        zoneData = data[4:6]
        subCmd = indexTelecodage + zoneData + securedTraceability
        size = "%0.2X" % int((len(subCmd) / 2))
        cmd = self.writeZoneTag + zone + address + size + subCmd
        crc = self.crcx25.calcCRC16X25(cmd)
        cmd += crc[0]
        cmd += crc[1]
        receiveData = self.writeECUCommand(cmd)
        if len(receiveData) >= 4:
            if receiveData[0:4] == "7402":
                return True
            elif receiveData[0:4] == "74A0":
                self.writeToOutputView(i18n().tr("Write Configuration Zone: Failed (Incorrect Checksum)"), receiveData)

        self.writeToOutputView(i18n().tr("Write Configuration Zone: Failed"), receiveData)
        return False

    def writeKWPhabZoneConfigurationCommand(self, zone: str(), data: str()):
        writeCmd = self.writeZoneTag + zone + data
        receiveData = self.writeECUCommand(writeCmd)
        if len(receiveData) == 4 and receiveData[:2] == "7B":
            return True

        self.writeToOutputView(i18n().tr("Write Configuration Zone: Failed"), receiveData)
        return False

    def writeZoneList(self, useSketchSeed: bool, ecuID: str, lin: str, key: str, valueList: list, writeSecureTraceability: bool):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit([i18n().tr("Serial Port Not Open"), "", ""], time.time())
            return

        receiveData = self.writeECUCommand(ecuID)
        if receiveData != "OK":
            self.writeToOutputView(i18n().tr("Selecting ECU: Failed"), receiveData)
            return

        if lin != None and len(lin) > 1:
            receiveData = self.writeECUCommand(lin)
            if receiveData != "OK":
                self.writeToOutputView(i18n().tr("Selecting LIN ECU: Failed"))
                return

        time.sleep(0.5)

        if not self.startSendingKeepAlive():
            return

        if not self.startDiagnosticMode():
            return

        time.sleep(0.5)

        if len(key) > 0:
            if useSketchSeed:
                if not self.setupSketchSeedForDiagnoticMode(key):
                    self.stopDiagnosticMode()
                    return
            else:
                seed = self.unlockingServiceForConfiguration(key)
                if len(seed) == 0:
                    self.stopDiagnosticMode()
                    return

                self.writeToOutputView(i18n().tr("Waiting 2 Sec..."))
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
                readCmd = self.readZoneTag + zone[0]
                time.sleep(0.2)
                receiveData = self.writeECUCommand(readCmd)
                time.sleep(0.2)
                if self.protocol == "uds":
                    self.writeUDSZoneConfigurationCommand(zone[0], zone[1])
                elif self.protocol == "kwp_is":
                    self.writeKWPisZoneConfigurationCommand(zone[0], zone[1])
                elif self.protocol == "kwp_hab":
                    self.writeKWPhabZoneConfigurationCommand(zone[0], zone[1])
                time.sleep(0.2)
                receiveData = self.writeECUCommand(readCmd)

        if self.protocol == "uds":
            receiveData = self.writeECUCommand(self.readSecureTraceability)
            if writeSecureTraceability:
                receiveData = self.writeECUCommand(self.secureTraceability)
                if len(receiveData) != 6 or receiveData[:2] != "6E":
                    self.writeToOutputView(i18n().tr("Configuration Write of Secure Traceability Zone: Failed"), receiveData)
            else:
                self.writeToOutputView(i18n().tr("NO Secure Traceability is Written!!"))

        if not self.stopDiagnosticMode():
            return

        self.writeToOutputView(i18n().tr("Write Successful"))

    def flashEcu(self, ecuID: str, flashFile: DecodeCalUlpFile):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit([i18n().tr("Serial Port Not Open"), "", ""], time.time())
            return

        if flashFile == None:
            self.receivedPacketSignal.emit([i18n().tr("Flash File not correct"), "", ""], time.time())
            return

        receiveData = self.writeECUCommand(ecuID)
        if receiveData != "OK":
            self.writeToOutputView(i18n().tr("Selecting ECU: Failed"), receiveData)
            return

        time.sleep(0.5)

        if not self.startSendingKeepAlive():
            return

        if not self.startDownloadMode():
            return

        time.sleep(0.5)

        key = flashFile.getUnlockKey()
        flashType = flashFile.getFlashType()
        flashSize = flashFile.getFlashSize()

        seed = self.unlockingServiceForDownload(key)
        if len(seed) == 0:
            self.stopDiagnosticMode()
            return

        self.writeToOutputView(i18n().tr("Waiting 2 Sec..."))
        time.sleep(2)

        if not self.sendUnlockingResponseForDownload(seed):
            self.stopDiagnosticMode()
            return

        if not self.stopSendingKeepAlive():
            return

        if not self.__eraseEcuFlash(flashType):
            self.stopDiagnosticMode()
            return

        if not self.__prepareEcuFlash(flashType):
            self.stopDiagnosticMode()
            return

        # Start begin timer for statistics
        a = datetime.datetime.now()

        # Download/Flash SREC File
        percPre = 0
        line = ""
        while line != "END":
            data = flashFile.getFlashLines()
            line = data[0]
            if len(line) > 4:
                receiveData = self.writeECUCommand(line, False)

                if receiveData[2:4] != line[2:4]:
                    self.writeToOutputView(i18n().tr("Flash line counters do not match...") + " (" + receiveData+ ")")

                perc = int((data[1] / flashSize) * 100)
                if perc != percPre:
                    c = datetime.datetime.now()
                    percPre = perc
                    self.writeToOutputView(i18n().tr("Procent: ") + str(perc) + " - " + str(int(data[1] / (c-a).total_seconds())) + " " + i18n().tr("Lines/Sec"))
                    # TODO: Make this more elegant
                    QApplication.processEvents(QEventLoop.AllEvents, 1000)

        # Stop timer for statistics
        b = datetime.datetime.now()

        if not self.__flashAutoControl():
            self.stopDiagnosticMode()
            return
        if not self.__eraseZI():
            self.stopDiagnosticMode()
            return
        if not self.__prepareEcuFlash("83"):
            self.stopDiagnosticMode()
            return

        line = flashFile.getFlashZILine("01")  # Download counter
        receiveData = self.writeECUCommand(line)

        if not self.__flashAutoControl():
            self.stopDiagnosticMode()
            return

        if not self.stopDiagnosticMode():
            return

        self.writeToOutputView(i18n().tr("Flashing Successful in:") + " " + str(int(flashSize / (b-a).total_seconds())) + " " + i18n().tr("Lines/Sec"))


    def rebootEcu(self, ecuID: str):
        if self.serialPort.isOpen():
            self.writeToOutputView(i18n().tr("Reboot ECU..."))
            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView(i18n().tr("ECU Not selected!"))
                return

            receiveData = self.writeECUCommand(self.rebootECU)
            if len(receiveData) >= 4 and receiveData[:4] == "5103":
                return
            elif len(receiveData) >= 6 and receiveData[:6] == "71A801":
                return

            self.writeToOutputView(i18n().tr("Reboot: Failed"))

    def readEcuFaults(self, ecuID: str):
        if self.serialPort.isOpen():
            self.writeToOutputView(i18n().tr("Read ECU Faults..."))

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView(i18n().tr("ECU Not selected!"))
                return ""

            if not self.startDiagnosticMode():
                return ""

            cmdOk = False
            receiveData = self.writeECUCommand(self.readEcuFaultsMode)
            if len(receiveData) > 4:
                cmdOk = True

            if self.stopDiagnosticMode() and cmdOk:
                return receiveData

            self.writeToOutputView(i18n().tr("Reading ECU Faults: Failed"))
            return ""

    def clearEcuFaults(self, ecuID: str):
        if self.serialPort.isOpen():
            self.writeToOutputView(i18n().tr("Clearing ECU Faults..."))

            receiveData = self.writeECUCommand(ecuID)
            if receiveData != "OK":
                self.writeToOutputView(i18n().tr("ECU Not selected!"))
                return

            if not self.startDiagnosticMode():
                return

            cmdOk = False
            receiveData = self.writeECUCommand(self.clearEcuFaultsMode)
            if len(receiveData) >= 2 and receiveData[:2] == "54":
                cmdOk = True

            if self.stopDiagnosticMode() and cmdOk:
                return

            self.writeToOutputView(i18n().tr("Clearing ECU Faults: Failed"))

    def setZonesToRead(self, ecuID: str, lin: str, zoneList: dict):
        if not self.serialPort.isOpen():
            self.receivedPacketSignal.emit([i18n().tr("Serial Port Not Open"), "", ""], time.time())
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
                    self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Requested zone different from received zone"), decodedData], time.time())
                    return data

                self.receivedPacketSignal.emit([self.ecuReadZone, answer, self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, answer)
            elif decodedData[0: + 4] == "5001":
                self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Communication closed"), self.zoneName], time.time())
            elif decodedData[0: + 4] == "5002":
                self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Download session opened"), self.zoneName], time.time())
            elif decodedData[0: + 4] == "5003":
                self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Diagnostic session opened"), self.zoneName], time.time())
            elif decodedData[0: + 4] == "6702":
                self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Unlocked successfully for download"), self.zoneName], time.time())
            elif decodedData[0: + 4] == "6704":
                self.receivedPacketSignal.emit([self.ecuReadZone, i18n().tr("Unlocked successfully for configuration"), self.zoneName], time.time())
            elif decodedData[0: + 2] == "7F":
                if len(decodedData) >= 6:
                    errorResponseList = self.__openErrorResponseTranslated()
                    error = decodedData[4:6]
                    cmd = decodedData[2:4]
                    if error in errorResponseList:
                        error = "Error: (" + cmd + ") " + errorResponseList[error]
                        self.receivedPacketSignal.emit([self.ecuReadZone, error, self.zoneName], time.time())
                        self.updateZoneDataSignal.emit(self.ecuReadZone, error)
                    else:
                        self.receivedPacketSignal.emit([self.ecuReadZone, "No Response", self.zoneName], time.time())
                        self.updateZoneDataSignal.emit(self.ecuReadZone, "No Response")
                else:
                    self.receivedPacketSignal.emit([self.ecuReadZone, "No Response", self.zoneName], time.time())
                    self.updateZoneDataSignal.emit(self.ecuReadZone, "No Response")
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unknown Error", self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unknown Error")
        elif len(decodedData) <= 2:
            if decodedData[0:2] == "OK":
                self.receivedPacketSignal.emit([self.ecuReadZone, "OK", self.zoneName], time.time())
            else:
                self.receivedPacketSignal.emit([self.ecuReadZone, "Unknown Error", self.zoneName], time.time())
                self.updateZoneDataSignal.emit(self.ecuReadZone, "Unknown Error")
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
                            self.writeToOutputView(i18n().tr("Open Diagnostic session: Failed/Stopping"), receiveData)
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
                self.writeToOutputView(i18n().tr("Reading ECU Zones: Successful"))
                self.readZoneListDoneSignal.emit()
                self.isRunning = False
