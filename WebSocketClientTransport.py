#from socket import timeout
import time

import websocket
import threading
import queue
from PySide6.QtWidgets import QApplication

class WebSocketClientTransport:
    def __init__(self, logger=None, url=""):
        self.logger = logger
        self.url = url
        self.ws = None
        self._thread = None
        self._rx_queue = queue.Queue()
        self._open = False

    def __del__(self):
        self.close()

    def isOpen(self):
        return self._open

    def open(self, portNr=None, baudRate=None, timeout=5.0):
        if self._open:
            return ""

        # Create an event to signal when the connection is established
        self._connection_event = threading.Event()

        def on_message(ws, message):
            self._rx_queue.put(message)

        def on_open(ws):
            self._open = True
            self._connection_event.set()  # Trigger the "switch"

        def on_close(ws, close_status_code, close_msg):
            self._open = False
            self._connection_event.clear()

        def on_error(ws, error):
            if self.logger:
                print(f"WebSocket Error: {error}")
                #self.logger(f"WebSocket Error: {error}")

        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=on_message,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error
        )

        self._thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._thread.start()

        start_time = time.time()
        while not self._open:
            # Check for timeout
            if time.time() - start_time > timeout:
                self.close()
                # This forces the background thread to stop the OS connect attempt
                if self.ws:
                    self.ws.keep_running = False # Tell the loop to stop
                    self.ws.close()             # Close the socket

                # Don't leave the thread hanging
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=1.0)

                return f"Failed to connect to {self.url} within {timeout}s"

            # This small sleep allows the OS and other threads to breathe
            time.sleep(0.1)

            QApplication.processEvents()

        return ""

    def close(self):
        if self.ws:
            # This triggers the websocket loop to stop
            self.ws.close()

        if self._thread and self._thread.is_alive():
            # Wait for the thread to actually finish
            self._thread.join(timeout=2.0)

        self._open = False
        self.ws = None

    def configure(self, tx_id, rx_id, protocol="uds", bus="DIAG", target=None, dialog_type="0"):
        return True

    def write(self, data):
        if not self._open:
            raise RuntimeError("WebSocket not open")
        self.ws.send(data)

    def readData(self, timeout=5):
        try:
            if timeout is None:
                timeout = 5
            # .get() is blocking by default.
            # It will wait until an item is available or 'timeout' seconds pass.
            end_time = time.time() + timeout
            while time.time() < end_time:
                message = self._rx_queue.get(block=True, timeout=timeout)
                if message is not None:
                    # If the message is a string, strip \r and \n from both ends
                    if isinstance(message, str):
                        return message.strip("\r\n ")

                    # If it's binary (bytes), you can still strip it
                    if isinstance(message, bytes):
                        return message.strip(b"\r\n ")

                    return message

            return "Timeout"
            #message = self._rx_queue.get(block=True, timeout=timeout)
            #if message is None:
                #return None

        except queue.Empty:
            # This triggers if the timeout is reached and the queue is still empty
            #if self.logger:
                #self.logger("Read timeout reached")
            print("Read timeout reached")
            return "Timeout"

    def sendReceive(self, data, timeout=None):
        # Clear existing messages in queue
        while not self._rx_queue.empty():
            try:
                self._rx_queue.get_nowait()
            except queue.Empty:
                break

        self.write(data)
        return self.readData(timeout)