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

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QSizePolicy, QTabWidget, QTreeWidget
from PySide6.QtGui import QColor

from EcuZoneLineEdit import EcuZoneLineEdit
from EcuZoneCheckBox import EcuZoneCheckBox
from EcuZoneComboBox import EcuZoneComboBox
from EcuZoneTreeWidgetItem import EcuZoneTreeWidgetItem
from EcuMultiZoneTreeWidgetItem import EcuMultiZoneTreeWidgetItem

class EcuZoneTreeView(QTabWidget):
    """
    """
    def __init__(self, parent, ecuObjectList = None):
        super(EcuZoneTreeView, self).__init__(parent)
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.updateView(ecuObjectList)

    def updateView(self, ecuObjectList):
        if ecuObjectList != None:
            if "zones" in ecuObjectList:
                self.zoneObjectList = ecuObjectList["zones"]
            elif "ecu" in ecuObjectList:
                self.zoneObjectList = ecuObjectList["ecu"]
            else:
                return;

            # Checking integrity of JSON file
            for zoneIDObject in self.zoneObjectList:
                zoneObject = self.zoneObjectList[zoneIDObject]
                if not("tab" in zoneObject):
                    print(zoneIDObject + ": Has not tab assigned")
                    continue
                if not(zoneObject["tab"] in ecuObjectList["tabs"]):
                    print(zoneIDObject + ": uses '" + zoneObject["tab"] + "' tab, but is not in tabs list")
                    continue

            self.clear()
            self.tabs = []
            for tabs in ecuObjectList["tabs"]:
                name = ecuObjectList["tabs"][tabs]
                index = self.addTab(EcuZoneTreeViewWidget(self, self.zoneObjectList, tabs), str(name))
                self.tabs.append([tabs, index])

    def getValuesAsCSV(self):
        value = []
        for tab in self.tabs:
            widget = self.widget(tab[1])
            value.append(widget.getValuesAsCSV())
        return value

    def getZoneListOfHexValue(self):
        value = []
        for tab in self.tabs:
            widget = self.widget(tab[1])
            value.append(widget.getZoneListOfHexValue())
        return value

    def getZoneAndHexValueOfCurrentRow(self):
        widget = self.currentWidget()
        return widget.getZoneAndHexValueOfCurrentRow()

    def changeZoneOption(self, zone: str, data: str):
        for zoneIDObject in self.zoneObjectList:
            if zone.upper() == zoneIDObject.upper():
                zoneObject = self.zoneObjectList[zoneIDObject]
                valueType = "None"
                if "type" in zoneObject:
                    valueType = zoneObject["type"]
                else:
                    print(zoneIDObject + ": has no item 'type'")
                tabName = zoneObject["tab"]
                for tab in self.tabs:
                    if tab[0] == tabName:
                        widget = self.widget(tab[1])
                        widget.changeZoneOption(zone.upper(), data, valueType)


class EcuZoneTreeViewWidget(QTreeWidget):
    def __init__(self, parent, zoneObjectList, tabName: str):
        super(EcuZoneTreeViewWidget, self).__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels(["Zone", "Zone Description", "Options"])
        self.setWordWrap(True)
        rowCount = 0
        # Setup Tree view
        for zoneIDObject in zoneObjectList:
            zoneObject = zoneObjectList[zoneIDObject]
            if not("tab" in zoneObject) or zoneObject["tab"] != tabName:
                continue

            itemName = zoneObject["name"];
            formType = zoneObject["form_type"]
            if formType == "multi":
                root = EcuMultiZoneTreeWidgetItem(self, rowCount, zoneIDObject, itemName, zoneObject)
                rootReadOnly = True
                root.addRootWidgetItem(self, EcuZoneLineEdit(self, zoneObject, rootReadOnly))
                self.markItemAsRootLevel(root)
                rowCount += 1
                # Do we have new NAC json File
                if "params" in zoneObject:
                    zoneObject = zoneObject["params"]
                    for subZoneObject in zoneObject:
                        # Check do we have a sub config if not goto next
                        if not "name" in subZoneObject:
                            continue
                        # We have a sub config
                        formType = subZoneObject["form_type"]
                        name = subZoneObject["name"]
                        if formType == "combobox":
                            widgetItem = EcuZoneComboBox(self, subZoneObject)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "checkbox":
                            root.addChildWidgetItem(self, name, EcuZoneCheckBox(self, subZoneObject))
                        elif formType == "string":
                            root.addChildWidgetItem(self, name, EcuZoneLineEdit(self, subZoneObject, False))
                else:
                    for subZoneIDObject in zoneObject:
                        subZoneObject = zoneObject[str(subZoneIDObject)]
                        # Check do we have a sub config if not goto next
                        if not "name" in subZoneObject:
                            continue
                        # We have a sub config
                        formType = subZoneObject["form_type"]
                        name = subZoneObject["name"]
                        if formType == "combobox":
                            widgetItem = EcuZoneComboBox(self, subZoneObject)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "checkbox":
                            root.addChildWidgetItem(self, name, EcuZoneCheckBox(self, subZoneObject))
                        elif formType == "string":
                            root.addChildWidgetItem(self, name, EcuZoneLineEdit(self, subZoneObject, False))
                root.setExpanded(True)
            else:
                root = EcuZoneTreeWidgetItem(self, rowCount, str(zoneIDObject), itemName)
                rowCount += 1
                if formType == "combobox":
                    root.addItem(self, EcuZoneComboBox(self, zoneObject))
                elif formType == "checkbox":
                    root.addItem(self, EcuZoneCheckBox(self, zoneObject))
                elif formType == "string":
                    root.addItem(self, EcuZoneLineEdit(self, zoneObject, False))

        self.setColumnWidth(0, 70)
        self.setColumnWidth(1, 400)
        self.setColumnWidth(2, 350)

    def markItemAsRootLevel(self, item):
        item.setBackground(0, QColor(0, 255, 0))
        item.setBackground(1, QColor(0, 255, 0))

    def markItemValueOutOfRange(self, item):
        item.setBackground(0, QColor(255, 128, 0))
        item.setBackground(1, QColor(255, 128, 0))

    def markItemNoResponse(self, item):
        widget = item.treeWidget().itemWidget(item, 2)
        widget.setDisabled(True);
        item.setBackground(0, QColor(255, 128, 128))
        item.setBackground(1, QColor(255, 128, 128))

    def getValuesAsCSV(self):
        value = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            itemValue = item.getValuesAsCSV()
            value.append(itemValue)
        return value

    def getZoneListOfHexValue(self):
        value = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            itemValue = item.getZoneAndHex()
            if itemValue[1] != "None":
                value.append(itemValue)
        return value

    def changeZoneOption(self, zone, data: str, valueType: str):
        cellItems = self.findItems(zone, Qt.MatchExactly)
        if cellItems:
            cellItem = cellItems[0]
            if data == "Disabled" or data == "No Response" or data == "Request out of range" or data == "Unkown Error" or data == "Timeout":
                self.markItemNoResponse(cellItem)
                return
            cellItem.changeZoneOption(cellItem, data, valueType)
