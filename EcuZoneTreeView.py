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

from PySide6.QtCore import Qt, Slot, QEvent, QSize, QPoint
from PySide6.QtWidgets import QSizePolicy, QMenu, QTabWidget, QTreeWidget, QTabBar, QStyle, QStylePainter, QStyleOptionTab
from PySide6.QtGui import QColor, QPaintEvent

from EcuZoneLineEdit import EcuZoneLineEdit
from EcuZoneCheckBox import EcuZoneCheckBox
from EcuZoneComboBox import EcuZoneComboBox
from EcuZoneTreeWidgetItem import EcuZoneTreeWidgetItem
from EcuMultiZoneTreeWidgetItem import EcuMultiZoneTreeWidgetItem
from i18n import i18n
import PyPSADiagGUI

class HorizontalTextTabBar(QTabBar):
    """
    Special Text TabBar, with always Horizontal text
    """
    def __init__(self, parent):
        super(HorizontalTextTabBar, self).__init__(parent)

    def paintEvent(self, event: QPaintEvent):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.CE_TabBarTabShape, option)
            painter.drawText(self.tabRect(index),
                             Qt.AlignCenter | Qt.AlignLeft | Qt.TextDontClip,
                             self.tabText(index))

    def tabSizeHint(self, index):
        size = QTabBar.tabSizeHint(self, index)
        if size.width() < size.height():
            size.transpose()
        return size - QSize(5, 4)

class EcuZoneTreeView(QTabWidget):
    """
    """
    tabs = []

    def __init__(self, parent, ecuObjectList = None):
        super(EcuZoneTreeView, self).__init__(parent)
        self.setTabBar(HorizontalTextTabBar(self))
        self.hideZones = False
        self.searchText = ""
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.updateView(ecuObjectList)
        self.setTabPosition(self.TabPosition.North)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)

    @Slot()
    def contextMenu(self, pos: QPoint):
        contextMenu = QMenu(self)
        tabsTop = contextMenu.addAction(i18n().tr("Tabs above the pages"))
        tabsLeft = contextMenu.addAction(i18n().tr("Tabs to the left of the pages"))

        action = contextMenu.exec_(self.mapToGlobal(pos))
        if action == tabsTop:
            self.setTabPosition(self.TabPosition.North)

        if action == tabsLeft:
            self.setTabPosition(self.TabPosition.West)

    def updateView(self, ecuObjectList):
        if ecuObjectList != None:
            if "zones" in ecuObjectList:
                self.zoneObjectList = ecuObjectList["zones"]
            elif "ecu" in ecuObjectList:
                self.zoneObjectList = ecuObjectList["ecu"]
            else:
                return

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
                name = i18n().tr(str(ecuObjectList["tabs"][tabs]))
                index = self.addTab(EcuZoneTreeViewWidget(self, self.zoneObjectList, tabs), str(name))
                self.tabs.append([tabs, index])

            self.hideNoResponseZones(self.hideZones)
            if hasattr(self, 'searchText') and self.searchText:
                self.filterZones(self.searchText)

    def hideNoResponseZones(self, hide: bool()):
        # Take over the hide flag, so we know for next update/change
        self.hideZones = hide
        for tab in self.tabs:
            index = tab[1]
            widget = self.widget(index)
            has_visible = widget.hideNoResponseZones(hide)
            self.setTabVisible(index, has_visible)

    def filterZones(self, text: str):
        if len(self.tabs) == 0:
            return

        self.searchText = text
        for tab in self.tabs:
            index = tab[1]
            widget = self.widget(index)
            has_visible = widget.setFilterText(text)
            self.setTabVisible(index, has_visible)

    def getValuesAsCSV(self):
        value = []
        for tab in self.tabs:
            widget = self.widget(tab[1])
            value.append(widget.getValuesAsCSV())
        return value

    def clearZoneListValues(self):
        for tab in self.tabs:
            widget = self.widget(tab[1])
            widget.clearZoneListValues()

    def getZoneListOfHexValue(self, virginWrite: bool()):
        value = []
        for tab in self.tabs:
            widget = self.widget(tab[1])
            value.append(widget.getZoneListOfHexValue(virginWrite))
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
        self.hideNoResponseZones(self.hideZones)


