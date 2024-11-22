"""
   SeedKeyAlgorithm.py

   Copyright (C) 2020 - 2022 Ludwig V. <https://github.com/ludwig-v>
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

import numpy as np


class SeedKeyAlgorithm():
    debug = False;

    # Code grabbed from ludwig-v(Vluds) Github page and adapted for Python
    # https://github.com/ludwig-v/psa-seedkey-algorithm/tree/main
    def transform(self, data_msb, data_lsb, sec):
        data = np.int32((data_msb << 8) | data_lsb)
        neg = False
        val = 0
        if data & 0x8000:
            data -= 0x10000
            data *= -1
            neg = True

        rem = np.int32(data % sec[0])
        num = np.int32(data / sec[0])
        if neg:
            rem *= -1
            num *= -1

        dom1 = np.int32(np.int16(rem) * np.uint8(sec[2]))
        dom2 = np.int32(np.int16(num) * np.uint8(sec[1]))
        result = np.int32(dom1 - dom2)
        if result < 0:
            result += (sec[0] * sec[2]) + sec[1]

        if self.debug:
            print("  " + hex(sec[0]) + " " + hex(sec[1]) + " " + hex(sec[2]))
            print("  data   " + hex(data))
            print("  rem    " + hex(rem))
            print("  num    " + hex(num))
            print("  dom1   " + hex(dom1))
            print("  dom2   " + hex(dom2))
            print("  result " + hex(result))
        return int(result) & 0xFFFF

    # Code grabbed from ludwig-v(Vluds) Github page and adapted for Python
    # https://github.com/ludwig-v/psa-seedkey-algorithm/tree/main
    def computeResponse(self, pin, chg):
        sec_1 = [0xB2,0x3F,0xAA]
        sec_2 = [0xB1,0x02,0xAB]
        res_msb = self.transform((pin >> 8), (pin & 0xFF), sec_1) |                   \
                  self.transform(((chg >> 24) & 0xFF), (chg & 0xFF), sec_2)
        res_lsb = self.transform(((chg >> 16) & 0xFF), ((chg >> 8) & 0xFF), sec_1) |  \
                  self.transform((res_msb >> 8), (res_msb & 0xFF), sec_2);
        return ((res_msb & 0xFFFF) << 16) | (res_lsb & 0xFFFF);

    # Some Seed data to test algorithm
    def trySeed(self, t):
        print("Try " + str(t))
        match(t):
            case 1:
                calSeed = 0x5ADF35FE
                chg = 0x242F6A10
                key = 0x50A6
            case 2:
                calSeed = 0x59F77DC3
                chg = 0x6B0A71E0
                key = 0x50A6
            case 3:
                # Will fail
                calSeed = 0x7EEF679A
                chg = 0xDFE7EFAF
                key = 0xB4E0
            case 4:
                calSeed = 0x17D83D3F
                chg = 0x11BF5E67
                key = 0xD91C
            case 5:
                calSeed = 0x759F6DB3
                chg = 0x288071B2
                key = 0xB6F0
            case 6:
                calSeed = 0x56FC7F9B
                chg = 0x00370AD3
                key = 0xEFCA

        self.debug =  True
        seed = self.computeResponse(key, chg)
        if seed - calSeed != 0:
            print("    ** Failed caclulation **")
        print("    Known Seed " + hex(calSeed))
        print("    Calc  Seed " + hex(seed))
        self.debug =  False

    def testCalculations(self):
        self.trySeed(1)
        self.trySeed(2)
        self.trySeed(3)
        self.trySeed(4)
        self.trySeed(5)
        self.trySeed(6)


