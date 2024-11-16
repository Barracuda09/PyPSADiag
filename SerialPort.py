"""
   SerialPort.py

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

import time
import serial.tools.list_ports


class SerialPort():

    def __init__(self):
        self.serialPort = serial.Serial()

    # Get available Serial ports and put it in Combobox
    def fillPortNameCombobox(self, combobox):
        combobox.clear()
        comPorts = serial.tools.list_ports.comports()
        nameList = list(port.device for port in comPorts)
        for name in nameList:
            combobox.addItem(name)

    def isOpen(self):
        return self.serialPort.isOpen()

    def close(self):
        self.serialPort.close()

    def open(self, portNr, baudRate):
        try:
            self.serialPort.port = portNr
            self.serialPort.baudrate = baudRate
            #self.serialController.setDTR(True)
            self.serialPort.open()
        except serial.SerialException as e:
            print('Error opening port: ' + str(e))

    def write(self, data):
        print(data)
        self.serialPort.write(data)

    def readData(self):
        data = bytearray()
        runLoop = 50
        while runLoop > 0:
            dataLen = self.serialPort.in_waiting
            if dataLen > 1:
                subData = self.serialPort.read(dataLen)
                if len(subData):
                    data.extend(subData)
                    if data.find(b"\r") != -1:
                        break
                    time.sleep(0.1)
                    runLoop = 5
            else:
                time.sleep(0.10)
                runLoop -= 1
        return data

    def sendReceive(self, cmd: str):
        cmd += "\n"
        self.write(cmd.encode("utf-8"))
        data = self.readData()
        if len(data) == 0:
            return "Timeout"

        i = data.find(b"\r")
        decodedData = data[:i].decode("utf-8");
        return decodedData
