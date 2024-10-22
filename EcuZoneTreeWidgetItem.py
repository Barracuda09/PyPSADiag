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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem, QTreeWidget, QLabel, QFrame

from EcuZoneLineEdit import EcuZoneLineEdit
from EcuZoneCheckBox import EcuZoneCheckBox
from EcuZoneComboBox import EcuZoneComboBox


class EcuZoneTreeWidgetItem(QTreeWidgetItem):
    zone = ""
    def __init__(self, parent, row: int, zone: str, description: str):
        super(EcuZoneTreeWidgetItem, self).__init__(parent, [zone, description])
        if isinstance(parent, QTreeWidget):
            parent.insertTopLevelItem(row, self)
        self.zone = zone

#        label = QLabel(description)
#        label.setWordWrap(True)
#        label.setFrameStyle(QFrame.NoFrame)
#        label.setContentsMargins(0, 0, 0, 0)
#        self.treeWidget().setItemWidget(self, 1, label)

    def addItem(self, tree: QTreeWidgetItem, widget):
        tree.setItemWidget(self, 2, widget)

    def getZoneAndHex(self):
        widget = self.treeWidget().itemWidget(self, 2)
        value = "None"
        if isinstance(widget, EcuZoneLineEdit):
            value = widget.getZoneAndHex()
        elif isinstance(widget, EcuZoneCheckBox):
            value = widget.getZoneAndHex()
        elif isinstance(widget, EcuZoneComboBox):
            value = widget.getZoneAndHex()
        return [self.zone, value]

    def changeZoneOption(self, cellItem, data: str, valueType: str):
        widget = cellItem.treeWidget().itemWidget(cellItem, 2)
        if isinstance(widget, EcuZoneLineEdit):
            widget.changeZoneOption(data, valueType)
        elif isinstance(widget, EcuZoneCheckBox):
            widget.changeZoneOption(data, valueType)
        elif isinstance(widget, EcuZoneComboBox):
            widget.changeZoneOption(data, valueType)

