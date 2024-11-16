"""
   EcuZoneLineEdit.py

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

from PySide6.QtWidgets import QLineEdit


class EcuZoneLineEdit(QLineEdit):
    """
    """
    initialValue = ""
    zoneObject = dict
    valueType = ""
    def __init__(self, parent, zoneObject: dict, readOnly: bool):
        super(EcuZoneLineEdit, self).__init__(parent)
        self.setReadOnly(readOnly)
        self.zoneObject = zoneObject

    def getCorrespondingByte(self):
        return self.zoneObject["byte"]

    def __setText(self, val):
        self.initialValue = val;
        super().setText(val)

    def updateText(self, val):
        super().setText(val)

    def isLineEditChanged(self):
        return self.isEnabled() and self.initialValue != self.text()

    def getZoneAndHex(self):
        value = "None"
        if self.isLineEditChanged():
            if self.valueType == "string_ascii":
                value = self.text().encode().hex()
            elif self.valueType == "int":
                value = "%0.2X" % int(self.text())
            else:
                value = self.text()
        return value

    def __shift(self):
        # Code snippet by Sean Eron Anderson
        v = int(self.zoneObject["mask"], 2)
        c = 32
        v &= -v
        if v:
            c -= 1
        if v & 0x0000FFFF:
            c -= 16
        if v & 0x00FF00FF:
            c -= 8
        if v & 0x0F0F0F0F:
            c -= 4
        if v & 0x33333333:
            c -= 2
        if v & 0x55555555:
            c -= 1
        return c

    def update(self, byte: str):
        if "mask" in self.zoneObject:
            text = self.text()
            mask = int(self.zoneObject["mask"], 2)
            if text != None and text != "":
                newByte = int(text) << self.__shift()
                value = (int(byte, 16) & ~mask) | newByte
                byte = "%0.2X" % value
        return byte

    def changeZoneOption(self, data: str, valueType: str):
        self.valueType = valueType
        if "mask" in self.zoneObject:
            byteData = []
            for i in range(0, len(data), 2):
                byteData.append(data[i:i + 2])

            byteNr = self.zoneObject["byte"]
            mask = int(self.zoneObject["mask"], 2)
            byte = (int(byteData[byteNr], 16) & mask) >> self.__shift()
            self.__setText(str(byte))
        else:
            if valueType == "string_ascii":
                txt = data
                try:
                    txt = bytes.fromhex(data).decode("utf-8")
                except:
                    valueType = "string"
                self.__setText(txt)
            elif valueType == "string_date":
                txt = ("%0.2d" % int(data[0:2], 16)) + "." + ("%0.2d" % int(data[2:4], 16)) + "." + ("%0.2d" % int(data[4:6], 16))
                self.__setText(txt)
            elif valueType == "int":
                txt = str(int(data, 16))
                self.__setText(txt)
            else:
                self.__setText(data)

