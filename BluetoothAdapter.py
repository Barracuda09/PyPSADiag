"""
   BluetoothAdapter.py

   ELM327 Bluetooth OBD Adapter for PyPSADiag
   Communicates with ELM327-based Bluetooth OBD scanners via virtual COM port

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or (at your option) any later version.
"""

import atexit
import os
import re
import sys
import threading
import time
import serial
import serial.tools.list_ports


IS_WINDOWS = sys.platform == "win32"

_POSIX_PORT_BLACKLIST = (
    "bluetooth-incoming-port",
    "bluetooth-modem",
    "debug-console",
    "wlan-debug",
)

_POSIX_USB_MARKERS = (
    "usbserial", "usbmodem", "slab_", "wchusbserial", "ftdi", "ttyusb", "ttyacm",
)


def _is_rfcomm_device(device: str) -> bool:
    if IS_WINDOWS or not device:
        return False
    leaf = device.rsplit("/", 1)[-1].lower()
    return device.startswith("/dev/cu.") and \
        not any(m in leaf for m in _POSIX_USB_MARKERS)


def _natural_com_key(name: str):
    m = re.search(r"\d+", name or "")
    return (int(m.group()) if m else 0, name or "")


def _is_bluetooth_port(port) -> bool:
    if IS_WINDOWS:
        return "BTHENUM" in (port.hwid or "").upper() or \
               "BLUETOOTH" in (port.description or "").upper()

    device = port.device or ""
    if not device.startswith("/dev/cu."):
        return False
    leaf = device[len("/dev/cu."):].lower()
    return not any(bad in leaf for bad in _POSIX_PORT_BLACKLIST)


