"""
   FileLoader.py

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

import csv
import json
from PySide6.QtCore import Qt, QThread, Signal


class FileLoaderThread(QThread):
    newRowSignal = Signal(list)
    loadingFinishedSignal = Signal()
    isRunning = bool
    path = None
    delayMs = 0

    def __init__(self):
        super(FileLoaderThread, self).__init__()
        self.isRunning = True

    def enable(self, path, delayMs):
        self.path = path
        self.delayMs = delayMs
        self.isRunning = True
        self.start()

    def stop(self):
        self.isRunning = False
        self.path = None

    def run(self):
        self.isRunning = True
        code = "utf-8"
        while self.isRunning:
            if self.path is not None:
                try:
                    stream = open(str(self.path), 'r', encoding=code)
                except OSError:
                    print("file not found: " + self.path)
                    self.stop()

                try:
                    for rowData in csv.reader(stream):
                        if not self.isRunning:
                            break
                        self.newRowSignal.emit(rowData)
                        self.msleep(self.delayMs)
                    self.loadingFinishedSignal.emit()
                except:
                    if code == "utf-8":
                        code = "iso-8859-1"
                        continue;
                self.stop()
