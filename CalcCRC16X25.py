"""
   CalcCRC16X25.py

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

import numpy as np


class CalcCRC16X25():

    def calcCRC16X25(self, data: str()):
        if len(data) & 1:
            return [ "BE", "EF"]
        byteData = []
        for i in range(0, len(data), 2):
            byteData.append(int(data[i:i + 2], 16))
        crc = 0xFFFF
        for i in range(0, len(byteData)):
            crc ^= (byteData[i] & 0xFF) << 0;
            for i in range(0, 8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc = crc >> 1
        crc = crc ^ 0xFFFF
        return ["%0.2X" % (crc & 0xFF), "%0.2X" % ((crc >> 8) & 0xFF)]


    # Some Data to test CRC16.X25
    def __tryCRC(self, t):
        print("Try " + str(t))
        match(t):
            case 0:
                # Fails because of incorrect size
                data = "34A00000000605D8FD00000"
                dataCmp = "34A00000000605D8FD000000A83E"
            case 1:
                data = "34A00000000605D8FD000000"
                dataCmp = "34A00000000605D8FD000000A83E"
            case 2:
                data    = "34A00000000605C8FD000000"
                dataCmp = "34A00000000605C8FD000000E88A"
            case 3:
                data    = "34A00000000605D800000000"
                dataCmp = "34A00000000605D8000000000CC2"
            case 4:
                data    = "34A00000000605FBFD000000"
                dataCmp = "34A00000000605FBFD000000F543"

        crc = self.calcCRC16X25(data)
        data += crc[0]
        data += crc[1]
        print("  " + data);
        print("  " + dataCmp);
        if data != dataCmp:
            print("    ** Failed CRC16.X25 **")

    def testCrc(self):
        self.__tryCRC(0)
        self.__tryCRC(1)
        self.__tryCRC(2)
        self.__tryCRC(3)
        self.__tryCRC(4)