class BluetoothAdapter:
    BAUD_RATES = [115200, 57600, 38400, 19200, 9600, 230400]
    POSIX_NOMINAL_BAUD = 115200

    AT_ST_NATIVE = "40"
    AT_ST_NORMAL = "30"

    def __init__(self, logger=None, isotp_mode=None, debug_timing=None, **kwargs):
        self.logger = logger
        self.serialPort = serial.Serial()
        self.connected = False
        self.configured = False
        self.current_tx_id = ""
        self.current_rx_id = ""
        self.current_protocol = "uds"
        self.elm_version = ""
        self.detected_baud = None
        self._raw_can_supported = True
        self._multiframe_incomplete = False
        self._exit_hook_armed = False

        mode = isotp_mode or os.environ.get("PYPSADIAG_ISOTP") or "native"
        self.isotp_mode = "raw" if str(mode).lower() == "raw" else "native"
        self._isotp_pref = self.isotp_mode
        self._native_failed = False
        self._native_segmented_tx = True

        if debug_timing is None:
            debug_timing = os.environ.get("PYPSADIAG_BT_TIMING", "") not in ("", "0")
        self.debug_timing = bool(debug_timing)

        self.at_st_native = self._env_st("PYPSADIAG_ST_NATIVE", self.AT_ST_NATIVE)
        self.at_st_raw = self._env_st("PYPSADIAG_ST_RAW", self.AT_ST_NORMAL)

        self._io_lock = threading.RLock()
        self._ka_thread = None
        self._ka_stop = threading.Event()
        self._ka_period = 2.0
        self._session_ka = False
        self._last_io = time.monotonic()
        self._ka_suspended = False

    @staticmethod
    def _env_st(name, default):
        raw = (os.environ.get(name) or "").strip().upper()
        if not raw:
            return default
        if re.fullmatch(r"[0-9A-F]{1,2}", raw) and int(raw, 16) > 0:
            return raw.zfill(2)
        print(f"[BT] Ignoring {name}={raw!r}: expected 1-2 hex digits 01-FF, "
              f"keeping {default}")
        return default

    def log(self, message, ui=False):
        log_msg = f"[BT] {message}"
        print(log_msg)
        if ui and self.logger and \
                threading.current_thread() is threading.main_thread():
            self.logger(log_msg)

    def _timing(self, label, t0):
        if self.debug_timing:
            self.log(f"  [t] {label}: {(time.monotonic() - t0) * 1000:.0f} ms")

    def fillPortNameCombobox(self, combobox):
        combobox.clear()
        comPorts = serial.tools.list_ports.comports()

        bt_ports = []
        other_ports = []

        for port in comPorts:
            if not IS_WINDOWS and (port.device or "").startswith("/dev/tty."):
                continue

            if _is_bluetooth_port(port):
                bt_ports.append(port)
            else:
                other_ports.append(port)

        bt_ports.sort(key=lambda p: _natural_com_key(p.device))
        other_ports.sort(key=lambda p: _natural_com_key(p.device))

        self.log(f"Found {len(bt_ports)} Bluetooth port(s), "
                 f"{len(other_ports)} other port(s)", ui=True)

        for port in bt_ports:
            self.log(f"Scanning {port.device} ({port.description})...", ui=True)
            baud, version = self._probe_elm327(port.device)
            if baud:
                label = f"{port.device} - ELM327 [{version}] @ {baud} baud"
                combobox.addItem(label, f"{port.device}:{baud}")
                self.log(f"  Found ELM327: {version} @ {baud}", ui=True)
            else:
                label = f"{port.device} - {port.description or 'Bluetooth'} (no response)"
                combobox.addItem(label, f"{port.device}:0")
                self.log(f"  No ELM327 response", ui=True)

        for port in other_ports:
            label = f"{port.device} - {port.description or 'Unknown'}"
            combobox.addItem(label, f"{port.device}:0")

    def _probe_elm327(self, port_name):
        bauds = [self.POSIX_NOMINAL_BAUD] if _is_rfcomm_device(port_name) \
            else self.BAUD_RATES

        for baud in bauds:
            test_port = serial.Serial()
            test_port.port = port_name
            test_port.baudrate = baud
            test_port.timeout = 1.5
            test_port.write_timeout = 3.0
            try:
                test_port.open()
                time.sleep(0.3)
                test_port.reset_input_buffer()

                test_port.write(b"ATZ\r")
                if IS_WINDOWS:
                    test_port.flush()

                data = bytearray()
                end = time.monotonic() + 3.0
                while time.monotonic() < end:
                    n = test_port.in_waiting
                    if n:
                        data.extend(test_port.read(n))
                        if b">" in data:
                            break
                    else:
                        time.sleep(0.01)

                if data:
                    response = data.decode("utf-8", errors="ignore")
                    if "ELM" in response.upper():
                        for line in response.split("\r"):
                            line = line.strip()
                            if "ELM" in line.upper():
                                return baud, line
                        return baud, "ELM327"

            except (serial.SerialException, OSError) as e:
                self.log(f"  probe {port_name}@{baud} failed: {e}")
            finally:
                try:
                    if test_port.is_open:
                        test_port.close()
                except Exception:
                    pass

        return None, None

    def open(self, portNr, baudRate=None):
        try:
            detected_baud = None
            if isinstance(portNr, str) and portNr.rsplit(":", 1)[-1].isdigit() \
                    and ":" in portNr:
                head, baud_str = portNr.rsplit(":", 1)
                if head:
                    portNr = head
                    if int(baud_str) > 0:
                        detected_baud = int(baud_str)

            self.serialPort.port = portNr
            self.serialPort.timeout = 3.0
            self.serialPort.write_timeout = 5.0

            if _is_rfcomm_device(portNr):
                baud = detected_baud or self.POSIX_NOMINAL_BAUD
                self.log(f"Connecting to {portNr} (RFCOMM, line speed ignored)", ui=True)
                self.serialPort.baudrate = baud
                self.serialPort.open()
                time.sleep(0.5)

                if self._init_elm327():
                    self.connected = True
                    self.detected_baud = baud
                    self._arm_exit_cleanup()
                    self._start_keep_alive()
                    return ""
                self.serialPort.close()
                return "ELM327 not responding on " + portNr

            if detected_baud:
                self.log(f"Connecting to {portNr} @ {detected_baud} baud (auto-detected)", ui=True)
                self.serialPort.baudrate = detected_baud
                self.serialPort.open()
                time.sleep(0.5)

                if self._init_elm327():
                    self.connected = True
                    self.detected_baud = detected_baud
                    self._arm_exit_cleanup()
                    self._start_keep_alive()
                    return ""
                self.serialPort.close()

            self.log(f"Auto-detecting baud rate on {portNr}...", ui=True)
            for baud in self.BAUD_RATES:
                try:
                    self.log(f"  Trying {baud} baud...", ui=True)
                    self.serialPort.baudrate = baud
                    if not self.serialPort.is_open:
                        self.serialPort.open()
                    time.sleep(0.3)

                    if self._init_elm327():
                        self.connected = True
                        self.detected_baud = baud
                        self.log(f"Connected @ {baud} baud", ui=True)
                        self._arm_exit_cleanup()
                        self._start_keep_alive()
                        return ""

                    self.serialPort.close()
                except serial.SerialException:
                    if self.serialPort.is_open:
                        self.serialPort.close()
                    continue

            return "ELM327 not found: no response at any baud rate"

        except serial.SerialException as e:
            return f"Error opening Bluetooth port: {str(e)}"

    def _arm_exit_cleanup(self):
        if IS_WINDOWS or self._exit_hook_armed:
            return
        atexit.register(self._atexit_close)
        self._exit_hook_armed = True

    def _atexit_close(self):
        try:
            self.close(quick=True)
        except Exception:
            pass

    def close(self, quick=False):
        atexit.unregister(self._atexit_close)
        self._exit_hook_armed = False
        self._stop_keep_alive(join_timeout=1.0 if quick else None)
        if self.serialPort.is_open:
            try:
                self._send_at("ATZ", timeout=0.5 if quick else 3)
            except Exception:
                pass
            self.serialPort.close()
        self.connected = False
        self.configured = False
        return True

    def isOpen(self):
        return self.serialPort.is_open and self.connected

    def is_configured(self):
        return self.configured

    def _init_elm327(self):
        response = self._send_at("ATZ", timeout=3)
        if response is None:
            self.log("ELM327 not responding")
            return False

        self.elm_version = next(
            (l.strip() for l in response.split("\n") if "ELM" in l.upper()),
            response.strip())
        self.log(f"ELM327 version: {self.elm_version}")

        common = [
            ("ATE0",    "Echo off"),
            ("ATL0",    "Linefeeds off"),
            ("ATS0",    "Spaces off"),
            ("ATH0",    "Headers off"),
        ]
        for cmd, description in common:
            response = self._send_at(cmd)
            if response is None:
                self.log(f"Failed: {description} ({cmd})")
                return False
            self.log(f"OK: {description}")

        if self._isotp_pref == "native":
            self.isotp_mode = "native"
            self._native_failed = False
            self._native_segmented_tx = True

        if self.isotp_mode == "native":
            if not self._init_native_isotp():
                self.log("Native ISO-TP unsupported by this adapter — "
                         "falling back to raw CAF0 mode", ui=True)
                self.isotp_mode = "raw"
                self._native_failed = True

        if self.isotp_mode == "raw":
            if not self._init_raw_isotp():
                return False

        lp_resp = self._send_at("AT LP 0")
        if lp_resp is None or "?" in (lp_resp or ""):
            self.log("AT LP 0 not supported (clone) — ignoring")
        else:
            self.log("OK: Low-power mode disabled")

        st = self.at_st_native if self.isotp_mode == "native" else self.at_st_raw
        self.log(f"ISO-TP mode: {self.isotp_mode.upper()} "
                 f"(AT ST {st} ~= {int(st, 16) * 4.096:.0f} ms)", ui=True)
        return True

    def _init_native_isotp(self):
        for cmd, description in [
            ("AT CAF1", "CAN auto-formatting on (ELM does ISO-TP)"),
            ("AT SP 6", "Protocol: ISO 15765-4 CAN 500kbps 11-bit"),
            ("AT AT1",  "Adaptive timing on"),
        ]:
            resp = self._send_at(cmd)
            if resp is None or "?" in (resp or "") or "ERROR" in (resp or "").upper():
                self.log(f"Native ISO-TP init failed at {cmd}: {resp}")
                return False
            self.log(f"OK: {description}")

        self._send_at(f"AT ST {self.at_st_native}")
        return True

    def _init_raw_isotp(self):
        for cmd, description in [
            ("AT CAF0", "CAN auto-formatting off (manual ISO-TP)"),
            ("AT CFC0", "CAN flow control off (manual FC)"),
            ("AT SP 6", "Protocol: ISO 15765-4 CAN 500kbps 11-bit"),
        ]:
            resp = self._send_at(cmd)
            if resp is None:
                self.log(f"Failed: {description} ({cmd})")
                return False
            self.log(f"OK: {description}")
        return True

    def configure(self, tx_id, rx_id, protocol="uds", bus="DIAG", target=None, dialog_type="0"):
        if not self.connected:
            self.log("Not connected")
            return False

        if not tx_id or not rx_id:
            self.log("No ECU selected yet — deferring CAN configuration")
            return True

        with self._io_lock:
            self.current_tx_id = tx_id
            self.current_rx_id = rx_id
            self.current_protocol = protocol

            protocol_lower = (protocol or "uds").lower()
            if protocol_lower in ("uds", "kwp_is", "kwp_hab"):
                self._send_at("AT SP 6")
            elif protocol_lower in ("kwp2000", "psa2000"):
                self._send_at("AT SP B")

            response = self._send_at(f"AT SH {tx_id}")
            if self._elm_error(response) is not None or response is None:
                self.log(f"Failed to set TX ID: {tx_id} ({response!r})")
                return False

            response = self._send_at(f"AT CRA {rx_id}")
            if self._elm_error(response) is not None or response is None:
                self.log(f"Failed to set RX filter: {rx_id} ({response!r})")
                return False

            self._send_at(f"AT CF {rx_id}")
            self._send_at("AT CM 7FF")

            if self.isotp_mode == "native":
                if not self._configure_native_fc(tx_id):
                    self.log("Custom flow control rejected — switching to raw mode",
                             ui=True)
                    self.isotp_mode = "raw"
                    self._native_failed = True
                    self._init_raw_isotp()
                    self._send_at("AT AT0")
                    self._send_at(f"AT ST {self.at_st_raw}")
                else:
                    self._send_at("AT AT1")
                    self._send_at(f"AT ST {self.at_st_native}")
            else:
                self._send_at("AT AT0")
                self._send_at(f"AT ST {self.at_st_raw}")

            self.configured = True
            self.log(f"Configured: TX={tx_id} RX={rx_id} protocol={protocol} "
                     f"mode={self.isotp_mode}")
            return True

    def _configure_native_fc(self, tx_id):
        for cmd in (f"AT FC SH {tx_id}", "AT FC SD 300000", "AT FC SM 1", "AT CFC1"):
            resp = self._send_at(cmd)
            if resp is None or "?" in (resp or "") or "ERROR" in (resp or "").upper():
                self.log(f"Flow control setup failed at '{cmd}': {resp}")
                return False
        self.log("OK: ELM-native flow control armed for " + tx_id)
        return True

    def sendReceive(self, data, timeout=1500):
        if not self.connected:
            return ""

        if data.startswith("K"):
            self._session_ka = True
            self._start_keep_alive()
            return "OK"
        elif data == "S":
            self._session_ka = False
            self.log("Keep-alive: session ended -> link-warm mode (ATI)")
            return "OK"

        with self._io_lock:
            if data.startswith(">") and ":" in data:
                self.log("ECU already configured, skipping Arduino command")
                return "OK"
            elif data.startswith("L"):
                self.log("LIN not supported on ELM327 OBD")
                return "OK"
            elif data == "R":
                self._init_elm327()
                if self.current_tx_id and self.current_rx_id:
                    self.configure(self.current_tx_id, self.current_rx_id,
                                   self.current_protocol)
                return "OK"
            elif data == "V":
                return self.elm_version or "ELM327 Bluetooth"

            t0 = time.monotonic()
            if self.isotp_mode == "native":
                result = self._send_uds_native(data, timeout)
            else:
                result = self._send_uds_raw(data, timeout)
            self._timing(f"sendReceive({data[:16]})", t0)
            return result

    def _send_uds_native(self, data, timeout=1500):
        read_timeout = max(timeout / 1000.0, 3.0)
        is_segmented = len(data) // 2 > 7
        if is_segmented:
            read_timeout = max(read_timeout, 6.0)
            if not self._native_segmented_tx:
                return self._send_raw_excursion(data, timeout)

        reasserted = False
        for attempt in range(3):
            try:
                self._drain_input()
                t0 = time.monotonic()
                self._write_line(data)
                self._timing("write", t0)

                t0 = time.monotonic()
                response = self._read_elm_response(read_timeout)
                self._timing("read", t0)

                if response is None:
                    if attempt < 2:
                        self.log(f"No response for {data}, retry {attempt + 2}/3")
                        time.sleep(0.15 * (attempt + 1))
                        continue
                    return "Timeout"

                err = self._elm_error(response)
                if err is not None:
                    if is_segmented and self._native_segmented_tx and \
                            (err == "?" or err.startswith("ERR")):
                        self._native_segmented_tx = False
                        self.log(f"Adapter cannot send segmented ISO-TP "
                                 f"({err}) — framing long requests in Python "
                                 f"from now on", ui=True)
                        return self._send_raw_excursion(data, timeout)
                    if err == "?" and not self._native_failed:
                        if not reasserted:
                            reasserted = True
                            self.log("Native '?' — re-asserting native config "
                                     "and retrying")
                            self._reassert_native()
                            continue
                        self.log("Adapter rejected native ISO-TP payload — "
                                 "falling back to raw mode", ui=True)
                        self._fallback_to_raw()
                        return self._send_uds_raw(data, timeout)
                    if err == "BUFFER FULL":
                        self.log("Response too long for native buffer — "
                                 "reading this one in raw mode")
                        return self._send_raw_excursion(data, timeout)
                    if attempt < 2 and err in ("NO DATA", "CAN ERROR"):
                        self.log(f"ELM327 error '{err}' for {data}, "
                                 f"retry {attempt + 2}/3")
                        time.sleep(0.15 * (attempt + 1))
                        continue
                    self.log(f"ELM327 error: {err}")
                    return ""

                parsed = self._parse_native_response(response)
                if not parsed:
                    if attempt < 2:
                        self.log(f"Unparseable response for {data}: {response!r}, "
                                 f"retry {attempt + 2}/3")
                        time.sleep(0.15 * (attempt + 1))
                        continue
                    self.log(f"Could not parse ELM response for {data}: "
                             f"{response!r}", ui=True)
                return parsed

            except serial.SerialTimeoutException:
                self.log(f"Write timeout for {data} (BT link stalled)")
                return "Timeout"
            except Exception as e:
                self.log(f"UDS send error: {e}")
                return ""

        return ""

    def _parse_native_response(self, response):
        if not response:
            return ""

        lines = [l.strip().replace(" ", "")
                 for l in response.replace("\r", "\n").split("\n")]
        lines = [l for l in lines if l]
        if not lines:
            return ""

        indexed = []
        plain = []

        for line in lines:
            if len(line) > 2 and line[1] == ":" and \
                    line[0].upper() in "0123456789ABCDEF":
                payload = line[2:].upper()
                if all(c in "0123456789ABCDEF" for c in payload):
                    indexed.append(payload)
                continue
            up = line.upper()
            if up and all(c in "0123456789ABCDEF" for c in up):
                plain.append(up)

        if indexed:
            total_len = None
            for up in plain:
                if len(up) <= 4:
                    total_len = int(up, 16)
                    break

            ordered = "".join(indexed)
            if total_len:
                got = len(ordered) // 2
                if got < total_len:
                    self.log(f"Multi-frame incomplete: {got}/{total_len} bytes")
                return ordered[:total_len * 2]
            return ordered

        singles = [up for up in plain if len(up) >= 2 and len(up) % 2 == 0]
        if singles:
            for s in singles:
                if not (len(s) >= 6 and s[0:2] == "7F" and s[4:6] == "78"):
                    return s
            return singles[-1]

        return ""

    def _reassert_native(self):
        self._send_at("AT CAF1")
        if self.current_tx_id:
            self._send_at(f"AT FC SH {self.current_tx_id}")
            self._send_at("AT FC SD 300000")
            self._send_at("AT FC SM 1")
        self._send_at("AT CFC1")
        self._send_at("AT AT1")
        self._send_at(f"AT ST {self.at_st_native}")

    def _send_raw_excursion(self, data, timeout):
        self._send_at("AT CAF0")
        self._send_at("AT CFC0")
        self._send_at("AT AT0")
        self._send_at(f"AT ST {self.at_st_raw}")
        try:
            return self._send_uds_raw(data, timeout)
        finally:
            if self.isotp_mode == "native":
                self._reassert_native()

    def _fallback_to_raw(self):
        self.isotp_mode = "raw"
        self._native_failed = True
        self._init_raw_isotp()
        if self.current_tx_id:
            self._send_at(f"AT SH {self.current_tx_id}")
        if self.current_rx_id:
            self._send_at(f"AT CRA {self.current_rx_id}")
        self._send_at("AT AT0")
        self._send_at(f"AT ST {self.at_st_raw}")

    def _send_uds_raw(self, data, timeout=1500):
        try:
            data_len = len(data) // 2
            read_timeout = max(timeout / 1000.0, 3.0)

            for attempt in range(7):
                self._drain_input()
                self._multiframe_incomplete = False

                if data_len <= 7:
                    sf_pci = f"{data_len:02X}"
                    raw_frame = (sf_pci + data).ljust(16, '0')
                    self._write_line(raw_frame)
                    response = self._read_elm_response(read_timeout)
                    result = self._check_and_parse(response, read_timeout)
                else:
                    result = self._send_uds_multiframe(data, data_len, read_timeout)

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
        try:
            ff_pci = f"1{data_len:03X}"
            ff_data = data[:12]
            ff_frame = (ff_pci + ff_data).ljust(16, '0')

            self._drain_input()
            self._write_line(ff_frame)

            fc_response = self._read_elm_response(read_timeout)
            if fc_response is None:
                self.log("Multi-frame send: no FC from ECU")
                return "Timeout"

            fc_ok = False
            for fc_line in fc_response.replace("\r", "\n").split("\n"):
                cleaned = fc_line.strip().replace(" ", "")
                if cleaned and len(cleaned) >= 2 and \
                   all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                    if (int(cleaned[0:2], 16) >> 4) == 3:
                        fc_ok = True
                        break

            if not fc_ok:
                self.log(f"Multi-frame send: invalid FC: {fc_response}")
                return ""

            remaining = data[12:]
            seq = 1
            while remaining:
                is_last = len(remaining) <= 14

                cf_pci = f"2{seq & 0x0F:X}"
                cf_data = remaining[:14]
                remaining = remaining[14:]
                cf_frame = (cf_pci + cf_data).ljust(16, '0')

                self._write_line(cf_frame)
                cf_resp = self._read_elm_response(read_timeout)

                if is_last:
                    return self._check_and_parse(cf_resp, read_timeout)

                seq += 1

            return ""
        except Exception as e:
            self.log(f"Multi-frame send error: {e}")
            return ""

    def _check_and_parse(self, response, read_timeout):
        if response is None:
            return "Timeout"

        err = self._elm_error(response)
        if err == "?":
            if self._raw_can_supported:
                self._raw_can_supported = False
                self.log("Your ELM327 clone is not supported! "
                         "It does not support raw CAN mode (AT CAF0) "
                         "required for PSA diagnostics. "
                         "Use a quality adapter (Vgate iCar Pro 2s, etc).", ui=True)
            return ""
        if err is not None:
            self.log(f"ELM327 error: {err}")
            return ""

        return self._parse_isotp_response(response, read_timeout)

    def _parse_isotp_response(self, response, read_timeout):
        if not response:
            return ""

        hex_lines = []
        for line in response.replace("\r", "\n").split("\n"):
            cleaned = line.strip().replace(" ", "")
            if cleaned and len(cleaned) % 2 == 0 and \
               all(c in "0123456789ABCDEFabcdef" for c in cleaned):
                hex_lines.append(cleaned.upper())

        if not hex_lines:
            return ""

        last_nrc78 = None
        for frame in hex_lines:
            first_byte = int(frame[0:2], 16)
            frame_type = (first_byte >> 4) & 0x0F

            if frame_type == 0:
                data_len = first_byte & 0x0F
                if data_len == 0 or data_len > 7:
                    continue
                data = frame[2:2 + data_len * 2]
                if len(data) >= 6 and data[0:2] == "7F" and data[4:6] == "78":
                    last_nrc78 = data
                    continue
                return data

            elif frame_type == 1:
                total_len = ((first_byte & 0x0F) << 8) | int(frame[2:4], 16)
                ff_data = frame[4:]

                self._write_line("3000000000000000")

                cf_response = self._read_elm_response(read_timeout)

                all_data = ff_data
                if cf_response:
                    for cf_line in cf_response.replace("\r", "\n").split("\n"):
                        cf_clean = cf_line.strip().replace(" ", "")
                        if not cf_clean or len(cf_clean) < 4 or len(cf_clean) % 2 != 0:
                            continue
                        if not all(c in "0123456789ABCDEFabcdef" for c in cf_clean):
                            continue
                        if (int(cf_clean[0:2], 16) >> 4) == 2:
                            all_data += cf_clean[2:].upper()
                else:
                    self.log("Multi-frame error: no Consecutive Frames received after FC")

                result = all_data[:total_len * 2].upper()
                got = len(result) // 2
                if got < total_len:
                    self.log(f"Multi-frame incomplete: {got}/{total_len} bytes")
                    self._multiframe_incomplete = True
                return result

        if last_nrc78 is not None:
            return last_nrc78

        return max(hex_lines, key=len)

    def readData(self):
        with self._io_lock:
            try:
                self._drain_input()
                self._write_line("ATMA")

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

                    if ft == 0:
                        dl = first_byte & 0x0F
                        if 0 < dl <= 7:
                            data = cleaned[2:2 + dl * 2]
                            if len(data) >= 6 and data[0:2] == "7F" and data[4:6] == "78":
                                continue
                            return cleaned
                    elif ft == 1:
                        return cleaned
            else:
                time.sleep(0.005)

        return None

    def _stop_monitor(self):
        try:
            self.serialPort.write(b"\r")
            time.sleep(0.1)
            self.serialPort.reset_input_buffer()
        except Exception:
            pass

    def _write_line(self, payload: str):
        self.serialPort.write((payload + "\r").encode("ascii", errors="ignore"))
        if IS_WINDOWS:
            self.serialPort.flush()
        self._last_io = time.monotonic()

    def _drain_input(self):
        try:
            self.serialPort.reset_input_buffer()
        except Exception:
            pass

    def _send_at(self, command, timeout=2):
        try:
            self._drain_input()
            self._write_line(command)
            return self._read_elm_response(timeout)
        except Exception as e:
            self.log(f"AT command error ({command}): {e}")
            return None

    @staticmethod
    def _elm_error(response):
        if response is None:
            return None
        first_line = response.split("\n")[0].strip().upper()
        if first_line == "?":
            return "?"
        elm_errors = ("NO DATA", "CAN ERROR", "BUFFER FULL",
                      "UNABLE TO CONNECT", "FB ERROR", "DATA ERROR",
                      "ACT ALERT", "STOPPED", "ERROR")
        if first_line in elm_errors or first_line.startswith("BUS INIT"):
            return first_line
        if re.fullmatch(r"ERR[0-9A-Z]{2}", first_line):
            return first_line
        return None

    def _read_elm_response(self, timeout=2):
        data = bytearray()
        now = time.monotonic()
        idle_deadline = now + timeout
        abs_deadline = now + timeout * 4
        poll = 0.002 if not IS_WINDOWS else 0.005

        while time.monotonic() < idle_deadline and time.monotonic() < abs_deadline:
            n = self.serialPort.in_waiting
            if n:
                data.extend(self.serialPort.read(n))
                if b">" in data:
                    break
                idle_deadline = time.monotonic() + timeout
            else:
                time.sleep(poll)
        else:
            if data:
                head = bytes(data[:120])
                more = f" (+{len(data) - 120} more bytes)" if len(data) > 120 else ""
                self.log(f"Read timed out after {timeout:.1f}s idle with no '>' "
                         f"prompt: {head!r}{more}")

        if not data:
            return None

        response = data.decode("utf-8", errors="ignore")
        response = response.replace(">", "").strip()
        lines = response.split("\r")
        clean_lines = [line.strip() for line in lines if line.strip()]
        if clean_lines:
            return "\n".join(clean_lines)
        return None

    def pause_keep_alive(self):
        self._ka_suspended = True
        self._stop_keep_alive()
        self.log("Keep-alive SUSPENDED — port handed to external consumer "
                 "(PIN Extractor)", ui=True)

    def resume_keep_alive(self):
        self._ka_suspended = False
        self.log("Keep-alive RESUMED", ui=True)
        if self.connected:
            self._start_keep_alive()

    def _start_keep_alive(self):
        if self._ka_suspended:
            return
        if self._ka_thread is not None and self._ka_thread.is_alive():
            return
        self._ka_stop.clear()
        self._ka_thread = threading.Thread(
            target=self._keep_alive_loop,
            name="ELM327-KeepAlive",
            daemon=True,
        )
        self._ka_thread.start()
        self.log(f"Keep-alive started (period={self._ka_period}s)")

    def _stop_keep_alive(self, join_timeout=None):
        if self._ka_thread is None:
            return
        self._ka_stop.set()
        if self._ka_thread.is_alive():
            self._ka_thread.join(
                timeout=self._ka_period + 1.0 if join_timeout is None
                else join_timeout)
        self._ka_thread = None
        self.log("Keep-alive stopped")

    def _keep_alive_loop(self):
        while not self._ka_stop.wait(self._ka_period):
            if not self.connected:
                continue
            if self._ka_suspended:
                continue
            if time.monotonic() - self._last_io < self._ka_period:
                continue
            if not self._io_lock.acquire(timeout=0.5):
                continue
            try:
                if not self.serialPort.is_open:
                    continue
                if self.configured and self._session_ka:
                    self._send_keep_alive_frame("3E80")
                else:
                    self._send_at("ATI")
            except serial.SerialTimeoutException:
                self.log("Keep-alive: write timeout (link may be dead)")
            except Exception as e:
                self.log(f"Keep-alive tick error (ignored): {e}")
            finally:
                self._io_lock.release()

    def _send_keep_alive_frame(self, data):
        if len(data) // 2 > 7:
            return
        if self.isotp_mode == "native":
            frame = data
        else:
            frame = (f"{len(data) // 2:02X}" + data).ljust(16, '0')
        try:
            self._drain_input()
            self._write_line(frame)
            self._read_elm_response(timeout=1.5)
        except serial.SerialTimeoutException:
            raise

    def get_adapter_info(self):
        return {
            "name": "ELM327 Bluetooth OBD",
            "type": "Bluetooth",
            "connected": self.connected,
            "configured": self.configured,
            "elm_version": self.elm_version,
            "isotp_mode": self.isotp_mode,
            "tx_id": self.current_tx_id,
            "rx_id": self.current_rx_id,
        }
