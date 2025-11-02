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

import os, sys


class DecodeCalUlpFile():

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

    def DecodeCalUlpFile(self, calFilePath: str, allData: bool):
        fileName = os.path.join(os.path.dirname(__file__), calFilePath)
        print(fileName)
        if os.path.isfile(fileName):
            file = open(fileName, 'r', encoding='utf-8')
            calFile = file.read()
            terminator = "\r\n"
            if calFile.find(terminator) == -1:
                terminator = "\n"
                if calFile.find(terminator) == -1:
                    print("Unkown Line-Terminator")
                    return
            regNr = 0
            for line in calFile.split(terminator):
                regNr += 1
                if len(line) < 2:
                    continue
                n = len(line)
                b = n + 2
                dataLength = int(line[2:2 + 2], 16)
                size = dataLength * 2 + 4
                crc = int(line[size - 2:size], 16)
                calcCrc = 0;
                index = 2
                while index < size - 2:
                    calcCrc += int(line[index:index + 2], 16)
                    index += 2
                calcCrc = 0xFF - (calcCrc & 0xFF)

                if line[0] == 'S' and calcCrc == crc:
                    match(line[1]):
                        case '0':
                            print("S0 (Hardware info) - Line: " + str(regNr))
                            print("  FAMILY_MUX_CODE  : " + line[ 8:10])
                            print("  ISO_LINE         : " + line[10:12])
                            print("  INTERBYTE_TX     : " + line[12:14])
                            print("  INTERBYTE_RX     : " + line[14:16])
                            print("  INTER_TXRX       : " + line[16:18])
                            print("  INTER_RXTX       : " + line[18:20])
                            print("  CAL_TYPE         : " + line[20:22])
                            print("  LOGICAL_MARK     : " + line[22:24])
                            print("  K_LINE_MANAGEMENT: " + line[24:26])
                            print("  CHECKSUM2        : " + line[26:28])
                        case '1':
                            print("S1 (Identification Zone - ZI) - Line: " + str(regNr))
                            print("  FLASH_SIGNATURE  : " + line[ 8:12])
                            print("  UNLOCK_KEY       : " + line[12:16])
                            print("  SUPPLIER         : " + line[16:18])
                            print("  SYSTEM           : " + line[18:20])
                            print("  APPLICATION      : " + line[20:22])
                            print("  SOFTWARE_VERSION : " + line[22:24])
                            print("  SOFTWARE_EDITION : " + line[24:28])
                            print("  CAL_NUMBER       : " + "96 " + line[28:34] + " 80")
                            print("  CHECKSUM2        : " + line[34:36])
                        case '2':
                            if allData == False:
                                return
                            print("S2 (Zones data block) - Line: " + str(regNr))
                            print("  ADDRESS   : " + line[ 4:10])
                            print("  LENGTH DAT: " + str(dataLength - 4))
                            data = line[10:-2]
                            print("  DATA      :"  + self.convertToHexASCIITable(data, 16))
                            print("  CHECKSUM2 : " + line[size - 2: size])
                        case '3':
                            if allData == False:
                                return
                            print("S3 (Binary data block) - Line: " + str(regNr))
                            print("  ADDRESS   : " + line[ 4:12])
                            print("  LENGTH DAT: " + str(dataLength - 4))
                            data = line[12:-2]
                            print("  DATA      :"  + self.convertToHexASCIITable(data, 16))
                            print("  CHECKSUM2 : " + line[size - 2: size])
                        case '8':
                            if allData == False:
                                return
                            print("S8 Start Address (Termination) Line: " + str(regNr))
                            if (dataLength > 1):
                                print("  ADDRESS   : "  + line[ 4:10])
                                print("  LENGTH DAT: "  + str(dataLength - 4))
                                print("  DATA      : "  + line[10: size - 2 - 10])
                                print("  CHECKSUM2 : "  + line[size - 2: size])
                else:
                    print("Checksum incorrect")

def printHelp():
    print("Use:")
    print("  --path      File Path to decode")
    print("  --all       Decode/Show all data")

if __name__ == "__main__":
    filePath = ""
    allData = False
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
            elif arg == "--help":
                printHelp()
                sys.exit(1)
    else:
        printHelp()
        sys.exit(1)

    cal = DecodeCalUlpFile()
    cal.DecodeCalUlpFile(filePath, allData)
