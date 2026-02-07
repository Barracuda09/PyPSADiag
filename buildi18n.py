"""
   buildi18n.py

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

import xml.etree.ElementTree as ElementTree
import sys, os, json, subprocess, re
from pathlib import Path

def geti18nString(line: str):
    nameGroup = re.search(r'"name".*:.*".*"', line)
    if nameGroup == None:
        if line.find(":") != -1:
            valueGroup = re.search(r':.*"(.*)"', line)
        else:
            valueGroup = re.search(r'.*(".*")', line)
        stringValue = valueGroup.group().strip(": ")
    else:
        valueGroup = re.search(r':.*"(.*)"', nameGroup.group())
        stringValue = valueGroup.group().strip(": ")
    return stringValue[1:len(stringValue) - 1]

def processJSONFile(pathIn: str, i18nList: []):

    with open(pathIn, 'r', encoding='utf-8') as file:
        linenr = 0
        tabFound = False
        for line in file:
            linenr += 1
            # find 'tabs' to translate
            if line.find("\"tabs\"") != -1:
                tabFound = True
                continue
            elif tabFound:
                # end '}' found continue
                if line.find("}") != -1:
                    tabFound = False
                    continue
            # Not 'name' continue
            elif line.find("\"name\"") == -1:
                continue

            # Check if the line has more then CR/LF
            if len(line) <= 2:
                continue

            # We found an i18n string we need to mark
            fileDict = {}
            fileDict["file"] = pathIn
            fileDict["line"] = linenr
            i18nName = geti18nString(line).replace("\\", "")
            print(i18nName)
            added = False
            # i18n String already there? then add only file name and line number
            for item in i18nList:
                if i18nName == item.get("i18n"):
                    item["file"].append(fileDict)
                    added = True
                    break

            # If i18n String is not there add new item
            if added == False:
                itemDict = {}
                itemDict["i18n"] = i18nName
                itemDict["file"] = []
                itemDict["file"].append(fileDict)
                i18nList.append(itemDict)

def addi18nListToTS(pathIn: str, i18nList: []):
    tree = ElementTree.parse(pathIn)
    root = tree.getroot()
    context = root.find(".//context")
    for item in i18nList:
        i18nSource = item.get("i18n")
        message = ElementTree.Element("message")
        message.tail = "\n    "
        for file in item.get("file"):
            name = os.path.relpath(file.get("file"), start=os.getcwd())
            line = file.get("line")
            location = ElementTree.SubElement(message, "location", filename = f"../{name}", line = str(line))
        source = ElementTree.SubElement(message, "source")
        source.text = i18nSource
        translation = ElementTree.SubElement(message, "translation", type = "unfinished")
        ElementTree.indent(message, space="    ", level=1)

        context.append(message)

    # Write back
    tree.write(pathIn, encoding='utf-8', xml_declaration=True)

def printUsage():
    print("Usage: translate [OPTIONS]")
    print("")
    print("Options:")
    print("  --help  Show this message")
    print("")
    print("Mandatory Options:")
    print("  --lang  Specifies the language code for example: nl or pl")
    print("")
    exit()

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        lang = False
        for arg in sys.argv:
            if arg == "--lang":
                lang = True;
            elif lang == True:
                lang = False
                langCode = arg;
            elif arg == "--help":
                printUsage()
    else:
        printUsage();

    files = "EcuMultiZoneTreeWidgetItem.py EcuZoneTreeView.py EcuZoneTreeWidgetItem.py PyPSADiagGUI.py DiagnosticCommunication.py main.py"
    subprocess.run(f"pyside6-lupdate {files} -source-language en_EN -ts ./i18n/PyPSADiag_{langCode}.qt.ts".split(" "))

    i18nList = []

    path = Path(os.path.join(os.path.dirname(__file__), "json"))
    for file in path.rglob("*.json"):
        if str(file).find("test") != -1 or str(file).find("SCAN") != -1:
            continue
        print(file)
        processJSONFile(str(file), i18nList)

    path = Path(os.path.join(os.path.dirname(__file__), "data"))
    for file in path.rglob("*.json"):
        if str(file).find("ECU_SUPPLIERS.json") != -1:
            continue
        print(file)
        processJSONFile(str(file), i18nList)

    addi18nListToTS(f"./i18n/PyPSADiag_{langCode}.qt.ts", i18nList)
