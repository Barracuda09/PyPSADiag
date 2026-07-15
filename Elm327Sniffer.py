"""
Elm327Sniffer.py
"""
from __future__ import annotations

import re
import time
import threading
from typing import Iterable, Optional, Set

import serial

from PySide6.QtCore import QObject, Signal


# ── Constants ──────────────────────────────────────────────────────────────
ELM_PROMPT = b">"

# Init sequence — driving ELM327 into raw CAN monitor mode.  See module
# docstring for rationale of each line.  ATCF/ATCM are appended dynamically
# in start_sniff() based on the wanted-IDs list.
INIT_SEQUENCE = [
    ("ATZ",    "reset"),
    ("ATD",    "defaults restore"),
    ("ATE0",   "echo off"),
    ("ATCFC1", "CAN flow control on"),
    ("ATH1",   "headers on"),
    ("ATSP6",  "ISO 15765-4 CAN 11-bit 500 kbps"),
    ("ATD1",   "display DLC byte"),
    ("ATH1",   "headers on (re-asserted after ATD1)"),
    ("ATAL",   "allow long messages (>7 bytes)"),
    ("ATCAF0", "auto-formatting OFF (raw frame passthrough)"),
]


def _compute_can_filter_mask(ids):
    ids = sorted(set(int(x) & 0x7FF for x in ids))
    if not ids:
        return (0x000, 0x000)
    if len(ids) == 1:
        return (ids[0], 0x7FF)
    diff = 0
    for v in ids:
        diff |= (ids[0] ^ v)
    mask = (~diff) & 0x7FF
    flt = ids[0] & mask
    return (flt, mask)


_LINE_RE = re.compile(
    r"^\s*(?P<id>[0-9A-Fa-f]{3,8})\s+"
    r"(?:(?P<dlc>[0-9A-Fa-f])\s+)?"
    r"(?P<payload>(?:[0-9A-Fa-f]{2}\s*){1,8})\s*$"
)


# ── Sniffer (Qt-aware) ─────────────────────────────────────────────────────

