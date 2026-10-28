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
from PySide6.QtGui import QKeyEvent, QRegularExpressionValidator, QIntValidator, QDoubleValidator
from PySide6.QtCore import Qt, QEvent, Slot, QRegularExpression, QLocale
from PySide6.QtWidgets import QLineEdit


class EcuZoneLineEdit(QLineEdit):
    """
    """
    zoneObject = {}
    valueType = ""
    initialLineValue = ""
    newLineLineValue = ""
    initialRaw = ""
    style = ""
    itemReadOnly = False
    def __init__(self, parent, zoneObject: dict, readOnly: bool):
        super(EcuZoneLineEdit, self).__init__(parent)
        self.itemReadOnly = readOnly
        self.setReadOnly(readOnly)
        self.zoneObject = zoneObject
        self.rangeToolTip = ""
        self.signed = zoneObject.get("signed", False)
        if not isinstance(self.signed, bool):
            raise ValueError("signed must be a boolean")
        if self.signed:
            if "mask" not in zoneObject:
                raise ValueError("Signed fields require a contiguous binary mask")
            mask = int(zoneObject["mask"], 2)
            if mask <= 0 or mask.bit_length() > 32:
                raise ValueError("Signed masks must fit in 1..32 bits")
            self.signedShift = self.__shift(mask)
            fieldMask = mask >> self.signedShift
            if fieldMask & (fieldMask + 1):
                raise ValueError("Signed fields require a contiguous binary mask")
            self.signedBits = fieldMask.bit_length()
            limit = 1 << (self.signedBits - 1)
            validator = QIntValidator(-limit, limit - 1, self)
            locale = QLocale.c()
            locale.setNumberOptions(QLocale.RejectGroupSeparator)
            validator.setLocale(locale)
            self.setValidator(validator)
            self.rangeToolTip = ("Signed %d-bit integer, %d to %d" %
                                 (self.signedBits, -limit, limit - 1))
            self.setToolTip(self.rangeToolTip)
        self.asciiByteRange = (zoneObject.get("type") == "string_ascii"
                               and "byte_range" in zoneObject and "mask" not in zoneObject)
        if self.asciiByteRange:
            size = zoneObject["byte_range"]
            if not isinstance(size, int) or size <= 0:
                raise ValueError("ASCII byte_range must be a positive integer")
            padding = zoneObject.get("padding_byte", "00")
            if not isinstance(padding, str) or len(padding) != 2:
                raise ValueError("padding_byte must be a two-digit hexadecimal byte")
            self.paddingByte = bytes.fromhex(padding)
            if len(self.paddingByte) != 1:
                raise ValueError("padding_byte must be a two-digit hexadecimal byte")
            expression = QRegularExpression(r"[\x00-\x7F]{0,%d}" % size)
            self.setValidator(QRegularExpressionValidator(expression, self))
            self.setToolTip("ASCII text, maximum %d bytes" % size)

        # Optional affine scaling for masked numeric fields:
        #   displayed = offset + code * scale        (code = (word & mask) >> shift)
        #   code      = round((displayed - offset) / scale)
        # Lets a field show a physical value (km, mpg, ...) instead of the raw code.
        # Fields without "scale" are unaffected (behaviour identical to before).
        self.scale = zoneObject.get("scale", None)
        self.offset = zoneObject.get("offset", 0)
        self.decimals = zoneObject.get("decimals", None)
        if self.scale is not None:
            if self.signed:
                raise ValueError("scale cannot be combined with signed")
            if "mask" not in zoneObject:
                raise ValueError("scale requires a mask")
            if not isinstance(self.scale, (int, float)) or self.scale == 0:
                raise ValueError("scale must be a non-zero number")
            if not isinstance(self.offset, (int, float)):
                raise ValueError("offset must be a number")
            if self.decimals is not None and (not isinstance(self.decimals, int) or self.decimals < 0):
                raise ValueError("decimals must be a non-negative integer")
            smask = int(zoneObject["mask"], 2)
            maxCode = smask >> self.__shift(smask)
            rawLo = self.offset + 0 * self.scale
            rawHi = self.offset + maxCode * self.scale
            lo = zoneObject.get("min", min(rawLo, rawHi))
            hi = zoneObject.get("max", max(rawLo, rawHi))
            dec = self.decimals if self.decimals is not None else 3
            validator = QDoubleValidator(float(min(lo, hi)), float(max(lo, hi)), dec, self)
            # Standard (not scientific) notation, so e.g. "22" stays "22" and is
            # never reformatted to "2e+01".
            validator.setNotation(QDoubleValidator.StandardNotation)
            locale = QLocale.c()
            locale.setNumberOptions(QLocale.RejectGroupSeparator)
            validator.setLocale(locale)
            self.setValidator(validator)
            self.rangeToolTip = ("Enter a value between %s and %s" % (min(lo, hi), max(lo, hi)))
            self.setToolTip(self.rangeToolTip)

        # Notify changes, to change color if changed
        self.textEdited.connect(self.textChange)

        # Save current style-sheet
        self.style = self.styleSheet()

    @Slot()
    def textChange(self, text):
        if text != self.newLineLineValue:
            self.newLineLineValue = text

        # Out-of-range / invalid input: flag it red with a tooltip instead of
        # silently mangling (e.g. "2e+01") or accepting it.
        if self.validator() is not None and not self.hasAcceptableInput():
            self.setStyleSheet("background-color: rgb(200, 60, 60)")
            if self.rangeToolTip:
                self.setToolTip("Value out of range. " + self.rangeToolTip)
            else:
                self.setToolTip("Value out of range")
            return

        if self.rangeToolTip:
            self.setToolTip(self.rangeToolTip)
        if self.newLineLineValue == self.initialLineValue:
            self.setStyleSheet(self.style)
        else:
            self.setStyleSheet("background-color: rgb(42, 130, 218)")

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
        if self.asciiByteRange:
            return self.zoneObject["byte_range"]
        if "mask" in self.zoneObject:
            bits = int(self.zoneObject["mask"], 2).bit_length()
            # round up to the nearest bit
            return (bits + 7) // 8
        return 1

    def __setText(self, val):
        self.initialLineValue = val;
        super().setText(val)

    def updateText(self, val):
        super().setText(val)

    def isLineEditChanged(self, virginWrite: bool):
        return self.isEnabled() and not(self.itemReadOnly) and (self.initialLineValue != self.text() or virginWrite)

    def __convertZoneData(self):
        if self.signed:
            start = self.getCorrespondingByte() * 2
            size = self.getCorrespondingByteSize() * 2
            return self.update(self.initialRaw[start:start + size]).upper()
        elif self.asciiByteRange:
            return self.update(self.initialRaw).upper()
        elif self.valueType == "string_ascii":
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
            if self.signed and not self.hasAcceptableInput():
                return "None"
            return self.__convertZoneData()

        return "Disabled"

    def clearZoneValue(self):
        self.initialLineValue = ""
        self.valueType = ""
        self.initialRaw = ""
        self.clear()

    def getZoneAndHex(self, virginWrite: bool):
        value = "None"
        if self.hasAcceptableInput() and self.isLineEditChanged(virginWrite):
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
        if self.asciiByteRange:
            if not self.hasAcceptableInput():
                return byte
            if self.text() == self.initialLineValue:
                return self.initialRaw
            data = self.text().encode("ascii")
            return data.ljust(self.getCorrespondingByteSize(), self.paddingByte).hex().upper()
        if "mask" in self.zoneObject:
            text = self.text()
            mask = int(self.zoneObject["mask"], 2)
            if self.signed:
                if not self.hasAcceptableInput():
                    return byte
                word = int(text) & ((1 << self.signedBits) - 1)
                newByte = (word << self.signedShift) & mask
                value = (int(byte, 16) & ~mask) | newByte
                return "%0.*X" % (self.getCorrespondingByteSize() * 2, value)
            if text != None and text != "":
                size = self.getCorrespondingByteSize() * 2
                shift = self.__shift(mask)
                if self.scale is not None:
                    # Don't write an out-of-range / invalid value; leave the byte as-is.
                    if not self.hasAcceptableInput():
                        return byte
                    code = int(round((float(text) - self.offset) / self.scale))
                    # keep within the field so a write never spills into neighbouring bits
                    maxCode = mask >> shift
                    code = max(0, min(code, maxCode))
                    newByte = (code << shift) & mask
                else:
                    newByte = int(text) << shift
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
            if "zoneLength" in self.zoneObject:
                zoneLength = self.zoneObject["zoneLength"]
                if isinstance(zoneLength, list):
                    if len(byteData) not in zoneLength:
                        return 2
                else:
                    if zoneLength != len(byteData):
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
            if self.signed and byte & (1 << (self.signedBits - 1)):
                byte -= 1 << self.signedBits
            if self.scale is not None:
                value = self.offset + byte * self.scale
                if self.decimals is not None:
                    self.__setText("%.*f" % (self.decimals, value))
                else:
                    self.__setText(str(value))
            elif "type" in self.zoneObject and self.zoneObject["type"] == "mileage":
                self.__setText(str(byte / 10))
            else:
                self.__setText(str(byte))

        elif "byte_range" in self.zoneObject:
            byteNr = self.zoneObject["byte"] * 2
            ran = self.zoneObject["byte_range"] * 2
            txt = data[byteNr:byteNr + ran]
            if self.asciiByteRange:
                if len(txt) != ran:
                    return 1
                try:
                    raw = bytes.fromhex(txt)
                    # Keep legacy display trimming when padding is unspecified.
                    padding = self.paddingByte if "padding_byte" in self.zoneObject else b"\x00 "
                    decoded = raw.rstrip(padding).decode("ascii")
                except ValueError:
                    return 1
                self.initialRaw = txt
                self.valueType = "string_ascii"
                self.__setText(decoded)
                return 0
            if "type" in self.zoneObject:
                if "zi_cal" == self.zoneObject["type"]:
                    txt = "96" + txt + "80"
                elif "zi_tool" == self.zoneObject["type"]:
                    file = open(os.path.join(os.path.dirname(__file__), "data/ToolType.json"), 'r', encoding='utf-8')
                    jsonFile = file.read()
                    tooltypeList = json.loads(jsonFile.encode("utf-8"))
                    if txt in tooltypeList:
                        txt = tooltypeList[str(txt)]
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
                elif "string_ascii" == self.zoneObject["type"]:
                    try:
                        txt = bytes.fromhex(txt).decode("utf-8", errors="ignore").rstrip("\x00 ")
                    except:
                        pass   # not decodable -> leave as hex
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
