import sys
from SerialPort import SerialPort
from VCIAdapter import VCIAdapter
from BluetoothAdapter import BluetoothAdapter

class DiagnosticAdapter:

    def __init__(self, logger=None, mode="serial", **kwargs):
        self.logger = logger

        if mode == "serial":
            simulation = kwargs.get("simulation", False)
            self.transport = SerialPort(logger=self.logger, simulation=simulation)

        elif mode == "vci" and sys.platform == "win32":
            self.transport = VCIAdapter(logger=self.logger)

        elif mode == "bluetooth":
            self.transport = BluetoothAdapter(logger=self.logger)

        else:
            raise ValueError("Unknown transport")

    def __getattr__(self, name):
        return getattr(self.transport, name)
