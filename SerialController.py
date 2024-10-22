"""
   SerialController.py

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
import time
import queue
from PySide6.QtCore import Qt, Slot, QThread, Signal, QIODevice


class SerialControllerThread(QThread):
    receivedPacketSignal = Signal(str, float)
    serialPort = QSerialPort
    writerQ = queue.Queue()

    def __init__(self):
        super(SerialControllerThread, self).__init__()

        # Open a Serial connection with 'ReadyRead' signal connected to 'receive' slot
        self.serialPort = QSerialPort(readyRead = self.receive)
        self.serialPort.setBaudRate(QSerialPort.Baud115200)
        self.serialPort.setPortName("COM3")
        self.serialPort.open(QIODevice.ReadWrite)
        elementE = ">333:333\n"
        print(elementE.encode("utf-8"))
        self.serialPort.write(elementE.encode("utf-8"))
        print("Write Done")

        self.isRunning = False
        self.closePort = False
        self.start()

    def connectPort(self, portName: str):
        self.serialPort.setBaudRate(QSerialPort.Baud115200)
        self.serialPort.setPortName(portName)
        self.serialPort.open(QIODevice.ReadWrite)

    def disconnectPort(self):
        self.closePort = True

    def writeData(self, data: str):
        print("writeData")
        self.writerQ.put(data)
        print("writeData Done")

    @Slot()
    def receive(self):
        while self.serialPort.canReadLine():
            self.text = self.serialPort.readLine().data().decode()
            self.text = self.text.rstrip("\r\n")
            print(self.text)
            #self.ui.output.append(self.text)

    def stop(self):
        self.isRunning = False

    def run(self):
        self.isRunning = True
        while self.isRunning:
            if self.closePort:
                if self.serialPort.isOpen():
                    self.serialPort.close()
                    self.closePort = False
                    print("Closing Port")
            if self.serialPort.isOpen():
                if not self.writerQ.empty():
                    self.element = self.writerQ.get()
                    print(self.element.rstrip("\r\n"))
                    self.serialPort.write(self.element.encode("utf-8"))
                    print("Done")

                    self.data = None
            #self.msleep(100)
            #print("Running")
