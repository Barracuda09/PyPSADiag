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

import json
import os
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QLineEdit


class EcuZoneLineEdit(QLineEdit):
    """
    """
    zoneObject = {}
    valueType = ""
    initialValue = ""
    initialRaw = ""
    itemReadOnly = False
    def __init__(self, parent, zoneObject: dict, readOnly: bool):
        super(EcuZoneLineEdit, self).__init__(parent)
        self.itemReadOnly = readOnly
        self.setReadOnly(readOnly)
        self.zoneObject = zoneObject

    def event(self, event: QEvent):
        if event.type() == QEvent.KeyPress:
            keyEvent = QKeyEvent(event)
            # When ESC -> Clear focus
            if keyEvent.key() == Qt.Key_Escape:
                # @TODO: Maybe give option to undo changes?
                self.clearFocus()
                return True
        return super().event(event)

    def getDescriptionName(self):
        return self.zoneObject["name"]

    def getCorrespondingByte(self):
        return self.zoneObject["byte"]

    def getCorrespondingByteSize(self):
        if "mask" in self.zoneObject:
            bits = int(self.zoneObject["mask"], 2).bit_count()
            if bits > 8 and bits <= 16:
                return 2
            elif bits > 16 and bits <= 32:
                return 4
        return 1

    def __setText(self, val):
        self.initialValue = val;
        super().setText(val)

    def updateText(self, val):
        super().setText(val)

    def isLineEditChanged(self, virginWrite: bool()):
        return self.isEnabled() and not(self.itemReadOnly) and (self.initialValue != self.text() or virginWrite)

    def __convertZoneData(self):
        if self.valueType == "string_ascii":
            value = self.text().encode().hex()
        elif self.valueType == "string_date":
            value = self.initialRaw
        elif self.valueType == "int":
            value = "%0.2X" % int(self.text())
        else:
            value = self.text()

        return value.upper()

    def getValuesAsCSV(self):
        if self.isEnabled():
            return self.__convertZoneData()

        return "Disabled"

    def clearZoneValue(self):
        valueType = ""
        initialValue = ""
        initialRaw = ""
        self.clear()

    def getZoneAndHex(self, virginWrite: bool()):
        value = "None"
        if self.isLineEditChanged(virginWrite):
            return self.__convertZoneData()

        return "None"

    def __shift(self, mask: int):
        # Code snippet by Sean Eron Anderson
        v = mask
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
                size = self.getCorrespondingByteSize() * 2
                newByte = int(text) << self.__shift(mask)
                value = (int(byte, 16) & ~mask) | newByte
                byte = f"%0.{size}X" % value
        return byte

    def __convertStringToDate(self, data: str):
        self.initialDate = data
        day   = int(data[0:2], 16)
        month = int(data[2:4], 16)
        year  = int(data[4:6], 16)
        # Check if date is not sane, then give ASCII
        if year >= 30 or day > 31 or month > 12:
            day   = data[0:2]
            month = data[2:4]
            year  = data[4:6]
        else:
            day   = ("%0.2d" % int(data[0:2], 16))
            month = ("%0.2d" % int(data[2:4], 16))
            year  = ("%0.2d" % int(data[4:6], 16))
        txt = day + "." + month + "." + year
        return txt

    def changeZoneOption(self, data: str, valueType: str):
        self.valueType = valueType
        self.initialRaw = data
        if "mask" in self.zoneObject:
            byteData = []
            for i in range(0, len(data), 2):
                byteData.append(data[i:i + 2])

            # Is this option used for this Zone (NAC/RCC JSON Files)
            zoneLength = len(byteData)
            if "zoneLength" in self.zoneObject:
                zoneLength = self.zoneObject["zoneLength"]
                if zoneLength > len(byteData):
                    return 2

            byteNr = self.zoneObject["byte"]
            mask = int(self.zoneObject["mask"], 2)
            size = self.getCorrespondingByteSize()

            # Integrity wrong, size does not match
            if (byteNr + size) > len(byteData):
                return 1

            currByteData = byteData[byteNr : byteNr + size]
            currData = ""
            for i in range(len(currByteData)):
                currData += currByteData[i]

            byte = (int(currData, 16) & mask) >> self.__shift(mask)
            self.__setText(str(byte))

        elif "byte_range" in self.zoneObject:
            byteNr = self.zoneObject["byte"] * 2
            ran = self.zoneObject["byte_range"] * 2
            txt = data[byteNr:byteNr + ran]
            if "type" in self.zoneObject:
                if "zi_cal" == self.zoneObject["type"]:
                    txt = "96" + txt + "80"
                elif "zi_sup" == self.zoneObject["type"]:
                    file = open(os.path.join(os.path.dirname(__file__), "data/ECU_SUPPLIERS.json"), 'r', encoding='utf-8')
                    jsonFile = file.read()
                    supplierList = json.loads(jsonFile.encode("utf-8"))
                    if txt in supplierList:
                        txt = supplierList[str(txt)]
                elif "zi_sys" == self.zoneObject["type"]:
                    txt = txt
                elif "string_date" == self.zoneObject["type"]:
                    txt = self.__convertStringToDate(txt)
            self.__setText(txt)
        else:
            if valueType == "string_ascii":
                try:
                    txt = bytes.fromhex(data).decode("utf-8")
                except:
                    valueType = "string"
                    txt = data
            elif valueType == "string_date":
                txt = self.__convertStringToDate(data)
            elif valueType == "mileage":
                txt = str(int(data, 16) / 10)
            elif valueType == "int":
                txt = str(int(data, 16))
            else:
                txt = data

            self.__setText(txt)

        return 0
