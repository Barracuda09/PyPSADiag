"""
   EcuSimulation.py

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
import queue
import csv
import json
import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QTextEdit

from SeedKeyAlgorithm import SeedKeyAlgorithm
from CalcCRC16X25 import CalcCRC16X25

class EcuSimulation(QThread):
    algo = SeedKeyAlgorithm()
    crcx25 = CalcCRC16X25()
    ecuData = None
    protocol = ""
    ecuID = ""
    rxID = ""
    txID = ""

    def __init__(self):
        super(EcuSimulation, self).__init__()

    def receive(self):
        time.sleep(0.2)
        #return "2306230723082309230A230B230C230D230E230F"
        return ""

    def sendReceive(self, cmd: str):
        time.sleep(0.2)
        return self.__simulateAnswer(cmd)

    def __simulateAnswer(self, cmd: str):
        if cmd[:1] == ">":
            # Open car simulation file
            file = open(os.path.join(os.path.dirname(__file__), "simu/car.json"), 'r', encoding='utf-8')
            jsonFile = file.read()
            self.carECUList = json.loads(jsonFile.encode("utf-8"))
            self.txID = cmd[1:4]
            self.rxID = cmd[5:9]
            self.ecuID = cmd[1:9]
            self.protocol = ""
            self.ecuData = None
            return "OK"
        if cmd == "KU":
            return "OK"
        if cmd == "KK":
            return "OK"
        if cmd == "S":
            return "OK"

        # Sketch
        if cmd[:1] == ":":
            return "6704"

        # UDS
        if cmd == "1103":
            return "5103"
        if cmd == "1003":
            # Check if ECU is in car simulation and if correct protocol
            if (self.ecuID in self.carECUList) and (self.carECUList[self.ecuID]["protocol"] == "uds"):
                self.protocol = "uds"
                return "500300C80014"
        if cmd == "1001":
            self.protocol = ""
            self.ecuData = None
            return "500100C80014"
        if cmd == "2703":
            #return "7F2722" # Return some error
            return "67036B0A71E0"
        if cmd[:4] == "2704":
            return "6704"

        # KWP_IS
        if cmd == "81":
            # Check if ECU is in car simulation and if correct protocol
            if (self.ecuID in self.carECUList) and (self.carECUList[self.ecuID]["protocol"] == "kwp_is"):
                self.protocol = "kwp_is"
                return "C1D08F"
        if cmd == "82":
            self.protocol = ""
            self.ecuData = None
            return "C2"
        if cmd == "2783":
            return "67836B0A71E0"
        if cmd[:4] == "2784":
            return "6784"

        # KWP_HAB
        if cmd == "31A800":
            return "71A801"

        # Simulate Read/Write
        if self.protocol == "uds":
            return self.__simulateUDS(cmd)
        elif self.protocol == "kwp_is":
            return self.__simulateKWPIS(cmd)

        return "Timeout"

    def __loadECUCSV(self, path: str):
        code = "utf-8"
        while True:
            try:
                stream = open(os.path.join(os.path.dirname(__file__), str(path)), 'r', encoding=code)
            except OSError:
                return False

            try:
                self.ecuData = list(csv.reader(stream))
                return True
            except:
                if code == "utf-8":
                    code = "iso-8859-1"
                    continue;
                else:
                    return False

    def __simulateUDS(self, cmd: str):
        if self.ecuData == None:
            path = ""
            if self.ecuID in self.carECUList:
                path = self.carECUList[self.ecuID]["file"]

            if not self.__loadECUCSV(path):
                return "Timeout"

        if cmd[:2] == "22":
            if  cmd[2:6] == "2901":
                 return "62" + cmd[2:6] + "FD000000010101"
#            elif cmd[2:6] == "2104":
#                return "6221042300230123022303230423057F3E03"
            for item in self.ecuData:
                if item[0] == cmd[2:6]:
                    return "62" + cmd[2:6] + item[1]
            return "7F2231"
        elif cmd[:2] == "2E":
            if  cmd[2:6] == "2901":
                 return "6E" + cmd[2:6]
            for item in self.ecuData:
                if item[0] == cmd[2:6]:
                    item[1] = cmd[6:]
                    return "6E" + cmd[2:6]
            return "7F2E31"
        elif cmd[:8] == "14FFFFFF":
            return "54"

        return "Timeout"


    def __simulateKWPIS(self, cmd: str):
        if self.ecuData == None:
            path = ""
            if self.ecuID in self.carECUList:
                path = self.carECUList[self.ecuID]["file"]

            if not self.__loadECUCSV(path):
                return "Timeout"

        if cmd[:2] == "21":
            for item in self.ecuData:
                if item[0] == cmd[2:4]:
                    return "61" + cmd[2:4] + item[1]
            return "7F2112"
        elif cmd[:2] == "34":
            for item in self.ecuData:
                if item[0] == cmd[2:4]:
                    val = str(item[1])
                    item[1] = val[:4] + cmd[14:24] + val[14:]
                    return "7402"
            return "7F3412"

        return "Timeout"
