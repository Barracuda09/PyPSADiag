"""
   BluetoothAdapter.py

   ELM327 Bluetooth OBD Adapter for PyPSADiag
   Communicates with ELM327-based Bluetooth OBD scanners via virtual COM port

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or (at your option) any later version.
"""

import threading
import time
import serial
import serial.tools.list_ports


class BluetoothAdapter:
    """
    ELM327 Bluetooth OBD Adapter
    Translates PyPSADiag commands to ELM327 AT command protocol
    """

    # Common baud rates for ELM327 adapters (most popular first)
    BAUD_RATES = [230400, 115200, 57600, 38400, 19200, 9600]

    # ELM327 AT ST timing (hex, units ≈ 4.096 ms).
    # Lower = faster per-frame return, but more NO DATA on slow ECUs.
    # A/B-tunable from one place.
    #   "10" = 0x10 = 16 dec × 4.096 ≈  65 ms  (aggressive)
    #   "20" = 0x20 = 32 dec × 4.096 ≈ 131 ms  (compromise fallback)
    #   "32" = 0x32 = 50 dec × 4.096 ≈ 205 ms  (conservative, original)
    AT_ST_NORMAL = "19"     # main per-frame timeout
    AT_ST_CF_RAPID = "05"   # ~20 ms between intermediate CFs (all NO DATA)

    def __init__(self, logger=None, **kwargs):
        self.logger = logger
        self.serialPort = serial.Serial()
        self.connected = False
        self.configured = False
        self.current_tx_id = ""
        self.current_rx_id = ""
        self.elm_version = ""
        self.detected_baud = None
        self._raw_can_supported = True

        # ─── Keep-alive infrastructure ──────────────────────────────
        # RLock so sendReceive → configure nests cleanly (both take the
        # lock, same thread is allowed to re-enter). Serializes ALL
        # serialPort I/O between the GUI worker thread
        # (sendReceive/readData/configure) and the background keep-alive
        # thread. Low-level helpers (_send_at, _send_uds) do NOT re-acquire.
        self._io_lock = threading.RLock()
        self._ka_thread = None
        self._ka_stop = threading.Event()
        self._ka_period = 2.0  # seconds — covers UDS S3 (5s), BT idle, ELM sleep

    def log(self, message, ui=False):
        """Log message. ui=True forwards to GUI logger, but ONLY from the
        main thread — the logger (writeToOutputView) calls
        QTextEdit.append() + viewport().repaint() synchronously, which
        corrupts Qt paint state and crashes if invoked from a worker
        thread (e.g. DiagnosticCommunication's QThread during a read).
        From worker threads we silently drop the UI forward and keep the
        console print."""
        log_msg = f"[BT] {message}"
        print(log_msg)
        if ui and self.logger and \
                threading.current_thread() is threading.main_thread():
            self.logger(log_msg)

    # ─── Port Management ─────────────────────────────────────────

    def fillPortNameCombobox(self, combobox):
        """Scan COM ports and auto-detect ELM327 Bluetooth adapters"""
        combobox.clear()
        comPorts = serial.tools.list_ports.comports()

        bt_ports = []
        other_ports = []

        for port in comPorts:
            is_bt = "BTHENUM" in (port.hwid or "").upper() or \
                    "BLUETOOTH" in (port.description or "").upper()

            if is_bt:
                bt_ports.append(port)
            else:
                other_ports.append(port)

        self.log(f"Found {len(bt_ports)} Bluetooth port(s), {len(other_ports)} other port(s)", ui=True)

        # Try to auto-detect ELM327 on Bluetooth ports
        for port in bt_ports:
            self.log(f"Scanning {port.device} ({port.description})...", ui=True)
            baud, version = self._probe_elm327(port.device)
            if baud:
                label = f"{port.device} - ELM327 [{version}] @ {baud} baud"
                # Store both port name and detected baud rate
                combobox.addItem(label, f"{port.device}:{baud}")
                self.log(f"  Found ELM327: {version} @ {baud}", ui=True)
            else:
                label = f"{port.device} - {port.description or 'Bluetooth'} (no response)"
                combobox.addItem(label, f"{port.device}:0")
                self.log(f"  No ELM327 response", ui=True)

        # Also list other ports (user might have a USB Bluetooth dongle)
        for port in other_ports:
            label = f"{port.device} - {port.description or 'Unknown'}"
            combobox.addItem(label, f"{port.device}:0")

    def _probe_elm327(self, port_name):
        """Try to detect ELM327 on a port by sending ATZ at different baud rates.
           Returns (baud_rate, version_string) or (None, None)"""
        test_port = serial.Serial()
        test_port.port = port_name
        test_port.timeout = 1.5
        test_port.write_timeout = 1.5

        for baud in self.BAUD_RATES:
            try:
                test_port.baudrate = baud
                test_port.open()
                time.sleep(0.3)

                # Flush any garbage
                test_port.reset_input_buffer()

                # Send ATZ (reset) and look for "ELM" in response
                test_port.write(b"ATZ\r")
                test_port.flush()

                # Read response
                data = bytearray()
                end = time.monotonic() + 2.0
                while time.monotonic() < end:
                    n = test_port.in_waiting
                    if n:
                        data.extend(test_port.read(n))
                        if b">" in data:
                            break
                    else:
                        time.sleep(0.01)

                test_port.close()

                if data:
                    response = data.decode("utf-8", errors="ignore")
                    if "ELM" in response.upper():
                        # Extract version string
                        for line in response.split("\r"):
                            line = line.strip()
                            if "ELM" in line.upper():
                                return baud, line
                        return baud, "ELM327"

            except (serial.SerialException, OSError):
                pass
            finally:
                if test_port.isOpen():
                    test_port.close()

        return None, None

    # ─── Connection ───────────────────────────────────────────────

    def open(self, portNr, baudRate=None):
        """Connect to ELM327 via Bluetooth COM port"""
        try:
            # Parse port:baud if provided by fillPortNameCombobox
            detected_baud = None
            if isinstance(portNr, str) and ":" in portNr:
                portNr, baud_str = portNr.rsplit(":", 1)
                if baud_str.isdigit() and int(baud_str) > 0:
                    detected_baud = int(baud_str)

            self.serialPort.port = portNr
            self.serialPort.timeout = 3.0
            self.serialPort.write_timeout = 3.0

            # If baud rate was detected during scan, use it directly
            if detected_baud:
                self.log(f"Connecting to {portNr} @ {detected_baud} baud (auto-detected)", ui=True)
                self.serialPort.baudrate = detected_baud
                self.serialPort.open()
                time.sleep(0.5)

                if self._init_elm327():
                    self.connected = True
                    self.detected_baud = detected_baud
                    return ""
                else:
                    self.serialPort.close()

            # Auto-detect baud rate by trying each one
            self.log(f"Auto-detecting baud rate on {portNr}...", ui=True)
            for baud in self.BAUD_RATES:
                try:
                    self.log(f"  Trying {baud} baud...", ui=True)
                    self.serialPort.baudrate = baud
                    if not self.serialPort.isOpen():
                        self.serialPort.open()
                    time.sleep(0.3)

                    if self._init_elm327():
                        self.connected = True
                        self.detected_baud = baud
                        self.log(f"Connected @ {baud} baud", ui=True)
                        return ""

                    self.serialPort.close()
                except serial.SerialException:
                    if self.serialPort.isOpen():
                        self.serialPort.close()
                    continue

            return "ELM327 not found: no response at any baud rate"

        except serial.SerialException as e:
            return f"Error opening Bluetooth port: {str(e)}"

    def close(self):
        """Disconnect from ELM327"""
        # Stop keep-alive thread BEFORE touching the serial port, so we don't
        # race with a keep-alive tick that's mid-write.
        self._stop_keep_alive()
        if self.serialPort.isOpen():
            try:
                # Reset ELM327 before closing
                self._send_at("ATZ", timeout=3)
            except Exception:
                pass
            self.serialPort.close()
        self.connected = False
        self.configured = False
        return True

    def isOpen(self):
        """Check if connected to ELM327"""
        return self.serialPort.isOpen() and self.connected

    def is_configured(self):
        """Check if ELM327 is configured for CAN communication"""
        return self.configured

    # ─── ELM327 Initialization ────────────────────────────────────

    def _init_elm327(self):
        """Initialize ELM327 with required AT commands"""
        # Reset
        response = self._send_at("ATZ", timeout=3)
        if response is None:
            self.log("ELM327 not responding")
            return False

        # Store ELM version
        self.elm_version = response.strip()
        self.log(f"ELM327 version: {self.elm_version}")

        # Basic configuration
        # CAF0 + CFC0: we handle ISO-TP framing and flow control manually
        # in Python, because ELM327 auto-FC doesn't work for non-standard
        # CAN IDs (PSA uses 0x764/0x664 instead of OBD 0x7E0-0x7E7).
        init_commands = [
            ("ATE0",    "Echo off"),
            ("ATL0",    "Linefeeds off"),
            ("ATS0",    "Spaces off"),
            ("ATH0",    "Headers off"),
            ("AT CAF0", "CAN auto-formatting off (manual ISO-TP)"),
            ("AT CFC0", "CAN flow control off (manual FC)"),
            ("AT SP 6", "Protocol: ISO 15765-4 CAN 500kbps 11-bit"),
        ]

        for cmd, description in init_commands:
            response = self._send_at(cmd)
            if response is None:
                self.log(f"Failed: {description} ({cmd})")
                return False
            self.log(f"OK: {description}")

        # Disable ELM327 low-power mode (non-fatal — many clones answer '?').
        # Prevents the adapter from auto-sleeping after ~15 min of idle,
        # which is one of the root causes of post-idle Write timeout.
        lp_resp = self._send_at("AT LP 0")
        if lp_resp is None or "?" in (lp_resp or ""):
            self.log("AT LP 0 not supported (clone) — ignoring")
        else:
            self.log("OK: Low-power mode disabled")

        return True

    # ─── Configuration ────────────────────────────────────────────

    def configure(self, tx_id, rx_id, protocol="uds", bus="DIAG", target=None, dialog_type="0"):
        """Configure ELM327 for ECU communication.

        Takes self._io_lock so the background keep-alive thread can't
        interleave writes. RLock lets sendReceive('R') re-enter safely."""
        if not self.connected:
            self.log("Not connected")
            return False

        with self._io_lock:
            self.current_tx_id = tx_id
            self.current_rx_id = rx_id

            # Set CAN protocol based on PyPSADiag protocol
            protocol_lower = protocol.lower()
            if protocol_lower in ("uds", "kwp_is", "kwp_hab"):
                # ISO 15765-4 CAN 500kbps 11-bit
                self._send_at("AT SP 6")
            elif protocol_lower in ("kwp2000", "psa2000"):
                # User-defined protocol may be needed
                self._send_at("AT SP B")

            # Set transmit CAN ID (header)
            response = self._send_at(f"AT SH {tx_id}")
            if response is None or "ERROR" in (response or ""):
                self.log(f"Failed to set TX ID: {tx_id}")
                return False

            # Set receive CAN ID filter (software) + hardware CAN filter/mask
            response = self._send_at(f"AT CRA {rx_id}")
            if response is None or "ERROR" in (response or ""):
                self.log(f"Failed to set RX filter: {rx_id}")
                return False
            # Hardware CAN acceptance filter — blocks non-matching frames at chip level,
            # critical on busy CAN buses (e.g. BSI body CAN) to prevent buffer overflow
            self._send_at(f"AT CF {rx_id}")   # CAN Filter = exact RX ID
            self._send_at("AT CM 7FF")        # CAN Mask = all 11 bits must match

            # Flow control is handled manually in _send_uds / _parse_isotp_response
            # (AT CFC0 set in init — ELM327 auto-FC doesn't work for non-OBD CAN IDs)

            # Timing: short ST so ELM327 quickly returns First Frame to us,
            # leaving enough time to send Flow Control before ECU's N_BS timeout (1000ms).
            # Value comes from class constant AT_ST_NORMAL (see top of class).
            # Default "10" ≈ 65 ms — enough for fast ECUs; slow ECUs retry.
            self._send_at("AT AT0")   # Adaptive timing OFF
            self._send_at(f"AT ST {self.AT_ST_NORMAL}")

            self.configured = True
            self.log(f"Configured: TX={tx_id} RX={rx_id} protocol={protocol}")
            return True

    # ─── Communication ────────────────────────────────────────────

    def sendReceive(self, data, timeout=1500):
        """Send command to ECU and receive response.

        All serial I/O goes through self._io_lock so the background
        keep-alive thread can safely interleave TesterPresent writes
        between user commands."""
        if not self.connected:
            return ""

        # K*/S are keep-alive life-cycle signals from DiagnosticCommunication.
        # Handle them OUTSIDE the lock so _start/_stop can manage the thread
        # cleanly (stop joins the thread, which itself needs the lock briefly).
        if data.startswith("K"):
            self._start_keep_alive()
            return "OK"
        elif data == "S":
            self._stop_keep_alive()
            return "OK"

        with self._io_lock:
            # Handle Arduino-specific commands (same approach as VCIAdapter)
            if data.startswith(">") and ":" in data:
                # Arduino ECU selection ">6B4:694" - already configured via configure()
                self.log("ECU already configured, skipping Arduino command")
                return "OK"
            elif data.startswith("L"):
                self.log("LIN not supported on ELM327 OBD")
                return "OK"
            elif data == "R":
                # Reset - re-init ELM327. configure() re-acquires the
                # RLock safely (same thread → recursive allow).
                self._init_elm327()
                if self.current_tx_id and self.current_rx_id:
                    self.configure(self.current_tx_id, self.current_rx_id)
                return "OK"
            elif data == "V":
                # Version request
                return self.elm_version or "ELM327 Bluetooth"

            # Regular UDS command
            return self._send_uds(data, timeout)

    def readData(self):
        """Read next response from ECU (for Response Pending / NRC 78 handling).
           Uses AT MA to monitor CAN bus for the ECU's delayed response."""
        with self._io_lock:
            try:
                self.serialPort.reset_input_buffer()
                self.serialPort.write(b"ATMA\r")
                self.serialPort.flush()

                frame = self._read_monitor_frame(timeout=6.0)
                self._stop_monitor()

                if frame is None:
                    return "Timeout"

                return self._parse_isotp_response(frame, 3.0)
            except Exception as e:
                self.log(f"readData error: {e}")
                self._stop_monitor()
                return "Timeout"

    def _read_monitor_frame(self, timeout=6.0):
        """Read a single valid ISO-TP response frame from AT MA monitor mode.
           Skips NRC 78 (Response Pending) — waits for the real answer."""
        buf = bytearray()
        end = time.monotonic() + timeout

        while time.monotonic() < end:
            n = self.serialPort.in_waiting
            if n:
                buf.extend(self.serialPort.read(n))
                text = buf.decode("utf-8", errors="ignore")
                for line in text.split("\r"):
                    cleaned = line.strip().replace(" ", "")
                    if not cleaned or len(cleaned) < 4 or len(cleaned) % 2 != 0:
                        continue
                    if not all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                        continue
                    cleaned = cleaned.upper()
                    first_byte = int(cleaned[0:2], 16)
                    ft = (first_byte >> 4) & 0x0F

                    if ft == 0:  # Single Frame
                        dl = first_byte & 0x0F
                        if 0 < dl <= 7:
                            data = cleaned[2:2 + dl * 2]
                            # Skip another NRC 78 (Response Pending)
                            if len(data) >= 6 and data[0:2] == "7F" and data[4:6] == "78":
                                continue
                            return cleaned
                    elif ft == 1:  # First Frame (multi-frame response)
                        return cleaned
            else:
                time.sleep(0.01)

        return None

    def _stop_monitor(self):
        """Stop AT MA / AT MR monitoring mode"""
        try:
            self.serialPort.write(b"\r")
            time.sleep(0.1)
            self.serialPort.reset_input_buffer()
        except Exception:
            pass

    # ─── Low-level ELM327 Communication ──────────────────────────

    def _send_at(self, command, timeout=2):
        """Send AT command to ELM327 and return response"""
        try:
            self.serialPort.reset_input_buffer()
            cmd = command + "\r"
            self.serialPort.write(cmd.encode("utf-8"))
            self.serialPort.flush()
            return self._read_elm_response(timeout)
        except Exception as e:
            self.log(f"AT command error ({command}): {e}")
            return None

    def _send_uds(self, data, timeout=1500):
        """Send UDS hex data to ECU via ELM327 with manual ISO-TP framing.
           AT CAF0 + AT CFC0: we build SF frames and handle FC ourselves."""
        try:
            data_len = len(data) // 2
            read_timeout = max(timeout / 1000.0, 3.0)

            for attempt in range(7):  # up to 6 retries on incomplete multi-frame
                # Bumped from 5→7 to tolerate more NO DATA misses at
                # short AT ST (~65 ms); retries are cheap if first succeeds.
                self.serialPort.reset_input_buffer()
                self._multiframe_incomplete = False

                if data_len <= 7:
                    # ── Single Frame: PCI(1 byte) + data, padded to 8 bytes ──
                    sf_pci = f"{data_len:02X}"
                    raw_frame = (sf_pci + data).ljust(16, '0')

                    self.serialPort.write((raw_frame + "\r").encode("utf-8"))
                    self.serialPort.flush()

                    response = self._read_elm_response(read_timeout)
                    result = self._check_and_parse(response, read_timeout)
                else:
                    # ── Multi-frame send: First Frame + wait FC + Consecutive Frames ──
                    result = self._send_uds_multiframe(data, data_len, read_timeout)

                # Retry on incomplete multi-frame read OR NO DATA on multi-frame send
                should_retry = self._multiframe_incomplete
                if data_len > 7 and result in ("", "Timeout"):
                    should_retry = True

                if should_retry and attempt < 6:
                    self.log(f"Retrying multi-frame for {data} "
                             f"(attempt {attempt + 2}/7)...")
                    time.sleep(0.15 * (attempt + 1))
                    continue

                if attempt > 0:
                    if should_retry:
                        self.log(f"All retries failed for {data}")
                        return ""
                    else:
                        self.log(f"Retry OK for {data}")

                return result

        except Exception as e:
            self.log(f"UDS send error: {e}")
            return ""

    def _send_uds_multiframe(self, data, data_len, read_timeout):
        """Send UDS command > 7 bytes using ISO-TP multi-frame (FF + CF)."""
        try:
            # ── First Frame: PCI(2 bytes) + first 6 data bytes ──
            ff_pci = f"1{data_len:03X}"          # e.g. "100A" for 10 bytes
            ff_data = data[:12]                   # first 6 bytes = 12 hex chars
            ff_frame = (ff_pci + ff_data).ljust(16, '0')

            self.serialPort.reset_input_buffer()
            self.serialPort.write((ff_frame + "\r").encode("utf-8"))
            self.serialPort.flush()

            # Read Flow Control from ECU (should be 30 xx xx = Continue To Send)
            fc_response = self._read_elm_response(read_timeout)
            if fc_response is None:
                self.log("Multi-frame send: no FC from ECU")
                return "Timeout"

            # Verify FC frame (type 3 = Flow Control)
            fc_ok = False
            for fc_line in fc_response.replace("\r", "\n").split("\n"):
                cleaned = fc_line.strip().replace(" ", "")
                if cleaned and len(cleaned) >= 2 and \
                   all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                    fb = int(cleaned[0:2], 16)
                    if (fb >> 4) == 3:  # FC frame
                        fc_ok = True
                        break

            if not fc_ok:
                self.log(f"Multi-frame send: invalid FC: {fc_response}")
                return ""

            # ── Consecutive Frames ──
            remaining = data[12:]  # after first 6 bytes
            seq = 1
            num_cfs = (len(remaining) + 13) // 14  # total CFs needed

            # Shorten AT ST for intermediate CFs (they get NO DATA anyway)
            # so we don't wait per-frame. Restore before last CF.
            if num_cfs > 1:
                self._send_at(f"AT ST {self.AT_ST_CF_RAPID}")

            while remaining:
                is_last = len(remaining) <= 14

                # Restore normal timeout before the last CF (need ECU response)
                if is_last and num_cfs > 1:
                    self._send_at(f"AT ST {self.AT_ST_NORMAL}")

                cf_pci = f"2{seq & 0x0F:X}"
                cf_data = remaining[:14]           # up to 7 bytes = 14 hex chars
                remaining = remaining[14:]
                cf_frame = (cf_pci + cf_data).ljust(16, '0')

                self.serialPort.write((cf_frame + "\r").encode("utf-8"))
                self.serialPort.flush()

                # Read response: intermediate CFs get NO DATA, last CF gets ECU answer
                cf_resp = self._read_elm_response(read_timeout)

                if is_last:
                    return self._check_and_parse(cf_resp, read_timeout)

                # Intermediate CF — ignore NO DATA, continue sending
                seq += 1

            return ""
        except Exception as e:
            self.log(f"Multi-frame send error: {e}")
            return ""

    def _check_and_parse(self, response, read_timeout):
        """Check ELM327 response for errors, then parse ISO-TP."""
        if response is None:
            return "Timeout"

        first_line = response.split("\n")[0].strip()

        # Detect unsupported clone
        if first_line == "?":
            if self._raw_can_supported:
                self._raw_can_supported = False
                self.log("Your ELM327 clone is not supported! "
                         "It does not support raw CAN mode (AT CAF0) "
                         "required for PSA diagnostics. "
                         "Use a quality adapter (Vgate iCar Pro 2s, etc).", ui=True)
            return ""

        elm_errors = ("NO DATA", "CAN ERROR", "BUFFER FULL",
                      "BUS INIT: ...ERROR", "UNABLE TO CONNECT",
                      "FB ERROR", "DATA ERROR", "ACT ALERT",
                      "STOPPED", "ERROR")
        if first_line in elm_errors or first_line.startswith("BUS INIT"):
            self.log(f"ELM327 error: {first_line}")
            return ""

        return self._parse_isotp_response(response, read_timeout)

    def _read_elm_response(self, timeout=2):
        """Read full response from ELM327 until '>' prompt"""
        data = bytearray()
        end = time.monotonic() + timeout

        while time.monotonic() < end:
            n = self.serialPort.in_waiting
            if n:
                data.extend(self.serialPort.read(n))
                # ELM327 signals end of response with '>' prompt
                if b">" in data:
                    break
                # Reset timeout on data received
                end = time.monotonic() + timeout
            else:
                time.sleep(0.01)

        if not data:
            return None

        # Decode and clean up response
        response = data.decode("utf-8", errors="ignore")
        # Remove prompt
        response = response.replace(">", "").strip()
        # Split into lines, keep ALL non-empty lines
        lines = response.split("\r")
        clean_lines = [line.strip() for line in lines if line.strip()]
        if clean_lines:
            # Return all lines joined with \n (for multi-frame parsing)
            return "\n".join(clean_lines)
        return None

    def _parse_isotp_response(self, response, read_timeout):
        """Parse raw ISO-TP CAN frames (AT CAF0 mode).

           With CAF0 + CFC0 + ATH0 + ATS0, each CAN frame is a raw hex line
           (up to 16 hex chars = 8 bytes). We decode ISO-TP framing manually:
             SF: 0N DDDDDD...  (N = data length, 1-7)
             FF: 1N NN DDDDDD  (NNN = total length, 12-bit)
             CF: 2N DDDDDD...  (N = sequence 0-F)
        """
        if not response:
            return ""

        # Collect valid hex lines from response
        hex_lines = []
        for line in response.replace("\r", "\n").split("\n"):
            cleaned = line.strip().replace(" ", "")
            if cleaned and len(cleaned) % 2 == 0 and \
               all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                hex_lines.append(cleaned.upper())

        if not hex_lines:
            return ""

        # Find the first frame that looks like a real ISO-TP response
        # (skip any stale noise lines)
        for frame in hex_lines:
            first_byte = int(frame[0:2], 16)
            frame_type = (first_byte >> 4) & 0x0F

            if frame_type == 0:
                # ── Single Frame ──
                data_len = first_byte & 0x0F
                if data_len == 0 or data_len > 7:
                    continue
                data = frame[2:2 + data_len * 2]
                # Skip NRC 78 (Response Pending) — real response follows
                if len(data) >= 6 and data[0:2] == "7F" and data[4:6] == "78":
                    continue
                return data

            elif frame_type == 1:
                # ── First Frame (multi-frame start) ──
                total_len = ((first_byte & 0x0F) << 8) | int(frame[2:4], 16)
                ff_data = frame[4:]  # up to 6 bytes (12 hex chars)

                # Send Flow Control immediately — no AT commands between FF and FC
                # to minimize latency (AT ST 32 ~200ms is enough for CF collection)
                self.serialPort.reset_input_buffer()
                self.serialPort.write(b"3000050000000000\r")
                self.serialPort.flush()

                # Read Consecutive Frames
                cf_response = self._read_elm_response(read_timeout)

                all_data = ff_data
                if cf_response:
                    for cf_line in cf_response.replace("\r", "\n").split("\n"):
                        cf_clean = cf_line.strip().replace(" ", "")
                        if not cf_clean or len(cf_clean) < 4 or len(cf_clean) % 2 != 0:
                            continue
                        if not all(c in "0123456789ABCDEFabcdef" for c in cf_clean):
                            continue
                        cf_byte = int(cf_clean[0:2], 16)
                        if (cf_byte >> 4) == 2:  # Consecutive Frame (PCI = 0x2N)
                            all_data += cf_clean[2:].upper()  # skip PCI byte
                else:
                    self.log("Multi-frame error: no Consecutive Frames received after FC")

                # Trim to declared total length
                result = all_data[:total_len * 2].upper()
                got = len(result) // 2
                if got < total_len:
                    self.log(f"Multi-frame incomplete: {got}/{total_len} bytes")
                    self._multiframe_incomplete = True
                return result

        # Fallback: return longest hex line as raw data
        return max(hex_lines, key=len)

    # ─── Keep-alive ───────────────────────────────────────────────

    def _start_keep_alive(self):
        """Start the background TesterPresent thread (idempotent).

        Purpose:
          - Keeps BT RFCOMM link warm (prevents OS 10-min idle drop)
          - Keeps ELM327 out of low-power sleep
          - Keeps ECU UDS session alive (resets S3 timer)

        Called when DiagnosticCommunication sends 'KK' / 'KU' at the
        start of a diagnostic session."""
        if self._ka_thread is not None and self._ka_thread.is_alive():
            return  # already running
        self._ka_stop.clear()
        self._ka_thread = threading.Thread(
            target=self._keep_alive_loop,
            name="ELM327-KeepAlive",
            daemon=True,
        )
        self._ka_thread.start()
        self.log(f"Keep-alive started (period={self._ka_period}s)")

    def _stop_keep_alive(self):
        """Signal the keep-alive thread to stop and wait briefly for it."""
        if self._ka_thread is None:
            return
        self._ka_stop.set()
        if self._ka_thread.is_alive():
            self._ka_thread.join(timeout=self._ka_period + 1.0)
        self._ka_thread = None
        self.log("Keep-alive stopped")

    def _keep_alive_loop(self):
        """Periodic TesterPresent sender, runs in its own daemon thread.

        Sends UDS `3E 80` (TesterPresent with suppressPosRspMsgIndicationBit
        — ECU stays silent, minimum bus traffic). Acquires self._io_lock
        for the full tick so it never interleaves with a user command."""
        while not self._ka_stop.wait(self._ka_period):
            if not self.connected or not self.configured:
                # Nothing useful to send yet; just keep looping so the
                # user can start a session later without restarting us.
                continue
            # Try-lock with short timeout: if the main thread is in the
            # middle of a long multi-frame read, skip this tick rather
            # than pile up. Next tick will likely succeed.
            if not self._io_lock.acquire(timeout=0.5):
                continue
            try:
                if not self.serialPort.isOpen():
                    continue
                self._send_uds_no_response("3E80")
            except serial.SerialTimeoutException:
                # BT write deadline — link looks dead. We don't reconnect
                # from the keep-alive thread (the user-initiated path in
                # _send_uds will handle it on the next real command).
                self.log("Keep-alive: write timeout (link may be dead)")
            except Exception as e:
                # Any other transient error — log and keep looping.
                self.log(f"Keep-alive tick error (ignored): {e}")
            finally:
                self._io_lock.release()

    def _send_uds_no_response(self, data):
        """Send a single ISO-TP Single Frame without parsing a response.

        Used by keep-alive: we only care that the bytes leave the BT link
        (keeps RFCOMM + ELM + ECU session alive). Caller MUST hold
        self._io_lock."""
        data_len = len(data) // 2
        if data_len > 7:
            return  # keep-alive payloads are always tiny
        sf_pci = f"{data_len:02X}"
        raw_frame = (sf_pci + data).ljust(16, '0')
        try:
            self.serialPort.reset_input_buffer()
            self.serialPort.write((raw_frame + "\r").encode("utf-8"))
            self.serialPort.flush()
            # Drain the ELM prompt so the next real read starts clean.
            # Short timeout — with 3E 80 there's no UDS response, only '>'.
            self._read_elm_response(timeout=0.5)
        except serial.SerialTimeoutException:
            raise  # bubble up to _keep_alive_loop

    # ─── Info ─────────────────────────────────────────────────────

    def get_adapter_info(self):
        """Get adapter information"""
        return {
            "name": "ELM327 Bluetooth OBD",
            "type": "Bluetooth",
            "connected": self.connected,
            "configured": self.configured,
            "elm_version": self.elm_version,
            "tx_id": self.current_tx_id,
            "rx_id": self.current_rx_id,
        }
