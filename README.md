# PyPSADiag

**IMPORTANT!**
-------
This application is as is, and you use it **at your own risk**.<br/>
I am not responsible for any damages or injuries resulting from the use of this application.<br/>
**VERY IMPORTANT:** This application is for **educational** purposes only **and should be used with care!.**

-------

PyPSADiag is an Python application for sending diagnostic frames over CAN-BUS to PSA/Stellantis based cars <br/>
See for additional Hardware/Info: [ludwig-v arduino-psa-diag](https://github.com/ludwig-v/arduino-psa-diag)

Currently supporting:

- JSON Configuration for example BSI2010 to setup GUI<br/>[See more JSON Configuration Files](https://github.com/Barracuda09/PyPSADiag/tree/main/json)
- Reading Zones that are listed in JSON Configuration file
- Saving Zones to CSV file
- Saving changed Zones (as an list) to ECU

What I would like to support:
- More ECU JSON Files

Help
-------
Help in any way is appreciated, just send me an email with anything you can
contribute to the project, like:
- More ECU JSON Files
- Python coding
- GUI design
- ideas / feature requests
- test reports
- spread the word!

Use a Release
-----
- Get release a from [Download Release](https://github.com/Barracuda09/PyPSADiag/releases) There is Windows, Linux and macOS versions
- Extract archive to your hardrive
- Run with PyPSADiag-windows.exe or any other distibution you downloaded:
	1. `PyPSADiag-windows.exe --lang nl`
	2. `Open Zone File` and select an ECU JSON file
	3. `Connect` to correct Arduino hardware
	4. `Read` Zones
	5. <b> **RISK:** You can save the Zones to the ECU by using the `Write` Button.<br/> **Always Check that these zones look correct** </b>

Build Yourself
-----
- Install Python 3.12 or above
- Get code `git clone https://github.com/Barracuda09/PyPSADiag.git`<br>
  OR use this [Download ZIP](https://github.com/Barracuda09/PyPSADiag/archive/refs/heads/main.zip)
- Enter created directory `cd /path/to/PyPSADiag`
- Create virtual environment `python -m venv .venv --prompt PyPSADiag`
- Activate your virtual environment with `source .venv/Script/activate`
- Install requirements, within path of PyPSADiag with `pip install -r requirements.txt`
- Run with:
	1. `python main.py --lang nl`
	2. `Open Zone File` and select an ECU JSON file
	3. `Connect` to correct Arduino hardware
	4. `Read` Zones
	5. <b> **RISK:** You can save the Zones to the ECU by using the `Write` Button.<br/> **Always Check that these zones look correct** </b>


Make Translations
------

For example to make a translation for Dutch use this command:
- `python buildi18n.py --lang nl` --> Build the qt.ts file
- `python translate.py --input ./i18n/PyPSADiag_nl.qt.ts` --> Google Translate
- `pyside6-linguist ./i18n/PyPSADiag_translated_nl.qt.ts` --> Correct translation if required
- `python translate.py --releaseonly --input ./i18n/PyPSADiag_nl.qt.ts` --> Only Release translation qm file
- `python main.py --lang nl` --> Run with nl language

Donate
------

If you like my work then please consider making a donation, to support my effort in
developing this application.<br>
Many thanks to all who donated already.<br>

| PayPal |
|-------|
|  [![PayPal](https://img.shields.io/badge/donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=H9AX9N7HWSWXE&item_name=PSADiag&item_number=PSADiag&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted) |

Contact
-------
If you like to contact me, you can do so by sending an email to:

    mpostema09 -at- gmail.com
