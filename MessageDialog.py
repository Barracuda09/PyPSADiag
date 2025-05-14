"""
   MessageDialog.py

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
from PySide6.QtWidgets import QWidget, QFrame, QDialog, QTextEdit, QPushButton, QHBoxLayout, QVBoxLayout, QSizePolicy

class MessageDialog(QDialog):

    def __init__(self, parent, title: str(), acceptTxt: str(), text: str()):
        super(MessageDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.append(text)

        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)

        self.rejectButton = QPushButton()
        self.rejectButton.setText("Cancel")
        self.acceptButton = QPushButton()
        self.acceptButton.setText(acceptTxt)

        self.rejectButton.clicked.connect(self.rejectCallback)
        self.acceptButton.clicked.connect(self.acceptCallback)

        self.workFrameLayout = QVBoxLayout()
        self.workFrameLayout.addWidget(self.output)

        self.buttontLayout = QHBoxLayout()
        self.buttontLayout.addWidget(self.acceptButton)
        self.buttontLayout.addWidget(self.rejectButton)

        self.frameLayout = QVBoxLayout()
        self.frameLayout.addLayout(self.workFrameLayout)
        self.frameLayout.addLayout(self.buttontLayout)

        self.setLayout(self.frameLayout)
        self.resize(self.sizeHint());

    @Slot()
    def rejectCallback(self):
        self.done(MessageDialog.Rejected)

    @Slot()
    def acceptCallback(self):
        self.done(MessageDialog.Accepted)
