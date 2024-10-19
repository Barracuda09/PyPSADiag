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


class EcuMultiZoneTreeWidgetItem(QTreeWidgetItem):
    zone = ""
    zoneObject = ""
    def __init__(self, parent: QTreeWidget, row: int, zone: str, description: str, zoneObject: dict):
        super(EcuMultiZoneTreeWidgetItem, self).__init__(parent, [zone, description])
        parent.insertTopLevelItem(row, self)
        self.zoneObject = zoneObject
        self.zone = zone

    def addRootWidgetItem(self, tree: QTreeWidget, widget):
        tree.setItemWidget(self, 2, widget)
        self.__setupConnections(widget)

    def addChildWidgetItem(self, tree: QTreeWidget, label, widget):
        level = EcuZoneTreeWidgetItem(self, None, "", label)
        tree.setItemWidget(level, 2, widget)
        self.__setupConnections(widget)

    def __setupConnections(self, widget):
        if isinstance(widget, EcuZoneLineEdit):
            widget.textChanged.connect(self.textChanged)
        elif isinstance(widget, EcuZoneCheckBox):
            widget.stateChanged.connect(self.stateChanged)
        elif isinstance(widget, EcuZoneComboBox):
            widget.currentIndexChanged.connect(self.currentIndexChanged)

    def getZoneAndHex(self):
        widget = self.treeWidget().itemWidget(self, 2)
        value = "None"
        if isinstance(widget, EcuZoneLineEdit):
            if widget.isLineEditChanged():
                value = widget.text()
        return [self.zone, value]

    def changeZoneOption(self, root, data: str, valueType: str):
        # Make Bytes (2 chars) from input data
        byteData = []
        for i in range(0, len(data), 2):
            byteData.append(data[i:i + 2])
        widget = root.treeWidget().itemWidget(root, 2)
        widget.setText(str(data))
        for index in range(root.childCount()):
            cellItem = root.child(index)
            widget = cellItem.treeWidget().itemWidget(cellItem, 2)
            zone = self.zoneObject[widget.getConfigID()]
            byteNr = zone["byte"]
            mask = int(zone["mask"], 2)
            byte = int(byteData[byteNr], 16) & mask
            if isinstance(widget, EcuZoneLineEdit):
                widget.setText(str(data))
            elif isinstance(widget, EcuZoneCheckBox):
                if byte > 0:
                    widget.setCheckState(Qt.Unchecked)
                else:
                    widget.setCheckState(Qt.Checked)
            elif isinstance(widget, EcuZoneComboBox):
                for i in range(widget.count()):
                    if widget.itemData(i) == byte:
                        widget.setCurrentIndex(i)
                        break

    def __update(self):
        rootWidget = self.treeWidget().itemWidget(self, 2)
        data = rootWidget.text()
        byteData = []
        for i in range(0, len(data), 2):
            byteData.append(data[i:i + 2])
        for index in range(self.childCount()):
            cellItem = self.child(index)
            widget = cellItem.treeWidget().itemWidget(cellItem, 2)
            zone = self.zoneObject[widget.getConfigID()]
            byteNr = zone["byte"]
            # Do we need to expand
            if len(byteData) < (byteNr + 1):
                for i in range((byteNr - len(byteData) + 1)):
                    byteData.insert(len(byteData) + i, "00")
            mask = int(zone["mask"], 2)
            if isinstance(widget, EcuZoneLineEdit):
                value = (int(byteData[byteNr], 16) & ~mask) | int(widget.text(), 16)
                byteData[byteNr] = "%0.2X" % value
            elif isinstance(widget, EcuZoneCheckBox):
                if widget.isChecked():
                    value = (int(byteData[byteNr], 16) & ~mask)
                    byteData[byteNr] = "%0.2X" % value
                else:
                    value = (int(byteData[byteNr], 16) | mask)
                    byteData[byteNr] = "%0.2X" % value
            elif isinstance(widget, EcuZoneComboBox):
                index = widget.currentIndex()
                value = (int(byteData[byteNr], 16) & ~mask) | widget.itemData(index)
                byteData[byteNr] = "%0.2X" % value

        data = ""
        for i in range(len(byteData)):
            data += byteData[i]
        rootWidget.updateText(str(data))

    @Slot()
    def currentIndexChanged(self, item: int):
        self.__update()

    @Slot()
    def textChanged(self, item: str):
        self.__update()

    @Slot()
    def stateChanged(self, item: int):
        self.__update()

