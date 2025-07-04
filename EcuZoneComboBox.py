"""
   EcuZoneComboBox.py

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

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QComboBox

from i18n import i18n

class EcuZoneComboBox(QComboBox):
    """
    """
    value = 0
    zoneObject = {}
    itemReadOnly = False
    def __init__(self, parent, zoneObject: dict, readOnly: bool):
        super(EcuZoneComboBox, self).__init__(parent)
        self.setStyleSheet("combobox-popup: 3;")
        self.setFocusPolicy(Qt.StrongFocus)
        self.itemReadOnly = readOnly
        self.zoneObject = zoneObject
        # Fill Combo Box
        for paramObject in self.zoneObject["params"]:
            name = i18n().tr(paramObject["name"])
            if "mask" in paramObject:
                self.addItem(name, int(paramObject["mask"], 2))
            else:
                self.addItem(name, int(paramObject["value"], 16))
        self.setCurrentIndex(0)

    def event(self, event: QEvent):
        if event.type() == QEvent.KeyPress:
            keyEvent = QKeyEvent(event)
            # When ESC -> Clear focus
            if keyEvent.key() == Qt.Key_Escape:
                # @TODO: Maybe give option to undo changes?
                self.clearFocus()
                return True
        return super().event(event)

    # Prevent scrolling without focus
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e);

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

    def setCurrentIndex(self, val):
        self.value = val;
        super().setCurrentIndex(val)

    def isComboBoxChanged(self, virginWrite: bool()):
        return self.isEnabled() and not(self.itemReadOnly) and self.value != self.currentIndex()

    def getValuesAsCSV(self):
        value = "Disabled"
        if self.isEnabled():
            index = self.currentIndex()
            value = "%0.2X" % self.itemData(index)
        return value

    def clearZoneValue(self):
        value = 0
        self.setCurrentIndex(0)

    def getZoneAndHex(self, virginWrite: bool()):
        value = "None"
        if self.isComboBoxChanged(virginWrite):
            index = self.currentIndex()
            value = "%0.2X" % self.itemData(index)
        return value

    def update(self, byte: str):
        index = self.currentIndex()
        mask = int(self.zoneObject["mask"], 2)
        value = (int(byte, 16) & ~mask) | self.itemData(index)
        size = self.getCorrespondingByteSize() * 2
        byte = f"%0.{size}X" % value
        return byte

    def changeZoneOption(self, data: str, valueType: str):
        byte = int(data, 16)
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

            byte = int(currData, 16) & mask
        else:
            print(" No mask")
            print("  Obj   : " + str(self.zoneObject))

        # Find the Option (byte) from the ComboBox
        foundMatch = False
        for i in range(self.count()):
            if self.itemData(i) == byte:
                self.setCurrentIndex(i)
                foundMatch = True
                break

        # Did we find item, else add it to combobox
        if foundMatch == False:
            print("** Add missing combobox item " + "0x%0.2X" % byte + " **")
            self.addItem("** 0x%0.2X" % byte, int(byte))
            self.setCurrentIndex(self.count() - 1)

        return 0
