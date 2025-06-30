"""
   translate.py

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
import subprocess
import sys, os

from i18n import i18n

class FileTranslater:

    def __init__(self):
        print("Translating...")

    # pathIn  = ./i18n/PyPSADiag_nl.qt.ts
    # pathOut = ./i18n/PyPSADiag_translated_nl.qt.ts
    def translate(self, pathIn, pathOut):
        if pathIn == pathOut:
            print("In and out paths are the same... ERROR")
            return

        treeOut = ElementTree.parse(pathOut)
        rootOut = treeOut.getroot()
        messagesOut = rootOut.findall(".//message")

        tree = ElementTree.parse(pathIn)
        root = tree.getroot()

        # Check destination language
        if "language" not in root.attrib:
            print("No destination language")
            return

        language = root.attrib["language"]
        messages = root.findall(".//message")
        for message in messages:
            txt = message.find("source").text.replace("\\", "")
            if txt != None:
                # Find if we already translated this i18n string
                translated = False
                for messageOut in messagesOut:
                    if messageOut.find("source").text.replace("\\", "") == txt:
                        translationOut = messageOut.find("translation")
                        if translationOut == None or "type" not in translationOut.attrib:
                            translated = True
                        break

                # Check if Input is correct
                translation = message.find("translation")
                if translation == None or "type" not in translation.attrib:
                    continue

                # Already translated, transfer to input tree
                if translated == True:
                    translation.text = translationOut.text
                    del translation.attrib["type"]
                    print("Done: " + translation.text)
                    continue

                txtTranslated = i18n().translate_text(str(txt), language)
                if txtTranslated != None:
                    translation.text = txtTranslated
                    del translation.attrib["type"]

                    print(txt + " - " + txtTranslated)

        # Write back
        tree.write(pathOut, encoding='utf-8', xml_declaration=True)

def printUsage():
    print("Usage: translate [OPTIONS]")
    print("")
    print("Mandatory Options:")
    print("  --input        ./i18n/PyPSADiag_[lang_code].qt.ts     Specifies the input ts file, for example: ./i18n/PyPSADiag_nl.qt.ts")
    print("  --releaseonly                                         Only release translation 'qm' file from input 'ts' file")
    print("")
    exit()

if __name__ == "__main__":
    releaseOnly = False
    if len(sys.argv) >= 3:
        inputTS = False
        for arg in sys.argv:
            if arg == "--input":
                inputTS = True;
            elif inputTS == True:
                inputTS = False
                inputTSName = arg;
            elif arg == "--releaseonly":
                releaseOnly = True
            elif arg == "--help":
                printUsage()
    else:
        printUsage();

    nameSplit = inputTSName.split("_")
    dirSplit = inputTSName.split("/")
    if len(nameSplit) != 2 or len(dirSplit) != 3:
        print("Not the correct format for input file name!")
        print("")
        printUsage()
        exit()
    outputTSName = nameSplit[0] + "_translated_" + nameSplit[1]

    # If output file does not exist, start with copy of input file
    if os.path.isfile(outputTSName) == False:
        print("Starting with 'empty' input file...")
        open(outputTSName, 'x')
        tree = ElementTree.parse(inputTSName)
        tree.write(outputTSName, encoding='utf-8', xml_declaration=True)

    # Get output file name an
    nameSplit = dirSplit[2].split(".")
    qmName = dirSplit[0] + "/" + dirSplit[1] + "/translations/" + nameSplit[0] + ".qm"

    if releaseOnly == False:
        print(f"Translating:")
        print(f" {inputTSName}  --->  {outputTSName}")
        translate = FileTranslater()
        translate.translate(inputTSName, outputTSName)

    print(f"Releasing:")
    print(f" {outputTSName}  --->  {qmName}")
    print(f"")
    subprocess.run(f"pyside6-lrelease {outputTSName} -qm {qmName}".split(" "))

