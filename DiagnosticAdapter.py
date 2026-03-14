
from SerialPort import SerialPort
from VCIAdapter import VCIAdapter

class DiagnosticAdapter:

    def __init__(self, logger=None, mode="serial", **kwargs):
        self.logger = logger

        if mode == "serial":
            simulation = kwargs.get("simulation", False)
            self.transport = SerialPort(logger=self.logger, simulation=simulation)

        elif mode == "vci":
            url = kwargs.get("url", "ws://localhost:8765")
            self.transport = VCIAdapter(logger=self.logger, url=url)

        else:
            raise ValueError("Unknown transport")

    def __getattr__(self, name):
        return getattr(self.transport, name)