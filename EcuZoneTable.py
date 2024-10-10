"""
   EcuZoneTable.py

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

import random
import json
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QCheckBox, QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, QLineEdit, QSizePolicy
from PySide6.QtGui import QColor


class EcuZoneTableView(QTabWidget):
    """
    """
    def __init__(self, parent, ecuObjectList = None):
        super(EcuZoneTableView, self).__init__(parent)
        self.updateView(ecuObjectList)

    def updateView(self, ecuObjectList):
        if ecuObjectList != None:
            self.zoneObjectList = ecuObjectList["zones"]
            self.clear()
            self.tabs = []
            for tabs in ecuObjectList["tabs"]:
                name = ecuObjectList["tabs"][tabs]
                index = self.addTab(EcuZoneTableWidget(self, self.zoneObjectList, tabs), str(name))
                self.tabs.append([tabs, index])

    def getValuesAsCSV(self):
        for tab in self.tabs:
            widget = self.widget(tab[1])
            print(tab[1])
            widget.getValuesAsCSV()

    def getZoneListOfHexValue(self):
        value = []
        for tab in self.tabs:
            widget = self.widget(tab[1])
            value.append(widget.getZoneListOfHexValue())
        return value

    def getZoneAndHexValueOfCurrentRow(self):
        widget = self.currentWidget()
        return widget.getZoneAndHexValueOfCurrentRow()

    def changeZoneOption(self, zone, data: str, valueType: str):
        for zoneIDObject in self.zoneObjectList:
            if str(zone) == str(zoneIDObject):
                zoneObject = self.zoneObjectList[zone]
                tabName = zoneObject["tab"]
                for tab in self.tabs:
                    if tab[0] == tabName:
                        widget = self.widget(tab[1])
                        widget.changeZoneOption(zone, data, valueType)

class EcuZoneLineEdit(QLineEdit):
    """
    """
    value = 0
    def __init__(self, parent):
        super(EcuZoneLineEdit, self).__init__(parent)

    def setText(self, val):
        self.value = val;
        super().setText(val)

    def isLineEditChanged(self):
        return self.isEnabled() and self.value != self.text()

class EcuZoneCheckBox(QCheckBox):
    """
    """
    value = 0
    def __init__(self, parent):
        super(EcuZoneCheckBox, self).__init__(parent)

    def setCheckState(self, val):
        self.value = val;
        super().setCheckState(val)

    def isCheckBoxChanged(self):
        return self.isEnabled() and self.value != self.checkState()

class EcuZoneComboBox(QComboBox):
    """
    """
    value = 0
    def __init__(self, parent):
        super(EcuZoneComboBox, self).__init__(parent)

    def setCurrentIndex(self, val):
        self.value = val;
        super().setCurrentIndex(val)

    def isComboBoxChanged(self):
        return self.isEnabled() and self.value != self.currentIndex()


class EcuZoneTableWidget(QTableWidget):
    """
    """
    def __init__(self, parent, zoneObjectList, tabName: str):
        super(EcuZoneTableWidget, self).__init__(parent)
        rowCount = 0
        # Get how many rows there are in this tab
        for zoneIDObject in zoneObjectList:
            self.zoneObject = zoneObjectList[str(zoneIDObject)]
            if self.zoneObject["tab"] == tabName:
                rowCount += 1
        self.setRowCount(rowCount)
        rowCount = 0
        self.setColumnCount(3)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.horizontalHeader().sectionResized.connect(self.resizeRowsToContents)
        self.setShowGrid(True)
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.setHorizontalHeaderLabels(["Zone", "Zone Description", "Options"])
        self.setObjectName(u"tableView")
        self.setWordWrap(True)
        for zoneIDObject in zoneObjectList:
            zoneObject = zoneObjectList[str(zoneIDObject)]
            if zoneObject["tab"] != tabName:
                continue
            formType = zoneObject["form_type"]
            item1 = QTableWidgetItem(str(zoneIDObject))
            item2 = QTableWidgetItem(zoneObject["name"])
            item3 = None
            if formType == "combobox":
                item3 = EcuZoneComboBox(self)
                item3.setStyleSheet("combobox-popup: 3;")
                for paramObject in zoneObject["params"]:
                    item3.addItem(paramObject["name"], int(paramObject["value"], 16))

                item3.setCurrentIndex(0)
            elif formType == "checkbox":
                item3 = EcuZoneCheckBox(self)
            elif formType == "string":
                item3 = EcuZoneLineEdit(self)

            self.setItem(rowCount, 0, item1)
            self.setItem(rowCount, 1, item2)
            self.setCellWidget(rowCount, 2, item3)
            rowCount += 1

        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 500)
        self.setColumnWidth(2, 280)

    def markItemNoResponse(self, row):
        cellItem = self.cellWidget(row, 2)
        cellItem.setDisabled(True);
        self.item(row, 0).setBackground(QColor(255, 128, 128))
        self.item(row, 1).setBackground(QColor(255, 128, 128))

    def markItemValueOutOfRange(self, row):
        self.item(row, 0).setBackground(QColor(255, 128, 0))
        self.item(row, 1).setBackground(QColor(255, 128, 0))

    def getValuesAsCSV(self):
        print(self.item(0,0).text())
        print(self.item(0,1).text())

    def getZoneListOfHexValue(self):
        value = []
        rowCount = self.rowCount()
        for row in range(rowCount):
            itemValue = self.getZoneAndHexValueOfRow(row)
            if itemValue[1] != "None":
                value.append(self.getZoneAndHexValueOfRow(row))
        return value

    def getZoneAndHexValueOfCurrentRow(self):
        row = self.currentRow()
        if row < 0:
            return [0 , "None"]
        return self.getZoneAndHexValueOfRow(row)

    def getZoneAndHexValueOfRow(self, row):
        value = "None"
        zone = self.item(row, 0).text()
        cellItem = self.cellWidget(row, 2)
        if isinstance(cellItem, EcuZoneLineEdit):
            if cellItem.isLineEditChanged():
                value = cellItem.text()
        elif isinstance(cellItem, EcuZoneCheckBox):
            if cellItem.isCheckBoxChanged():
                if cellItem.checkState() == Qt.Checked:
                    value = "01"
                else:
                    value = "00"
        elif isinstance(cellItem, EcuZoneComboBox):
            if cellItem.isComboBoxChanged():
                index = cellItem.currentIndex()
                value = "%0.2X" % cellItem.itemData(index)
        return [zone, value]

    def changeZoneOption(self, zone, data: str, valueType: str):
        cellItems = self.findItems(zone, Qt.MatchExactly)
        if cellItems:
            row = cellItems[0].row()
            cellItem = self.cellWidget(row, 2)
            if isinstance(cellItem, EcuZoneLineEdit):
                if data == "No Response":
                    self.markItemNoResponse(row)
                    return
                if valueType == "string_ascii":
                    cellItem.setText(str(data))
                elif valueType == "int":
                    cellItem.setText(str(int(data, 16)))
                else:
                    cellItem.setText(data)
            elif isinstance(cellItem, EcuZoneCheckBox):
                if data == "No Response":
                    self.markItemNoResponse(row)
                    return
                if data == "01":
                    cellItem.setCheckState(Qt.Checked)
                elif data == "00":
                    cellItem.setCheckState(Qt.Unchecked)
            elif isinstance(cellItem, EcuZoneComboBox):
                if data == "No Response":
                    self.markItemNoResponse(row)
                    return
                for i in range(cellItem.count()):
                    if cellItem.itemData(i) == int(data, 16):
                        cellItem.setCurrentIndex(i)
                        return
                self.markItemValueOutOfRange(row)

