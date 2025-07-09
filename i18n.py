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

    def translate_text(self, text, dest: str):
        #self.translator = GoogleTranslator(service_urls=['translate.google.com'])
        self.translator = GoogleTranslator()
        return asyncio.run(self.__async_translate_text(text, dest))

    async def __async_translate_text(self, text, dest: str):
        resultList = await self.translator.translate(text, dest=dest, src="en")
        if isinstance(resultList, list):
            text = []
            for result in resultList:
                text.append(result.text)
            return text
        else:
            return resultList.text

    def tr(self, text: str):
        #return text
        #return self.translate_text(text, "nl")[0]
        return str(QCoreApplication.translate("", text))

