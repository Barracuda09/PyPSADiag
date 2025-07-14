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
from PySide6.QtWidgets import QTreeWidgetItem, QTreeWidget

from EcuZoneLineEdit import EcuZoneLineEdit
from EcuZoneCheckBox import EcuZoneCheckBox
from EcuZoneComboBox import EcuZoneComboBox
from EcuZoneTreeWidgetItem import EcuZoneTreeWidgetItem
from i18n import i18n


class EcuMultiZoneTreeWidgetItem(QTreeWidgetItem):
    zone = ""
    zoneDescription = ""
    zoneObject = {}
    integrity = True
    selfUpdate = False
    def __init__(self, parent: QTreeWidget, row: int, zone: str, description: str, zoneObject: dict):
        super(EcuMultiZoneTreeWidgetItem, self).__init__(parent, [zone.upper(), str("** " + i18n().tr(description) + " **")])
        parent.insertTopLevelItem(row, self)
        self.setToolTip(1, i18n().tr(description))
        self.zoneObject = zoneObject
        self.zone = zone.upper()
        self.zoneDescription = description

    def addRootWidgetItem(self, tree: QTreeWidget, widget):
        widget.setReadOnly(True)
        tree.setItemWidget(self, 2, widget)
        self.__setupConnections(widget)

    def addChildWidgetItem(self, tree: QTreeWidget, label, widget):
        level = EcuZoneTreeWidgetItem(self, None, "", label)
        level.setToolTip(1, i18n().tr(label))
        tree.setItemWidget(level, 2, widget)
        self.__setupConnections(widget)

    def __setupConnections(self, widget):
        if isinstance(widget, EcuZoneLineEdit):
            widget.textChanged.connect(self.textChanged)
        elif isinstance(widget, EcuZoneCheckBox):
            widget.stateChanged.connect(self.stateChanged)
        elif isinstance(widget, EcuZoneComboBox):
            widget.currentIndexChanged.connect(self.currentIndexChanged)

    def getValuesAsCSV(self):
        widget = self.treeWidget().itemWidget(self, 2)
        value = "None"
        # Check if Integrity is correct, then return Zone data
        if self.integrity and isinstance(widget, EcuZoneLineEdit):
            value = widget.getValuesAsCSV()
        return [self.zone, value, self.zoneDescription]

    def clearZoneListValues(self):
        rootWidget = self.treeWidget().itemWidget(self, 2)
        rootWidget.clearZoneValue()
        for index in range(self.childCount()):
            cellItem = self.child(index)
            widget = cellItem.treeWidget().itemWidget(cellItem, 2)
            widget.clearZoneValue()

    def getZoneAndHex(self, virginWrite: bool()):
        widget = self.treeWidget().itemWidget(self, 2)
        value = "None"
        # Check if Integrity is correct, then return Zone data
        if self.integrity and isinstance(widget, EcuZoneLineEdit):
            value = widget.getZoneAndHex(virginWrite)
        return [self.zone, value]

    def changeZoneOption(self, root, data: str, valueType: str):
        self.selfUpdate == True
        try:
            # Set Root value of Multi Config zone
            widget = root.treeWidget().itemWidget(root, 2)
            widget.changeZoneOption(data, "")

            # Set individual Sub items
            for index in range(root.childCount()):
                cellItem = root.child(index)
                widget = cellItem.treeWidget().itemWidget(cellItem, 2)
                result = widget.changeZoneOption(data, valueType)
                if result == 2:
                    print("Disabled(2): " + self.zone + " - " + widget.getDescriptionName())
                    widget.setStyleSheet("QComboBox{background-color: red;}")
                    widget.setEnabled(False)
                    cellItem.setHidden(True)
                elif result == 1:
                    print("Disabled(1): " + self.zone + " - " + widget.getDescriptionName())
                    self.integrity = False
        except:
            print("except: EcuMultiZoneTreeWidgetItem:changeZoneOption " + self.zone + " - " + widget.getDescriptionName())

        self.selfUpdate == False
        # Integrity wrong, disable the sub zones and coding
        if not self.integrity:
            for index in range(root.childCount()):
                cellItem = root.child(index)
                widget = cellItem.treeWidget().itemWidget(cellItem, 2)
                widget.setStyleSheet("QComboBox{background-color: red;}")
                widget.setEnabled(False)

    def __update(self):
        # If we are "self" updating (By loading CSV file) do not call update
        if self.selfUpdate == True:
            return

        rootWidget = self.treeWidget().itemWidget(self, 2)
        data = rootWidget.text()
        # Make Bytes (2 chars) from input data
        byteData = []
        for i in range(0, len(data), 2):
            byteData.append(data[i:i + 2])

        for index in range(self.childCount()):
            cellItem = self.child(index)
            widget = cellItem.treeWidget().itemWidget(cellItem, 2)

            byteNr = widget.getCorrespondingByte()
            size = widget.getCorrespondingByteSize()

            # Size do not correspond or not Enabled, Then Goto next item
            if (byteNr + size) > len(byteData) or widget.isEnabled() == False:
                continue

            # Get the corresponing data for this "zone"
            currData = str().join(byteData[byteNr : byteNr + size])

            if isinstance(widget, EcuZoneLineEdit):
                currData = widget.update(currData)
            elif isinstance(widget, EcuZoneCheckBox):
                currData = widget.update(currData)
            elif isinstance(widget, EcuZoneComboBox):
                currData = widget.update(currData)

            # Put back changed "zone" data
            for i in range(size):
                j = (i * 2)
                byteData[byteNr + i] = currData[j:j + 2]

        # Update changed "zone" data
        rootWidget.updateText(str().join(byteData))

    @Slot()
    def currentIndexChanged(self, item: int):
        self.__update()

    @Slot()
    def textChanged(self, item: str):
        self.__update()

    @Slot()
    def stateChanged(self, item: int):
        self.__update()

