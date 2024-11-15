"""
   EcuZoneCheckBox.py

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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox


class EcuZoneCheckBox(QCheckBox):
    """
    """
    initialValue = 0
    zoneObject = dict
    def __init__(self, parent, zoneObject: dict):
        super(EcuZoneCheckBox, self).__init__(parent)
        self.zoneObject = zoneObject

    def getCorrespondingByte(self):
        return self.zoneObject["byte"]

    def setCheckState(self, val):
        self.initialValue = val;
        super().setCheckState(val)

    def isCheckBoxChanged(self):
        return self.isEnabled() and self.initialValue != 0 and self.initialValue != self.checkState()

    def getZoneAndHex(self):
        value = "None"
        if "mask" in self.zoneObject:
            print("EcuZoneCheckBox.getZoneAndHex(..) has mask?")
        else:
            if self.isCheckBoxChanged():
                if self.checkState() == Qt.Checked:
                    value = "01"
                else:
                    value = "00"
        return value

    def update(self, byte: str):
        mask = int(self.zoneObject["mask"], 2)
        if "available_logic" in self.zoneObject and "active_high" == self.zoneObject["available_logic"]:
            if self.isChecked():
                value = (int(byte, 16) | mask)
                byte = "%0.2X" % value
            else:
                value = (int(byte, 16) & ~mask)
                byte = "%0.2X" % value
        else:
            if self.isChecked():
                value = (int(byte, 16) & ~mask)
                byte = "%0.2X" % value
            else:
                value = (int(byte, 16) | mask)
                byte = "%0.2X" % value

        return byte

    def changeZoneOption(self, data: str, valueType: str):
        if "mask" in self.zoneObject:
            byteData = []
            for i in range(0, len(data), 2):
                byteData.append(data[i:i + 2])

            byteNr = self.zoneObject["byte"]
            mask = int(self.zoneObject["mask"], 2)
            byte = int(byteData[byteNr], 16) & mask
            if "available_logic" in self.zoneObject and "active_high" == self.zoneObject["available_logic"]:
                if byte > 0:
                    self.setCheckState(Qt.Checked)
                else:
                    self.setCheckState(Qt.Unchecked)
            else:
                if byte > 0:
                    self.setCheckState(Qt.Unchecked)
                else:
                    self.setCheckState(Qt.Checked)
        else:
            if data == "01":
                self.setCheckState(Qt.Checked)
            elif data == "00":
                self.setCheckState(Qt.Unchecked)

