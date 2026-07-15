import sys
from WebSocketClientTransport import WebSocketClientTransport
from SerialPort import SerialPort
from VCIAdapter import VCIAdapter
from BluetoothAdapter import BluetoothAdapter

class DiagnosticAdapter:

    def __init__(self, logger=None, mode="serial", **kwargs):
        print(f"Initializing DiagnosticAdapter with mode: {mode}")
        self.logger = logger

        if mode == "serial":
            simulation = kwargs.get("simulation", False)
            self.transport = SerialPort(logger=self.logger, simulation=simulation)

        elif mode == "vci" and sys.platform == "win32":
            self.transport = VCIAdapter(logger=self.logger)

        elif mode == "bluetooth":
            self.transport = BluetoothAdapter(logger=self.logger)

        elif mode == "websocket":
            ipAddress = kwargs.get("ipAddress", "192.168.100.1")
            url = "ws://" + ipAddress + "/ws"
            print(f"Using WebSocket URL: {url}")
            self.transport = WebSocketClientTransport(logger=self.logger, url=url)

        else:
            raise ValueError("Unknown transport")

    def __getattr__(self, name):
        return getattr(self.transport, name)
