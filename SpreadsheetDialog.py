"""
   SpreadsheetDialog.py

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

from PySide6.QtCore import Qt, Slot, QIODevice
from PySide6.QtWidgets import QWidget, QFrame, QDialog, QPushButton, QHBoxLayout, QVBoxLayout, QSizePolicy, QSpacerItem, QTableWidget, QTableWidgetItem

from i18n import i18n

class SpreadsheetDialog(QDialog):

    def __init__(self, parent, title: str(), csvList: [], labels: []):
        super(SpreadsheetDialog, self).__init__(parent)
        self.resize(1100, 600)
        self.setWindowTitle(title)
        self.setModal(True)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)

        # Setup Spreadsheet for csvList
        self.spreadsheet = QTableWidget()
        self.spreadsheet.setColumnCount(len(labels))
        self.spreadsheet.setHorizontalHeaderLabels(labels)
        self.spreadsheet.setRowCount(len(csvList))
        self.spreadsheet.setSortingEnabled(False)
        row = 0
        for csv in csvList:
            col = 0
            for value in csv:
                item = QTableWidgetItem(value)
                self.spreadsheet.setItem(row, col, item)
                col += 1
            row += 1
        self.spreadsheet.resizeColumnsToContents()
        self.spreadsheet.adjustSize()


        # Setup Buttons
        self.acceptButton = QPushButton()
        self.acceptButton.setText(i18n().tr("Ok"))

        # Setup Connections (Signal-Slots)
        self.acceptButton.clicked.connect(self.acceptCallback)

        # Add Widgets to Work Frame layout
        self.workFrameLayout = QVBoxLayout()
        self.workFrameLayout.addWidget(self.spreadsheet)

        # Add Buttons to Button layout
        self.buttontLayout = QHBoxLayout()
        self.buttontLayout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.buttontLayout.addWidget(self.acceptButton)

        # Add Layouts to Main layout
        self.frameLayout = QVBoxLayout()
        self.frameLayout.setContentsMargins(16, 16, 16, 16)
        self.frameLayout.setSpacing(12)
        self.frameLayout.addLayout(self.workFrameLayout)
        self.frameLayout.addLayout(self.buttontLayout)
        self.setLayout(self.frameLayout)

    @Slot()
    def acceptCallback(self):
        self.done(SpreadsheetDialog.Accepted)
