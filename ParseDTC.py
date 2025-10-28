"""
   ParseDTC.py

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

import json, os

from i18n import i18n
from SpreadsheetDialog  import SpreadsheetDialog

class ParseDTC():

    def __init__(self):
        self.isRunning = True

    @classmethod
    def __openDTCFileTranslated(cls, dtcFilePath: str):
        fileName = os.path.join(os.path.dirname(__file__), dtcFilePath)
        dtcDict = {}
        if os.path.isfile(fileName):
            file = open(fileName, 'r', encoding='utf-8')
            jsonFile = file.read()
            responseList = json.loads(jsonFile.encode("utf-8"))
            # Build translated Dictionary
            for response in responseList:
                dtcDict[response] = i18n().tr(responseList[str(response)]["name"])
        return dtcDict

    @classmethod
    def parse(cls, dtc: str, dtcFilePath: str):
        letterMap = {0: 'P', 1: 'C', 2: 'B', 3: 'U'}
        fileName = os.path.join(os.path.dirname(__file__), "data/DTCFailureType.json")
        dtcFailureTypes = cls.__openDTCFileTranslated(fileName);
        dtcExplanations = cls.__openDTCFileTranslated(dtcFilePath);
        dtcList = []
        if dtc[:4] == "5902":
            index = 6
            while index + 8 <= len(dtc):
                H = int(dtc[index:index+2], 16)
                index += 2
                M = dtc[index:index+2]
                index += 2
                faultTypeByte = dtc[index:index+2]
                index += 2
                status = int(dtc[index:index+2], 16)
                index += 2
    
                letter = letterMap[(H >> 6) & 0x3]
                firstDigit = "%.1X" % ((H >> 4) & 0x3)
                secondDigit = "%.1X" % (H & 0xF)
                lowerDigit = M
                dtcNumberStr = letter + firstDigit + secondDigit + lowerDigit
                dtcExpl = dtcExplanations.get(dtcNumberStr, i18n().tr("Unknown"))
                faultTypeStr = dtcFailureTypes.get(faultTypeByte, i18n().tr("Unknown"))
                dtcStatusStr = ""
                if status & 0x01:
                    dtcStatusStr += i18n().tr("(Test Failed)")
                if status & 0x02:
                    dtcStatusStr += i18n().tr("(Test Failed This Operation Cycle)")
                if status & 0x04:
                    dtcStatusStr += i18n().tr("(Pending DTC)")
                if status & 0x08:
                    dtcStatusStr += i18n().tr("(Confirmed DTC)")
                if status & 0x10:
                    dtcStatusStr += i18n().tr("(Test Not Completed Since last Clear)")
                if status & 0x20:
                    dtcStatusStr += i18n().tr("(Test Failed Since last Clear)")
                if status & 0x40:
                    dtcStatusStr += i18n().tr("(Test Not Completed This OP Cycle)")
                if status & 0x80:
                    dtcStatusStr += i18n().tr("(Warning Indicator Requested)")

                dtcList.append([dtcNumberStr, faultTypeStr, dtcExpl, dtcStatusStr])

        dtcdialog = SpreadsheetDialog(None, i18n().tr("DTC"), dtcList, [i18n().tr("Code"), i18n().tr("Fault"), i18n().tr("Explanation"), i18n().tr("Status")])
        dtcdialog.exec()