class EcuZoneTreeViewWidget(QTreeWidget):
    def __init__(self, parent, zoneObjectList, tabName: str):
        super(EcuZoneTreeViewWidget, self).__init__(parent)
        self.hideZones = False
        self.searchText = ""
        self.setColumnCount(3)
        headers = [i18n().tr("Zone"), i18n().tr("Zone Description"), i18n().tr("Options")]
        self.setHeaderLabels(headers)
        self.setSelectionMode(QTreeWidget.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWordWrap(True)
        self.setAutoScroll(False)
        rowCount = 0
        itemReadOnly = False
        # Setup Tree view
        for zoneIDObject in zoneObjectList:
            zoneObject = zoneObjectList[zoneIDObject]
            if not("tab" in zoneObject) or zoneObject["tab"] != tabName:
                continue
            if "read_only" in zoneObject:
                itemReadOnly = zoneObject["read_only"]
            else:
                itemReadOnly = False

            itemName = i18n().tr(zoneObject["name"])
            formType = zoneObject["form_type"]
            if formType == "multi":
                root = EcuMultiZoneTreeWidgetItem(self, rowCount, zoneIDObject, itemName, zoneObject)
                root.addRootWidgetItem(self, EcuZoneLineEdit(self, zoneObject, itemReadOnly))
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
                        name = i18n().tr(subZoneObject["name"])
                        if formType == "combobox":
                            widgetItem = EcuZoneComboBox(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "checkbox":
                            widgetItem = EcuZoneCheckBox(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "string":
                            widgetItem = EcuZoneLineEdit(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                else:
                    for subZoneIDObject in zoneObject:
                        subZoneObject = zoneObject[str(subZoneIDObject)]
                        # Check do we have a sub config if not goto next
                        if not "name" in subZoneObject:
                            continue
                        # We have a sub config
                        formType = subZoneObject["form_type"]
                        name = i18n().tr(subZoneObject["name"])
                        if formType == "combobox":
                            widgetItem = EcuZoneComboBox(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "checkbox":
                            widgetItem = EcuZoneCheckBox(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                        elif formType == "string":
                            widgetItem = EcuZoneLineEdit(self, subZoneObject, itemReadOnly)
                            root.addChildWidgetItem(self, name, widgetItem)
                root.setExpanded(True)
            else:
                root = EcuZoneTreeWidgetItem(self, rowCount, str(zoneIDObject), itemName)
                rowCount += 1
                if formType == "combobox":
                    widgetItem = EcuZoneComboBox(self, zoneObject, itemReadOnly)
                    root.addItem(self, widgetItem)
                elif formType == "checkbox":
                    widgetItem = EcuZoneCheckBox(self, zoneObject, itemReadOnly)
                    root.addItem(self, widgetItem)
                elif formType == "string":
                    widgetItem = EcuZoneLineEdit(self, zoneObject, itemReadOnly)
                    root.addItem(self, widgetItem)

        self.setColumnWidth(0, 70)
        self.setColumnWidth(1, 400)
        self.setColumnWidth(2, 350)

    def markItemAsRootLevel(self, item):
        item.setBackground(0, PyPSADiagGUI.DARK_GREEN)
        item.setBackground(1, PyPSADiagGUI.DARK_GREEN)
        item.setBackground(2, PyPSADiagGUI.DARK_GREEN)

    def markItemValueOutOfRange(self, item):
        item.setBackground(0, PyPSADiagGUI.ORANGE)
        item.setBackground(1, PyPSADiagGUI.ORANGE)
        item.setBackground(2, PyPSADiagGUI.ORANGE)

    def markItemNoResponse(self, item):
        widget = item.treeWidget().itemWidget(item, 2)
        widget.setDisabled(True)
        item.setBackground(0, PyPSADiagGUI.DARK_RED)
        item.setBackground(1, PyPSADiagGUI.DARK_RED)
        item.setBackground(2, PyPSADiagGUI.DARK_RED)

    def markItemAsNormal(self, item):
        widget = item.treeWidget().itemWidget(item, 2)
        if widget.isEnabled() == False:
            widget.setDisabled(False)
            item.setBackground(0, PyPSADiagGUI.BASE_COLOR)
            item.setBackground(1, PyPSADiagGUI.BASE_COLOR)
            item.setBackground(2, PyPSADiagGUI.BASE_COLOR)

    def hideNoResponseZones(self, hide: bool()):
        self.hideZones = hide
        return self.applyFilters()

    def setFilterText(self, text: str):
        self.searchText = text
        return self.applyFilters()

    def applyFilters(self):
        search_lower = self.searchText.lower()
        visible_count = 0
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            hide_item = False

            # Check if item should be hidden due to hideZones filter
            if self.hideZones:
                widget = item.treeWidget().itemWidget(item, 2)
                if widget and widget.isEnabled() == False:
                    hide_item = True

            # Always process children to ensure proper visibility state
            if not hide_item:
                if self.searchText:
                    # Text filter is active - check matches
                    zone_id = item.text(0).lower()
                    zone_desc = item.text(1).lower()
                    top_level_matches = search_lower in zone_id or search_lower in zone_desc

                    # Check children for matches
                    child_matches = False
                    for child_index in range(item.childCount()):
                        child = item.child(child_index)
                        # Children marked as variant-mismatch by changeZoneOption
                        # (Disabled(2)) stay hidden regardless of search filter.
                        if bool(child.data(0, Qt.UserRole + 1)):
                            child.setHidden(True)
                            continue
                        child_param_name = child.text(1).lower()
                        child_matches_search = search_lower in child_param_name

                        # Hide/show individual children based on search
                        child.setHidden(not child_matches_search)
                        if child_matches_search:
                            child_matches = True

                    # Hide top-level item only if neither it nor any of its children match
                    if not top_level_matches and not child_matches:
                        hide_item = True
                else:
                    # No text filter - make children visible, but keep
                    # variant-mismatch children hidden.
                    for child_index in range(item.childCount()):
                        child = item.child(child_index)
                        if bool(child.data(0, Qt.UserRole + 1)):
                            child.setHidden(True)
                        else:
                            child.setHidden(False)

            item.setHidden(hide_item)
            if not hide_item:
                visible_count += 1

        return visible_count > 0

    def getValuesAsCSV(self):
        value = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            itemValue = item.getValuesAsCSV()
            value.append(itemValue)
        return value

    def clearZoneListValues(self):
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            item.clearZoneListValues()
            self.markItemAsNormal(item)

    def getZoneListOfHexValue(self, virginWrite: bool()):
        value = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            itemValue = item.getZoneAndHex(virginWrite)
            if itemValue[1] != "None":
                value.append(itemValue)
        return value

    def changeZoneOption(self, zone, data: str, valueType: str):
        cellItems = self.findItems(zone, Qt.MatchExactly)
        if cellItems:
            cellItem = cellItems[0]
            # Do not translate these strings
            if data == "Disabled" or data == "No Response" or data == "Request out of range" or data == "Unknown Error" or data == "Timeout" or (len(data) >= 6 and data[0:6] == "Error:"):
                self.markItemNoResponse(cellItem)
                return
            cellItem.changeZoneOption(cellItem, data, valueType) 
