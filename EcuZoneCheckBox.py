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

from PySide6.QtWidgets import QCheckBox


class EcuZoneCheckBox(QCheckBox):
    """
    """
    value = 0
    configID = ""
    def __init__(self, parent, configID: str = ""):
        super(EcuZoneCheckBox, self).__init__(parent)
        self.configID = configID

    def getConfigID(self):
        return self.configID

    def setCheckState(self, val):
        self.value = val;
        super().setCheckState(val)

    def isCheckBoxChanged(self):
        return self.isEnabled() and self.value != self.checkState()

