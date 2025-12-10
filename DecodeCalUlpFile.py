"""
   DecodeCalUlpFile.py

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

import os, sys, json

from CalcCRC16X25 import CalcCRC16X25

class DecodeCalUlpFile():
    file = None
    fileOk = False
    fileLineNr = 0
    flashSize = 0
    flashLineNr = 1
    beginFlash = False
    flashType = ""
    unlockKey = ""
    flashSign = ""
    supplier = ""
    originalCalData = "FFFFFF"
    newCalDate = "FFFFFF"
    system = ""
    application = ""
    softVersion = ""
    softEdition = ""
    calNumber = ""
    site = "00"           # Factory ID
    signature = "020000"  # Factory ID

    def convertToHexASCIITable(self, data: str, blockSize):
        if blockSize == 0:
            return ""
        out = ""
        line = ""
        asciiStr = ""
        for i in range(0, len(data), 2):
            c = data[i:i + 2]
            s = chr(int(c,16))
            if i % (blockSize * 2) == 0:
                out += (line + "  " + asciiStr + os.linesep)
                line = ""
                asciiStr = ""
            else:
                line += " "
            line += c
            if s.isprintable():
                asciiStr += s
            else:
                asciiStr += "."

        # Add remaining
        spaces = (blockSize * 3) - len(line) - 1
        out += line + str(' ' * spaces) + "  " + asciiStr + os.linesep
        return out

    def getFlashSize(self):
        return self.flashSize

    def getFlashType(self):
        return self.flashType

    def getUnlockKey(self):
        return self.unlockKey

    def getFlashZILine(self, downloadCounter: str):
        if self.file == None or self.fileOk == False:
            return "END"

        flashLine  = self.flashSign + "0000"
        flashLine += self.supplier + self.system
        flashLine += self.originalCalData
        flashLine += self.application + self.softVersion + self.softEdition
        flashLine += self.newCalDate
        flashLine += self.site + self.signature
        flashLine += downloadCounter
        flashLine += self.calNumber
        flashLine += "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5C"

        # Calculate CRC16X25 over the data
        crcx25 = CalcCRC16X25()
        crc = crcx25.calcCRC16X25(flashLine)
        flashLine += crc[0]
        flashLine += crc[1]

        # Calculate CRC16X25 over the entire command
        flashLine = "3601" + flashLine
        crc = crcx25.calcCRC16X25(flashLine)
        flashLine += crc[0]
        flashLine += crc[1]

        return flashLine

    def getFlashLines(self):
        if self.file == None or self.fileOk == False:
            return ["END", self.fileLineNr]

        if self.beginFlash == False:
            self.beginFlash = True
            self.fileLineNr = 0
            self.file.seek(0)

        line = self.file.readline()
        if len(line) == 0:
            return ["END", self.fileLineNr]
        line = line.rstrip()
        if line[0] == 'S' and (line[1] == "2" or line[1] == "3"):
            if line[1] == "2":
                addr = line[ 4:10]
                data = line[10:-2]
            if line[1] == "3":
                addr = line[ 4:12]
                data = line[12:-2]

            flashLine = "36" + "%0.2X" % self.flashLineNr
            flashLine += addr
            flashLine += "%0.2X" % int(len(data) / 2)
            flashLine += data

            crcx25 = CalcCRC16X25()
            crc = crcx25.calcCRC16X25(flashLine)
            flashLine += crc[0]
            flashLine += crc[1]

            self.fileLineNr  += 1
            self.flashLineNr += 1
            self.flashLineNr %= 256
            return [flashLine, self.fileLineNr]

        return ["", self.fileLineNr]

    def decodeCalUlpFile(self, calFilePath: str, allData: bool):
        fileName = os.path.join(os.path.dirname(__file__), calFilePath)
        print(fileName)
        if os.path.isfile(fileName):
            self.file = open(fileName, 'r', encoding='utf-8')
            self.flashSize = 0
            self.fileLineNr = 0
            self.fileOk = True
            while line := self.file.readline():
                line = line.rstrip()
                self.fileLineNr += 1
                if len(line) < 2:
                    continue
                b = len(line) + 2
                dataLength = int(line[2:2 + 2], 16)
                size = dataLength * 2 + 4
                crc = int(line[size - 2:size], 16)
                calcCrc = 0;
                index = 2
                while index < size - 2:
                    calcCrc += int(line[index:index + 2], 16)
                    index += 2
                calcCrc = 0xFF - (calcCrc & 0xFF)
                if line[0] == 'S' and calcCrc == crc and b == size + 2:
                    match(line[1]):
                        case '0':
                            calMap = {'81': '(.cal)', '82': '(.ulp)', '92': '(.ulp new Gen)'}
                            isoMap = {'00': '(CAN)', '01': '(LIN)', '05': '(ISO 5)',  '08': '(ISO 8)'}
                            print("S0 (Hardware info) - Line: " + str(self.fileLineNr))
                            print("  FAMILY_MUX_CODE  : " + line[ 8:10])
                            print("  ISO_LINE         : " + line[10:12] + " " + isoMap[line[10:12]])
                            print("  INTERBYTE_TX     : " + line[12:14])
                            print("  INTERBYTE_RX     : " + line[14:16])
                            print("  INTER_TXRX       : " + line[16:18])
                            print("  INTER_RXTX       : " + line[18:20])
                            print("  CAL_TYPE         : " + line[20:22] + " " + calMap[line[20:22]])
                            print("  LOGICAL_MARK     : " + line[22:24])
                            print("  K_LINE_MANAGEMENT: " + line[24:26])
                            print("  CHECKSUM2        : " + line[26:28])
                            self.flashType = line[20:22]
                        case '1':
                            self.flashSign = line[ 8:12]
                            self.unlockKey = line[12:16]
                            self.supplier = line[16:18]
                            self.system = line[18:20]
                            self.application = line[20:22]
                            self.softVersion = line[22:24]
                            self.softEdition = line[24:28]
                            self.calNumber = line[28:34]

                            file = open(os.path.join(os.path.dirname(__file__), "data/ECU_SUPPLIERS.json"), 'r', encoding='utf-8')
                            jsonFile = file.read()
                            supplierList = json.loads(jsonFile.encode("utf-8"))
                            supplierTXT = "Unkown"
                            if self.supplier in supplierList:
                                supplierTXT = supplierList[str(self.supplier)]

                            print("S1 (Identification Zone - ZI) - Line: " + str(self.fileLineNr))
                            print("  ADDRESS (16-bit) : " + line[ 4: 8])
                            print("  FLASH_SIGNATURE  : " + line[ 8:12])
                            print("  UNLOCK_KEY       : " + line[12:16])
                            print("  SUPPLIER         : " + line[16:18] + " (" + supplierTXT + ")")
                            print("  SYSTEM           : " + line[18:20])
                            print("  APPLICATION      : " + line[20:22])
                            print("  SOFTWARE_VERSION : " + line[22:24])
                            print("  SOFTWARE_EDITION : " + line[24:28])
                            print("  CAL_NUMBER       : " + "96 " + line[28:34] + " 80")
                            print("  CHECKSUM2        : " + line[34:36])
                        case '2':
                            self.flashSize += 1
                            if allData == False:
                                continue
                            print("S2 (Zones data block) - Line: " + str(self.fileLineNr))
                            print("  ADDRESS   : " + line[ 4:10])
                            print("  LENGTH DAT: " + str(dataLength - 4))
                            data = line[10:-2]
                            print("  DATA      :"  + self.convertToHexASCIITable(data, 16))
                            print("  CHECKSUM2 : " + line[size - 2: size])
                        case '3':
                            self.flashSize += 1
                            if allData == False:
                                continue
                            print("S3 (Binary data block) - Line: " + str(self.fileLineNr))
                            print("  ADDRESS   : " + line[ 4:12])
                            print("  LENGTH DAT: " + str(dataLength - 4))
                            data = line[12:-2]
                            print("  DATA      :"  + self.convertToHexASCIITable(data, 16))
                            print("  CHECKSUM2 : " + line[size - 2: size])
                        case '7':
                            if allData == False:
                                continue
                            print("S7 Start Address 32-Bit (Termination) Line: " + str(self.fileLineNr))
                            if (dataLength > 1):
                                print("  ADDRESS   : "  + line[ 4:12])
                                print("  LENGTH DAT: "  + str(dataLength - 4))
                                print("  DATA      : "  + line[12: size - 2 - 12])
                                print("  CHECKSUM2 : "  + line[size - 2: size])
                        case '8':
                            if allData == False:
                                continue
                            print("S8 Start Address 24-Bit (Termination) Line: " + str(self.fileLineNr))
                            if (dataLength > 1):
                                print("  ADDRESS   : "  + line[ 4:10])
                                print("  LENGTH DAT: "  + str(dataLength - 4))
                                print("  DATA      : "  + line[10: size - 2 - 10])
                                print("  CHECKSUM2 : "  + line[size - 2: size])
                        case '9':
                            if allData == False:
                                continue
                            print("S9 Start Address 16-Bit (Termination) Line: " + str(self.fileLineNr))
                            if (dataLength > 1):
                                print("  ADDRESS   : "  + line[4:8])
                                print("  LENGTH DAT: "  + str(dataLength - 4))
                                print("  DATA      : "  + line[8: size - 2 - 8])
                                print("  CHECKSUM2 : "  + line[size - 2: size])
                if b != size + 2:
                    print("*** Incorrect size on line: " + str(self.fileLineNr))
                    self.fileOk = False
                if calcCrc != crc:
                    print("*** Checksum incorrect on line: " + str(self.fileLineNr) + " - CRC: " + "%2X" % calcCrc)
                    self.fileOk = False
                if line[0] != 'S':
                    print("*** Some other error on line: " + str(self.fileLineNr))
                    self.fileOk = False

        return self.fileOk

def printHelp():
    print("Use to show informations about S0 and S1 records:")
    print("  --path      File Path to decode")
    print("  --all       Decode/Show all data records")
    print("  --flash     Make flash file")

if __name__ == "__main__":
    filePath = ""
    allData = False
    flash = False
    if len(sys.argv) >= 2:
        foundPath = False
        for arg in sys.argv:
            if arg == "--path":
                foundPath = True
            elif foundPath:
                filePath = str(arg)
                foundPath = False
            elif arg == "--all":
                allData = True
            elif arg == "--flash":
                flash = True
            elif arg == "--help":
                printHelp()
                sys.exit(1)
    else:
        printHelp()
        sys.exit(1)

    cal = DecodeCalUlpFile()
    fileOk = cal.decodeCalUlpFile(filePath, allData)
    print("File OK: " + str(fileOk))

    if flash == True and fileOk == True:
        line = ""
        while line != "END":
            data = cal.getFlashLines()
            line = data[0]
            if len(line) > 4:
                print(line)
