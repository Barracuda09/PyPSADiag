"""
   i18n.py

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

import asyncio
from PySide6.QtCore import QCoreApplication
from googletrans import Translator as GoogleTranslator

class i18n():

    def __init__(self):
        self.translator = GoogleTranslator()
        self.trans = True;

    def translate_text(self, text: str):
        return asyncio.run(self.async_translate_text(text))

    async def async_translate_text(self, text: str):
        print("Translate")
        result = await self.translator.translate(text, dest="de")
        print(str(result.text))
        return str(result.text)

    def tr(self, text: str):
        #return text
        #return self.translate_text(text)
        return str(QCoreApplication.translate("", text))

