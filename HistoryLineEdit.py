"""
   HistoryLineEdit.py

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

from PySide6.QtCore import Qt, Slot, QIODevice, QEvent
from PySide6.QtWidgets import QWidget, QLineEdit
from PySide6.QtGui import QKeyEvent

class HistoryLineEdit(QLineEdit):
    historyIndex = 0
    history = []

    def __init__(self, parent = None):
        super(HistoryLineEdit, self).__init__(parent)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_Up:
            if len(self.history) > self.historyIndex:
                self.setText(self.history[self.historyIndex])
                if len(self.history) > self.historyIndex + 1:
                    self.historyIndex += 1
        elif key == Qt.Key_Down:
            if self.historyIndex > 0:
                self.historyIndex -= 1
                self.setText(self.history[self.historyIndex])
            else:
                self.clear()
        elif key == Qt.Key_Escape:
            self.historyIndex = 0
            self.clear()
        elif key == Qt.Key_Enter or key == Qt.Key_Return:
            txt = self.text()
            if txt != "":
                self.historyIndex = 0
                self.history.insert(self.historyIndex, txt)

        super().keyPressEvent(event)
