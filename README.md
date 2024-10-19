# PyPSADiag

An Python application for configuring PSA/Stellantis based cars<br/>
See for additional Hardware/Info: [ludwig-v arduino-psa-diag](https://github.com/ludwig-v/arduino-psa-diag)

Currently supporting:

- JSON Configuration for BSI2010 to setup GUI</br> (Grabbed from: [forum-peugeot.com user weirdcactus](https://www.forum-peugeot.com/Forum/threads/tuto-t%C3%A9l%C3%A9codage-et-calibration-dun-nac-rcc-cirocco-cmb_num-sans-diagbox-via-arduino.121767/page-152#post-2739080))
- Reading Zones that are listed in JSON Configuration file
- Reading Zones with Multiple configurations, that are listed in JSON Configuration file
- Writing Zones to CSV file
- Writing changed Zones (as an list) to ECU

What I would like to support:
- [ludwig-v nac reverse engineering JSON file](https://github.com/ludwig-v/psa-nac-firmware-reverse-engineering/blob/main/Configuration/nac.json)

IMPORTANT!
-------
This application is as is, and you use it at your own risk.<br/>
I am not responsible for any damages or injuries resulting from the use of this application.

Help
-------
Help in any way is appreciated, just send me an email with anything you can
contribute to the project, like:
- more ECU JSON Files
- coding
- GUI design
- ideas / feature requests
- test reports
- spread the word!

Build
-----
- Install Python 3.12 or above
- Get code `git clone https://github.com/Barracuda09/PyPSADiag.git`
- Create virtual enviroment `python -m venv /path/to/PyPSADiag/.venv`
- Goto virtual enviroment with `/path/to/PyPSADiag/.venv/Script/activate`
- Install requirements, within path of PyPSADiag with `pip install -r requirements.txt`
- Change GUI:
	- `pyside6-designer PyPSADiag.ui`
- Build GUI:
	- `pyside6-uic PyPSADiag.ui -o ui_PyPSADiag.py`
- Run with:
	1. python `main.py`
	2. `Open Zone File` and select an ECU JSON file
	3. `Connect` to correct Arduino hardware
	4. `Read` Zones
	5. <b>RISK: The you can change Zones and use `Write` to write them to ECU.</b>

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
