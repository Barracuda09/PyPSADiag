"""
   FileConverter.py

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
import sys

class FileConverter:

    def __init__(self):
        print("Converting...")

    # pathIn  = ./json/test_nac_original.json
    # pathOut = ./json/test_nac_conv.json
    def convertNAC(self, pathIn, pathOut):
        if pathIn == pathOut:
            print("In and out paths are the same... ERROR")
            return

        file = open(pathIn, 'r', encoding='utf-8')
        jsonFile = file.read()
        self.ecuObjectList = json.loads(jsonFile.encode("utf-8"))

        # Converter
        for zoneID in self.ecuObjectList["NAC"]["zones"]:
            zone = self.ecuObjectList["NAC"]["zones"][zoneID]
            if "params" in zone:
                zone["tab"] = "telemat"
                zone["type"] = "raw"
                zone["form_type"] = "multi"
                zone["params"] = zone.pop("params")
                for param in zone["params"]:
                    param.pop("size")
                    param["name_original"] = param.pop("name")
                    param["name"] = param["detail"]["en"]
                    param.pop("detail")
                    param["byte"] = int(param["pos"]) - 4
                    param.pop("pos")
                    param.pop("mask")
                    param["mask"] = param.pop("maskBinary")
                    if "listbox" in param:
                        param["form_type"] = "combobox"
                        param["params"] = param.pop("listbox")
                        for item in param["params"]:
                            item["mask"] = '{0:08b}'.format(int(item["value"], 16))
                            item["name"] = item["text"]["en"]
                            item.pop("text")
                            item.pop("value")
                    else:
                        mask = int(param["mask"], 2)
                        if mask.bit_count() > 1:
                            param["type"] = "raw"
                            param["form_type"] = "string"
                        else:
                            param["form_type"] = "checkbox"
                            param["available_logic"] = "active_high"

            else:
                print("Need to handle this!!")

        self.ecuObjectList = self.ecuObjectList.pop("NAC")
        self.ecuObjectList.pop("VIN")
        self.ecuObjectList.pop("SN")
        self.ecuObjectList["name"] = "telemat_nac_rcc"
        self.ecuObjectList["tx_id"] = "764"
        self.ecuObjectList["rx_id"] = "664"
        self.ecuObjectList["protocol"] = "uds"
        self.ecuObjectList["key_type"] = "multi"
        keys = {"NAC": "D91C", "RCC": "D91C" }
        tabs = {"telemat": "Telematic Unit (BTEL)"}
        self.ecuObjectList["keys"] = keys
        self.ecuObjectList["tabs"] = tabs
        self.ecuObjectList["zones"] = self.ecuObjectList.pop("zones")
        # Converter

        wFile = open(pathOut, 'w', encoding='utf-8')
        json.dump(self.ecuObjectList, wFile, ensure_ascii=False, indent=2)

    # pathIn  = ./json/test_CIROCCO_original.json
    # pathOut = ./json/test_CIROCCO_conv.json
    def convertCIROCCO(self, pathIn, pathOut):
        if pathIn == pathOut:
            print("In and out paths are the same... ERROR")
            return

        file = open(pathIn, 'r', encoding='utf-8')
        jsonFile = file.read()
        self.ecuObjectList = json.loads(jsonFile.encode("utf-8"))

        # Converter
        for zoneID in self.ecuObjectList["CIROCCO"]["zones"]:
            zone = self.ecuObjectList["CIROCCO"]["zones"][zoneID]
            if "params" in zone:
                zone["tab"] = "cmb"
                zone["type"] = "raw"
                zone["form_type"] = "multi"
                zone["params"] = zone.pop("params")
                for param in zone["params"]:
                    param.pop("size")
                    param["name_original"] = param.pop("name")
                    param["name"] = param["detail"]["en"]
                    param.pop("detail")
                    param["byte"] = int(param["pos"]) - 4
                    param.pop("pos")
                    param.pop("mask")
                    param["mask"] = param.pop("maskBinary")
                    if "listbox" in param:
                        param["form_type"] = "combobox"
                        param["params"] = param.pop("listbox")
                        for item in param["params"]:
                            item["mask"] = '{0:08b}'.format(int(item["value"], 16))
                            item["name"] = item["text"]["en"]
                            item.pop("text")
                            item.pop("value")
                    else:
                        mask = int(param["mask"], 2)
                        if mask.bit_count() > 1:
                            param["type"] = "raw"
                            param["form_type"] = "string"
                        else:
                            param["form_type"] = "checkbox"
                            param["available_logic"] = "active_high"

            else:
                print("Need to handle this!!")

        self.ecuObjectList = self.ecuObjectList.pop("CIROCCO")
        self.ecuObjectList.pop("SN")
        self.ecuObjectList["name"] = "combine"
        self.ecuObjectList["tx_id"] = "75F"
        self.ecuObjectList["rx_id"] = "65F"
        self.ecuObjectList["protocol"] = "uds"
        self.ecuObjectList["key_type"] = "multi"
        keys = {"CIROCCO": "FAFA" }
        tabs = {"cmb": "Instrument Panel CIROCCO"}
        self.ecuObjectList["keys"] = keys
        self.ecuObjectList["tabs"] = tabs
        self.ecuObjectList["zones"] = self.ecuObjectList.pop("zones")
        # Converter

        wFile = open(pathOut, 'w', encoding='utf-8')
        json.dump(self.ecuObjectList, wFile, ensure_ascii=False, indent=2)