class Elm327Sniffer(QObject):
    """ELM327 passive sniffer over a CALLER-OWNED serial port.

    Usage:
        s = Elm327Sniffer(parent_serial)        # borrow caller's port
        s.frameReceived.connect(on_frame)
        s.statusChanged.connect(on_status)
        s.start_sniff([0x072, 0x0A8])
        ...
        s.stop_sniff()                          # gives the port back
    """

    # int can_id, bytes payload
    frameReceived = Signal(int, bytes)
    # str — human-readable status message
    statusChanged = Signal(str)
    # str — error message (also logged to statusChanged)
    errorOccurred = Signal(str)

    def __init__(self, serial_port: serial.Serial,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._serial: serial.Serial = serial_port
        self._reader: Optional[_ReaderThread] = None
        self._filter_ids: Set[int] = set()

    # ── Filtering: ATCF/ATCM computed in start_sniff() ─────────────────────

    # ── Start / Stop monitoring ────────────────────────────────────────────
    def start_sniff(self, ids: Iterable[int]):
        """Initialise the ELM and enter ATMA (Monitor All) mode.
        """
        if self._serial is None or not self._serial.is_open:
            self.errorOccurred.emit("Serial port not open.")
            return

        self._filter_ids = set(int(x) & 0x7FF for x in ids)

        # Run the static init sequence
        for cmd, desc in INIT_SEQUENCE:
            self.statusChanged.emit(f"  > {cmd}  ({desc})")
            try:
                resp = self._send_at(cmd, timeout=2.0 if cmd == "ATZ" else 0.6)
            except _SniffIOError as e:
                self.errorOccurred.emit(f"Init failed at {cmd!r}: {e}")
                return
            self.statusChanged.emit(f"  < {resp!r}")
            if cmd != "ATZ" and "OK" not in resp.upper():
                self.errorOccurred.emit(
                    f"{cmd!r} did not return OK (got {resp!r}) — continuing")

        # Compute and install HW filter
        flt, mask = _compute_can_filter_mask(self._filter_ids)
        n_pass = 1 << bin(mask ^ 0x7FF).count("1")
        self.statusChanged.emit(
            f"HW filter:  ATCF{flt:03X}  ATCM{mask:03X}  "
            f"(admits up to {n_pass} CAN IDs)")
        for at in (f"ATCF{flt:03X}", f"ATCM{mask:03X}"):
            try:
                resp = self._send_at(at, timeout=0.6)
            except _SniffIOError as e:
                self.errorOccurred.emit(f"{at} failed: {e}")
                return
            self.statusChanged.emit(f"  > {at}   < {resp!r}")

        self.statusChanged.emit(
            "Python-side fine filter for IDs: "
            + ", ".join(f"0x{x:03X}" for x in sorted(self._filter_ids)))

        # ATMA — start passive monitor
        self.statusChanged.emit("> ATMA (monitor all — passive sniff)")
        try:
            self._serial.write(b"ATMA\r")
            self._serial.flush()
        except (serial.SerialException, OSError) as e:
            self.errorOccurred.emit(f"ATMA write failed: {e}")
            return

        # Spawn reader thread
        self._reader = _ReaderThread(
            ser=self._serial,
            filter_ids=self._filter_ids,
            on_frame=self._on_frame,
            on_error=lambda msg: self.errorOccurred.emit(msg))
        self._reader.daemon = True
        self._reader.start()
        self.statusChanged.emit("Sniffer streaming…")

    def stop_sniff(self):
        """Abort ATMA and stop the reader thread.  Leaves the port open
        for further use by the owning caller."""
        if self._reader is not None:
            self._reader.stop()
            self._reader.join(timeout=2.0)
            self._reader = None

        # Send a single character to abort ATMA on the ELM side.
        if self._serial is not None and self._serial.is_open:
            try:
                self._serial.write(b" \r")
                self._serial.flush()
                time.sleep(0.1)
                self._serial.reset_input_buffer()
            except Exception:
                pass
        self.statusChanged.emit("Sniffer stopped.")

    # ── Internal callbacks ─────────────────────────────────────────────────
    def _on_frame(self, can_id: int, payload: bytes):
        """Reader-thread callback — re-emit as Qt signal on the receiving
        thread (Qt signals are thread-safe; cross-thread calls go via the
        event-loop queue)."""
        self.frameReceived.emit(can_id, payload)

    # ── AT helper ──────────────────────────────────────────────────────────
    def _send_at(self, cmd: str, timeout: float = 1.0) -> str:
        """Send an AT command, read until '>' prompt, return the textual
        response (with prompt stripped).  Raises _SniffIOError on timeout."""
        if self._serial is None:
            raise _SniffIOError("Serial not open")
        self._serial.reset_input_buffer()
        self._serial.write((cmd + "\r").encode("ascii", errors="ignore"))
        self._serial.flush()

        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            n = self._serial.in_waiting
            if n:
                buf.extend(self._serial.read(n))
                if ELM_PROMPT in buf:
                    break
            else:
                time.sleep(0.005)
        else:
            raise _SniffIOError(f"timeout waiting for ELM prompt after {cmd!r}")

        idx = buf.rfind(ELM_PROMPT)
        return buf[:idx].decode("ascii", errors="replace").strip()


# ── Internal reader thread ─────────────────────────────────────────────────

class _ReaderThread(threading.Thread):
    """Continuously reads lines from the ELM327 in ATMA mode and parses
    them into (can_id, payload) tuples, pushing every match to `on_frame`.
    """

    def __init__(self, ser: serial.Serial,
                 filter_ids: Set[int],
                 on_frame, on_error):
        super().__init__()
        self._ser = ser
        self._filter_ids = filter_ids
        self._on_frame = on_frame
        self._on_error = on_error
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        line_buf = bytearray()
        while not self._stop.is_set():
            try:
                self._ser.timeout = 0.1
                chunk = self._ser.read(256)
            except (serial.SerialException, OSError) as e:
                self._on_error(f"Reader I/O error: {e}")
                return
            if not chunk:
                continue

            for byte in chunk:
                if byte in (0x0D, 0x0A):     # CR or LF -> end of line
                    if line_buf:
                        self._handle_line(bytes(line_buf))
                        line_buf.clear()
                elif byte == 0x3E:           # '>' prompt — discard, ELM idle
                    line_buf.clear()
                else:
                    line_buf.append(byte)

    def _handle_line(self, raw: bytes):
        try:
            text = raw.decode("ascii", errors="replace").strip()
        except Exception:
            return
        if not text:
            return
        m = _LINE_RE.match(text)
        if not m:
            return  # non-frame line (STOPPED, BUFFER FULL, NO DATA, ?, etc.)

        try:
            can_id = int(m.group("id"), 16)
        except ValueError:
            return

        # Python-side fine filter (HW filter may admit a superset)
        if can_id not in self._filter_ids:
            return

        payload_str = m.group("payload").replace(" ", "")
        if len(payload_str) % 2 != 0:
            return
        try:
            payload = bytes.fromhex(payload_str)
        except ValueError:
            return
        if len(payload) > 8:
            return

        self._on_frame(can_id, payload)


# ── Exceptions ─────────────────────────────────────────────────────────────

class _SniffIOError(Exception):
    """Internal — raised when ELM I/O times out or fails during init."""
    pass
