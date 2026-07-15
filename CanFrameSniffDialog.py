"""CanFrameSniffDialog — PIN Extractor dialog."""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import serial

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
)

from Elm327Sniffer import Elm327Sniffer
from PINExtractor import PinExtractorWorker, ALPHABET


# 0x072 = challenge (arrives first), 0x0A8 = response.
# Crypto relation: compute_response(PIN, payload_0x072) == payload_0x0A8.
CHALLENGE_ID = 0x072
RESPONSE_ID  = 0x0A8

# Coalesce high-rate frame updates into batched table refreshes.
UI_REFRESH_MS = 200

_HEX_RE = re.compile(r"[^0-9A-Fa-f]")


def _hex_to_bytes4(text: str) -> Optional[bytes]:
    cleaned = _HEX_RE.sub("", text or "")
    if len(cleaned) != 8:
        return None
    try:
        return bytes.fromhex(cleaned)
    except ValueError:
        return None


def _bytes_to_hex_spaced(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


# Real (challenge, response) pairs have a gap of ~0-5 ms; allow a wider
# window for clock jitter. Stale heartbeats fall outside it.
_PAIR_MIN_GAP_MS = -2.0
_PAIR_MAX_GAP_MS = 50.0


def _pair_by_timestamp(chal_ts_list, resp_ts_list, max_pairs=None
                        ) -> List[Tuple[bytes, bytes]]:
    chals = sorted(
        [(p[1:5], ts) for p, ts in chal_ts_list
         if len(p) == 5 and p[0] == 0x00],
        key=lambda x: x[1])
    resps = sorted(
        [(p[1:5], ts) for p, ts in resp_ts_list
         if len(p) == 5 and p[0] == 0x04],
        key=lambda x: x[1])

    used_chal_indices: set = set()
    pairs: List[Tuple[bytes, bytes]] = []
    for r_bytes, r_ts in resps:
        best_idx = None
        best_abs_gap = None
        for ci in range(len(chals)):
            if ci in used_chal_indices:
                continue
            c_ts = chals[ci][1]
            gap_ms = (r_ts - c_ts).total_seconds() * 1000.0
            if _PAIR_MIN_GAP_MS <= gap_ms <= _PAIR_MAX_GAP_MS:
                ag = abs(gap_ms)
                if best_abs_gap is None or ag < best_abs_gap:
                    best_abs_gap = ag
                    best_idx = ci
        if best_idx is not None:
            used_chal_indices.add(best_idx)
            pairs.append((chals[best_idx][0], r_bytes))
            if max_pairs is not None and len(pairs) >= max_pairs:
                break
    return pairs


# ── Aggregator ─────────────────────────────────────────────────────────────

class _PayloadAggregator:
    """Per-payload count + first/last timestamp for one CAN ID."""

    def __init__(self):
        self.entries: Dict[str, Tuple[int, datetime, datetime]] = {}

    def record(self, payload: bytes) -> None:
        key = payload.hex().upper()
        now = datetime.now()
        cur = self.entries.get(key)
        if cur is None:
            self.entries[key] = (1, now, now)
        else:
            count, first_ts, _ = cur
            self.entries[key] = (count + 1, first_ts, now)

    def clear(self):
        self.entries.clear()

    def unique_count(self) -> int:
        return len(self.entries)

    def items_in_order(self):
        for key, (cnt, first_ts, last_ts) in self.entries.items():
            yield key, cnt, first_ts, last_ts


# ── Embedded sniffer view ──────────────────────────────────────────────────

class _SnifferTab(QWidget):
    """Two aggregated frame tables + Clear/Save.
    Owns the Elm327Sniffer; Start/Stop is driven from the PIN Extractor."""

    def __init__(self, serial_port: serial.Serial, log_callback,
                 parent=None):
        super().__init__(parent)
        self._sniffer = Elm327Sniffer(serial_port, self)
        self._agg_chal = _PayloadAggregator()
        self._agg_resp = _PayloadAggregator()
        self._total_frames = 0
        self._dirty = False
        self._log_callback = log_callback
        self._streaming = False

        self._build_ui()
        self._wire_signals()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(UI_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh_tables_if_dirty)
        self._refresh_timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)

        self.chalGroup = QGroupBox(
            f"Challenge"
            "  —  0 unique payloads")
        gl = QVBoxLayout(self.chalGroup)
        gl.setContentsMargins(6, 4, 6, 4)
        gl.setSpacing(2)
        self.chalTable = QTableWidget(0, 3)
        self.chalTable.setHorizontalHeaderLabels(["Payload (hex)", "Count", "Last seen"])
        h = self.chalTable.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.chalTable.verticalHeader().setVisible(False)
        self.chalTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.chalTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.chalTable.setFont(font)
        # Cap at ~4 data rows + header; scrollbar appears for more rows.
        self.chalTable.setMaximumHeight(160)
        gl.addWidget(self.chalTable)
        root.addWidget(self.chalGroup)

        self.respGroup = QGroupBox(
            f"Response"
            "  —  0 unique payloads")
        gl = QVBoxLayout(self.respGroup)
        gl.setContentsMargins(6, 4, 6, 4)
        gl.setSpacing(2)
        self.respTable = QTableWidget(0, 3)
        self.respTable.setHorizontalHeaderLabels(["Payload (hex)", "Count", "Last seen"])
        h = self.respTable.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.respTable.verticalHeader().setVisible(False)
        self.respTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.respTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.respTable.setFont(font)
        self.respTable.setMaximumHeight(160)
        gl.addWidget(self.respTable)
        root.addWidget(self.respGroup)

        status_row = QHBoxLayout()
        self.totalLabel = QLabel("Total frames: 0    Stream: ● IDLE")
        status_row.addWidget(self.totalLabel)
        status_row.addStretch()

        self.clearBtn = QPushButton("Clear")
        status_row.addWidget(self.clearBtn)
        self.saveBtn = QPushButton("Save log…")
        status_row.addWidget(self.saveBtn)
        root.addLayout(status_row)

    def _wire_signals(self):
        self.clearBtn.clicked.connect(self._on_clear)
        self.saveBtn.clicked.connect(self._on_save)
        # AT-command status stream is suppressed; only frames feed the UI.
        self._sniffer.frameReceived.connect(self._on_frame)

    def begin_stream(self):
        self._streaming = True
        self._set_stream_status(True)

    def end_stream(self):
        self._streaming = False
        self._set_stream_status(False)

    def log_message(self, msg: str):
        if self._log_callback:
            self._log_callback(msg)

    @Slot()
    def _on_clear(self):
        self._agg_chal.clear()
        self._agg_resp.clear()
        self._total_frames = 0
        self._dirty = True
        self._refresh_tables_if_dirty()

    @Slot()
    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save aggregated capture",
            f"sniff_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# PyPSADiag CAN sniffer aggregated capture\n")
                f.write(f"# saved: {datetime.now().isoformat()}\n")
                f.write(f"# total frames: {self._total_frames}\n\n")
                f.write(f"## Challenge\n")
                for hx, cnt, _first, last_ts in self._agg_chal.items_in_order():
                    f.write(f"  {self._fmt_hex(hx)}   count={cnt}   "
                            f"last={last_ts.isoformat(timespec='milliseconds')}\n")
                f.write(f"\n## Response\n")
                for hx, cnt, _first, last_ts in self._agg_resp.items_in_order():
                    f.write(f"  {self._fmt_hex(hx)}   count={cnt}   "
                            f"last={last_ts.isoformat(timespec='milliseconds')}\n")
        except OSError as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return
        self._log(f"Saved to {path}")

    @Slot(int, bytes)
    def _on_frame(self, can_id: int, payload: bytes):
        if can_id == CHALLENGE_ID:
            self._total_frames += 1
            self._agg_chal.record(payload)
            self._dirty = True
        elif can_id == RESPONSE_ID:
            self._total_frames += 1
            self._agg_resp.record(payload)
            self._dirty = True

    @Slot(str)
    def _log(self, msg: str):
        if self._log_callback:
            self._log_callback(f"[Sniffer] {msg}")

    @Slot(str)
    def _log_error(self, msg: str):
        if self._log_callback:
            self._log_callback(f"[Sniffer ERROR] {msg}")

    def _set_stream_status(self, live: bool):
        label = f"Total frames: {self._total_frames}    Stream: ● " + (
            "LIVE" if live else "IDLE")
        self.totalLabel.setText(label)
        self.totalLabel.setStyleSheet(
            "color: #1a7f37; font-weight: bold;" if live else "color: #888;")

    @staticmethod
    def _fmt_hex(hex_no_spaces: str) -> str:
        return " ".join(hex_no_spaces[i:i+2] for i in range(0, len(hex_no_spaces), 2))

    def _refresh_tables_if_dirty(self):
        if not self._dirty:
            return
        self._dirty = False
        self._refresh_one(self.chalTable, self._agg_chal, self.chalGroup,
                          CHALLENGE_ID, "Challenge")
        self._refresh_one(self.respTable, self._agg_resp, self.respGroup,
                          RESPONSE_ID, "Response")
        self._set_stream_status(self._streaming)

    def _refresh_one(self, table: QTableWidget, agg: _PayloadAggregator,
                     group: QGroupBox, cid: int, label: str):
        rows = list(agg.items_in_order())
        table.setRowCount(len(rows))
        for i, (hx, cnt, _first_ts, last_ts) in enumerate(rows):
            pl_item = QTableWidgetItem(self._fmt_hex(hx))
            cnt_item = QTableWidgetItem(str(cnt))
            cnt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ts_item = QTableWidgetItem(last_ts.strftime("%H:%M:%S.%f")[:-3])
            for it in (pl_item, cnt_item, ts_item):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 0, pl_item)
            table.setItem(i, 1, cnt_item)
            table.setItem(i, 2, ts_item)
        group.setTitle(
            f"{label}  —  {len(rows)} unique payloads")

    def latest_pairs(self, n: int = 4) -> List[Tuple[bytes, bytes]]:
        return _pair_by_timestamp(
            ((bytes.fromhex(hx), first_ts)
             for hx, _cnt, first_ts, _last in self._agg_chal.items_in_order()),
            ((bytes.fromhex(hx), first_ts)
             for hx, _cnt, first_ts, _last in self._agg_resp.items_in_order()),
            max_pairs=n)

    def shutdown(self):
        if self._streaming:
            try:
                self._sniffer.stop_sniff()
            except Exception:
                pass


# ── PIN Calculator (manual paste) ──────────────────────────────────────────

class _PairRowWidgets:
    __slots__ = ("chal_edit", "resp_edit", "chal_ok", "resp_ok")
    def __init__(self, chal_edit, resp_edit, chal_ok, resp_ok):
        self.chal_edit = chal_edit
        self.resp_edit = resp_edit
        self.chal_ok = chal_ok
        self.resp_ok = resp_ok


class _ExtractorTab(QWidget):
    """Manual PIN calculator — paste pairs or pull them from the sniffer."""

    def __init__(self, sniffer_tab: _SnifferTab, parent=None):
        super().__init__(parent)
        self._sniffer_tab = sniffer_tab
        self._rows: List[_PairRowWidgets] = []
        self._worker: Optional[PinExtractorWorker] = None
        self._last_pin: Optional[str] = None
        self._build_ui()
        for _ in range(4):
            self._add_row()

    def _build_ui(self):
        root = QVBoxLayout(self)

        note = QLabel(
            "Manual PIN Calculator. Paste Challenge-Response pairs for calculation.<br>"
            "<i>4 pairs always produce a unique PIN. "
            "A single pair can have multiple collisions.</i>")
        note.setWordWrap(True)
        root.addWidget(note)

        self.pairsGroup = QGroupBox("Pairs")
        self.pairsGrid = QGridLayout(self.pairsGroup)
        self.pairsGrid.addWidget(QLabel("<b>#</b>"), 0, 0)
        self.pairsGrid.addWidget(QLabel("<b>Challenge (4 hex bytes)</b>"), 0, 1)
        self.pairsGrid.addWidget(QLabel("<b>Response (4 hex bytes)</b>"), 0, 2)
        root.addWidget(self.pairsGroup)

        btns = QHBoxLayout()
        self.addRowBtn = QPushButton("+ Add pair")
        self.addRowBtn.clicked.connect(self._add_row)
        btns.addWidget(self.addRowBtn)
        self.delRowBtn = QPushButton("− Remove last")
        self.delRowBtn.clicked.connect(self._remove_row)
        btns.addWidget(self.delRowBtn)
        self.autoFillBtn = QPushButton("↻ Auto-fill from Extractor tab")
        self.autoFillBtn.clicked.connect(self._auto_fill_from_sniffer)
        btns.addWidget(self.autoFillBtn)
        self.clearAllBtn = QPushButton("✕ Clear all")
        self.clearAllBtn.clicked.connect(self._clear_all)
        btns.addWidget(self.clearAllBtn)
        btns.addStretch()
        root.addLayout(btns)

        ext_group = QGroupBox(
            "PIN calculation")
        ext_layout = QVBoxLayout(ext_group)
        ext_btn_row = QHBoxLayout()
        self.extractBtn = QPushButton("⚡ Calculate PIN")
        self.extractBtn.clicked.connect(self._start_extraction)
        ext_btn_row.addWidget(self.extractBtn)
        self.stopExtractBtn = QPushButton("■ Stop")
        self.stopExtractBtn.setEnabled(False)
        self.stopExtractBtn.clicked.connect(self._stop_extraction)
        ext_btn_row.addWidget(self.stopExtractBtn)
        ext_btn_row.addStretch()
        ext_layout.addLayout(ext_btn_row)

        self.progress = QProgressBar()
        self.progress.setMaximum(36 ** 4)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m  (%p%)")
        ext_layout.addWidget(self.progress)

        root.addWidget(ext_group)

        res_group = QGroupBox("Result")
        rl = QVBoxLayout(res_group)
        self.resultLabel = QLabel("<i>(no run yet)</i>")
        f = QFont("Consolas", 11)
        f.setStyleHint(QFont.Monospace)
        self.resultLabel.setFont(f)
        self.resultLabel.setWordWrap(True)
        self.resultLabel.setMinimumHeight(40)
        self.resultLabel.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.resultLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rl.addWidget(self.resultLabel)
        self.copyBtn = QPushButton("📋 Copy PIN to clipboard")
        self.copyBtn.setEnabled(False)
        self.copyBtn.clicked.connect(self._copy_pin)
        rl.addWidget(self.copyBtn)
        root.addWidget(res_group)

    def _add_row(self):
        idx = len(self._rows)
        if idx >= 16:
            return
        row = idx + 1
        num_label = QLabel(f"{row}")
        chal_edit = QLineEdit()
        chal_edit.setPlaceholderText("e.g. 00 00 00 00")
        chal_edit.setFont(self._mono())
        resp_edit = QLineEdit()
        resp_edit.setPlaceholderText("e.g. FF FF FF FF")
        resp_edit.setFont(self._mono())
        chal_ok = QLabel(" ")
        resp_ok = QLabel(" ")

        chal_edit.textChanged.connect(
            lambda t, lbl=chal_ok: self._validate(t, lbl))
        resp_edit.textChanged.connect(
            lambda t, lbl=resp_ok: self._validate(t, lbl))

        self.pairsGrid.addWidget(num_label, row, 0)
        self.pairsGrid.addWidget(chal_edit, row, 1)
        self.pairsGrid.addWidget(resp_edit, row, 2)
        self.pairsGrid.addWidget(chal_ok, row, 3)
        self.pairsGrid.addWidget(resp_ok, row, 4)

        self._rows.append(_PairRowWidgets(chal_edit, resp_edit, chal_ok, resp_ok))

    def _remove_row(self):
        if not self._rows:
            return
        idx = len(self._rows)
        for col in range(5):
            item = self.pairsGrid.itemAtPosition(idx, col)
            if item and item.widget():
                w = item.widget()
                self.pairsGrid.removeWidget(w)
                w.deleteLater()
        self._rows.pop()

    @staticmethod
    def _validate(text: str, label: QLabel):
        b = _hex_to_bytes4(text)
        if b is not None:
            label.setText("✓")
            label.setStyleSheet("color: #1a7f37;")
        elif text.strip():
            label.setText("✗")
            label.setStyleSheet("color: #b71c1c;")
        else:
            label.setText(" ")
            label.setStyleSheet("")

    @staticmethod
    def _mono() -> QFont:
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        return f

    @Slot()
    def _clear_all(self):
        for r in self._rows:
            r.chal_edit.clear()
            r.resp_edit.clear()
        self.resultLabel.setText("<i>(no run yet)</i>")
        self.copyBtn.setEnabled(False)
        self.progress.setValue(0)

    @Slot()
    def _auto_fill_from_sniffer(self):
        while len(self._rows) < 4:
            self._add_row()
        pairs = self._sniffer_tab.latest_pairs(n=len(self._rows))
        if not pairs:
            QMessageBox.information(
                self, "No pairs",
                "No (challenge, response) pairs captured yet on the Extractor tab.")
            return
        for i, (ch, rs) in enumerate(pairs):
            if i >= len(self._rows):
                break
            self._rows[i].chal_edit.setText(_bytes_to_hex_spaced(ch))
            self._rows[i].resp_edit.setText(_bytes_to_hex_spaced(rs))

    @Slot()
    def _start_extraction(self):
        if self._worker is not None and self._worker.isRunning():
            return

        ext_pairs: List[Tuple[int, int]] = []
        for i, row in enumerate(self._rows, 1):
            cb = _hex_to_bytes4(row.chal_edit.text())
            rb = _hex_to_bytes4(row.resp_edit.text())
            if cb is None and rb is None:
                continue
            if cb is None or rb is None:
                QMessageBox.warning(
                    self, "Incomplete pair",
                    f"Row {i}: both Challenge and Response must be exactly "
                    f"4 hex bytes (8 hex digits, spaces ignored).")
                return
            ch_int = int.from_bytes(cb, "big")
            rs_int = int.from_bytes(rb, "big")
            ext_pairs.append((ch_int, rs_int))

        if not ext_pairs:
            QMessageBox.warning(
                self, "No pairs",
                "Enter at least one (challenge, response) pair.")
            return

        self.extractBtn.setEnabled(False)
        self.stopExtractBtn.setEnabled(True)
        self.progress.setValue(0)
        self.resultLabel.setText("<i>working…</i>")
        self.copyBtn.setEnabled(False)

        self._worker = PinExtractorWorker(ext_pairs, self)
        self._worker.progressSignal.connect(self._on_progress)
        self._worker.foundSignal.connect(self._on_found)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    @Slot()
    def _stop_extraction(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()

    @Slot(int, int)
    def _on_progress(self, done: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    @Slot(list)
    def _on_found(self, cands: List[str]):
        if not cands:
            self.resultLabel.setText(
                "<span style='color:#b71c1c'>No PIN found.</span><br>"
                "<i>The pairs may be from different ECUs or corrupted."
                "Double-check your hex.</i>")
            self.copyBtn.setEnabled(False)
            self._last_pin = None
        elif len(cands) == 1:
            pin = cands[0]
            self.resultLabel.setText(
                f"<span style='color:#1a7f37'><b>PIN = {pin}</b></span><br>"
                f"<i>Matched all {self._pair_count()} pair(s) ✓</i>")
            self._last_pin = pin
            self.copyBtn.setEnabled(True)
        else:
            preview_n = 10
            preview = ", ".join(cands[:preview_n])
            more = f" (+{len(cands) - preview_n} more)" if len(cands) > preview_n else ""
            self.resultLabel.setText(
                f"<b>{len(cands)} candidates:</b> {preview}{more}<br>"
                f"<i>Add another (challenge, response) pair to disambiguate.</i>")
            self._last_pin = None
            self.copyBtn.setEnabled(False)

    @Slot()
    def _on_worker_finished(self):
        self.extractBtn.setEnabled(True)
        self.stopExtractBtn.setEnabled(False)

    def _pair_count(self) -> int:
        return sum(
            1 for r in self._rows
            if _hex_to_bytes4(r.chal_edit.text())
            and _hex_to_bytes4(r.resp_edit.text()))

    @Slot()
    def _copy_pin(self):
        if self._last_pin:
            QGuiApplication.clipboard().setText(self._last_pin)


# ── PIN Extractor (one-button automatic flow) ──────────────────────────────

class _AutoExtractorTab(QWidget):
    """One-button extraction with double-batch verification.
    Sniffs continuously: pairs 1-4 → PIN #1, pairs 5-8 → PIN #2, compare."""

    PAIRS_PER_BATCH = 4

    STATE_IDLE              = 0
    STATE_COLLECTING_BATCH1 = 1
    STATE_EXTRACTING_BATCH1 = 2
    STATE_COLLECTING_BATCH2 = 3
    STATE_EXTRACTING_BATCH2 = 4
    STATE_DONE              = 5

    def __init__(self, sniffer_tab: _SnifferTab, parent=None):
        super().__init__(parent)
        self._sniffer_tab = sniffer_tab
        self._state = self.STATE_IDLE

        # Private append-only pool, one entry per unique payload.
        self._chal_payloads_ts: List[Tuple[bytes, datetime]] = []
        self._resp_payloads_ts: List[Tuple[bytes, datetime]] = []

        self._pin1: Optional[str] = None
        self._pin2: Optional[str] = None
        self._worker: Optional[PinExtractorWorker] = None

        # Tracks whether we're currently subscribed to frameReceived, so we
        # never call disconnect twice (PySide6 emits a noisy RuntimeWarning
        # via libpyside on stray disconnects — try/except can't suppress it).
        self._frame_handler_connected = False

        self._anim_base = ""
        self._dot_count = 0

        self._build_ui()

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(500)
        self._anim_timer.timeout.connect(self._tick_animation)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        note = QLabel(
            "<b>Automatic PIN extraction.</b><br>"
            "Press <b>▶ Extract PIN</b> and turn ignition to <b>ON</b>.  "
            "If only a single pair is captured - switch ignition ON/OFF to capture more, then use PIN Calculator.")
        note.setWordWrap(True)
        root.addWidget(note)

        btn_row = QHBoxLayout()
        self.extractBtn = QPushButton("▶ Extract PIN")
        big_font = QFont()
        big_font.setPointSize(12)
        big_font.setBold(True)
        self.extractBtn.setFont(big_font)
        self.extractBtn.setMinimumHeight(34)
        self.extractBtn.clicked.connect(self._on_extract_clicked)
        btn_row.addWidget(self.extractBtn, 2)

        self.stopBtn = QPushButton("■ Stop")
        self.stopBtn.setFont(big_font)
        self.stopBtn.setMinimumHeight(34)
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.stopBtn, 1)
        root.addLayout(btn_row)

        # status + detail share a row to save vertical space
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(8)
        self.statusLabel = QLabel("")
        f = QFont("Consolas", 11)
        f.setStyleHint(QFont.Monospace)
        self.statusLabel.setFont(f)
        self.statusLabel.setStyleSheet("color: white; padding: 1px;")
        info_row.addWidget(self.statusLabel)
        self.detailLabel = QLabel("")
        self.detailLabel.setStyleSheet("color: white;")
        info_row.addWidget(self.detailLabel, 1)
        root.addLayout(info_row)

        res_group = QGroupBox("Result")
        rl = QVBoxLayout(res_group)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(4)
        self.resultLabel = QLabel("<i>(idle)</i>")
        rf = QFont("Consolas", 11)
        rf.setStyleHint(QFont.Monospace)
        self.resultLabel.setFont(rf)
        self.resultLabel.setWordWrap(True)
        # Stable min-height — keeps the panel from jumping on text change.
        self.resultLabel.setMinimumHeight(28)
        self.resultLabel.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.resultLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rl.addWidget(self.resultLabel)
        self.copyBtn = QPushButton("📋 Copy PIN to clipboard")
        self.copyBtn.setEnabled(False)
        self.copyBtn.clicked.connect(self._copy_pin)
        rl.addWidget(self.copyBtn)
        root.addWidget(res_group)

        sniffer_group = QGroupBox("Live CAN frames")
        sg_layout = QVBoxLayout(sniffer_group)
        sg_layout.setContentsMargins(6, 4, 6, 4)
        sg_layout.setSpacing(2)
        sg_layout.addWidget(self._sniffer_tab)
        root.addWidget(sniffer_group)
        # Any spare vertical space goes to the bottom — keeps the tables
        # locked to their single-row height instead of growing.
        root.addStretch(1)

    def shutdown(self):
        if self._state != self.STATE_IDLE:
            self._abort("Closed before completion.")

    @Slot()
    def _on_extract_clicked(self):
        if self._state != self.STATE_IDLE:
            return
        self._pin1 = None
        self._pin2 = None
        self._chal_payloads_ts.clear()
        self._resp_payloads_ts.clear()
        self.resultLabel.setText("<i>working…</i>")
        self.copyBtn.setEnabled(False)
        self.extractBtn.setEnabled(False)
        self.stopBtn.setEnabled(True)

        self._connect_frame_handler()
        try:
            self._sniffer_tab._sniffer.start_sniff([CHALLENGE_ID, RESPONSE_ID])
        except Exception as e:
            self._abort(f"Failed to start sniff: {e}")
            return
        self._sniffer_tab.begin_stream()
        self._sniffer_tab.log_message("[PIN Extractor]: Started")

        self._state = self.STATE_COLLECTING_BATCH1
        self._start_animation("Extracting")
        self._update_detail(batch_no=1, valid_pairs=0)

    @Slot()
    def _on_stop_clicked(self):
        if self._state == self.STATE_IDLE:
            return
        self._abort("Stopped by user.")

    @Slot(int, bytes)
    def _on_frame(self, can_id: int, payload: bytes):
        if self._state in (self.STATE_IDLE,
                            self.STATE_EXTRACTING_BATCH2,
                            self.STATE_DONE):
            return

        now = datetime.now()
        if can_id == CHALLENGE_ID:
            if not any(p == payload for p, _ in self._chal_payloads_ts):
                self._chal_payloads_ts.append((payload, now))
        elif can_id == RESPONSE_ID:
            if not any(p == payload for p, _ in self._resp_payloads_ts):
                self._resp_payloads_ts.append((payload, now))
        else:
            return

        all_pairs = _pair_by_timestamp(self._chal_payloads_ts,
                                        self._resp_payloads_ts)

        if self._state == self.STATE_COLLECTING_BATCH1:
            self._update_detail(batch_no=1, valid_pairs=len(all_pairs))
            if len(all_pairs) >= self.PAIRS_PER_BATCH:
                self._start_worker_for_batch(1, all_pairs[:self.PAIRS_PER_BATCH])

        elif self._state == self.STATE_EXTRACTING_BATCH1:
            # Sniff continues while batch-1 worker runs — show batch-2 progress.
            already_have_for_batch2 = max(
                0, len(all_pairs) - self.PAIRS_PER_BATCH)
            self._update_detail_batch2_during_b1_work(already_have_for_batch2)

        elif self._state == self.STATE_COLLECTING_BATCH2:
            extra = max(0, len(all_pairs) - self.PAIRS_PER_BATCH)
            self._update_detail(batch_no=2, valid_pairs=extra)
            if len(all_pairs) >= self.PAIRS_PER_BATCH * 2:
                self._start_worker_for_batch(
                    2, all_pairs[self.PAIRS_PER_BATCH:self.PAIRS_PER_BATCH*2])

    def _start_worker_for_batch(self, batch_no: int,
                                  pairs: List[Tuple[bytes, bytes]]):
        self._state = (self.STATE_EXTRACTING_BATCH1 if batch_no == 1
                       else self.STATE_EXTRACTING_BATCH2)
        self._update_detail(batch_no, len(pairs), searching=True)

        # Batch 2 is the last one — stop sniffing.
        if batch_no == 2:
            self._disconnect_frame_handler()
            try:
                self._sniffer_tab._sniffer.stop_sniff()
            except Exception:
                pass
            self._sniffer_tab.end_stream()

        ext_pairs = [(int.from_bytes(c, "big"), int.from_bytes(r, "big"))
                     for c, r in pairs]
        self._worker = PinExtractorWorker(ext_pairs, self)
        self._worker.foundSignal.connect(self._on_extraction_done)
        self._worker.start()

    @Slot(list)
    def _on_extraction_done(self, candidates: List[str]):
        if self._state == self.STATE_EXTRACTING_BATCH1:
            if len(candidates) == 1:
                self._pin1 = candidates[0]
                all_pairs = _pair_by_timestamp(self._chal_payloads_ts,
                                                self._resp_payloads_ts)
                if len(all_pairs) >= self.PAIRS_PER_BATCH * 2:
                    self._start_worker_for_batch(
                        2, all_pairs[self.PAIRS_PER_BATCH:self.PAIRS_PER_BATCH*2])
                else:
                    self._state = self.STATE_COLLECTING_BATCH2
                    self._update_detail(
                        batch_no=2,
                        valid_pairs=max(0, len(all_pairs) - self.PAIRS_PER_BATCH))
            else:
                self._abort(
                    "Batch 1: " + ("no PIN found"
                                   if not candidates
                                   else f"{len(candidates)} candidates ({', '.join(candidates)})"))
        elif self._state == self.STATE_EXTRACTING_BATCH2:
            if len(candidates) == 1:
                self._pin2 = candidates[0]
                self._compare_and_finish()
            else:
                self._abort(
                    "Batch 2: " + ("no PIN found"
                                   if not candidates
                                   else f"{len(candidates)} candidates"))

    def _compare_and_finish(self):
        # Defensive double-stop — sniff was already stopped at batch-2 start.
        self._disconnect_frame_handler()
        try:
            self._sniffer_tab._sniffer.stop_sniff()
        except Exception:
            pass
        self._sniffer_tab.end_stream()

        self._stop_animation()
        self.detailLabel.setText("")
        if self._pin1 == self._pin2:
            self.resultLabel.setText(
                f"<span style='color:#1a7f37'><b>PIN = {self._pin1}</b></span>"
                f"  <i style='color:#888'>(verified)</i>")
            self.copyBtn.setEnabled(True)
        else:
            self.resultLabel.setText(
                f"<span style='color:#b71c1c'><b>Mismatch:</b></span> "
                f"batch 1 = {self._pin1}, batch 2 = {self._pin2}")
            self.copyBtn.setEnabled(False)
        self._state = self.STATE_IDLE
        self.extractBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
        self._sniffer_tab.log_message("[PIN Extractor]: Stopped")

    def _abort(self, reason: str):
        # `reason` is intentionally not displayed — keeps Result one-line.
        self._disconnect_frame_handler()
        try:
            self._sniffer_tab._sniffer.stop_sniff()
        except Exception:
            pass
        self._sniffer_tab.end_stream()
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self._stop_animation()
        self.detailLabel.setText("")
        self.resultLabel.setText("<i>(idle)</i>")
        self.copyBtn.setEnabled(False)
        self._state = self.STATE_IDLE
        self.extractBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
        self._sniffer_tab.log_message("[PIN Extractor]: Stopped")

    def _connect_frame_handler(self):
        if not self._frame_handler_connected:
            self._sniffer_tab._sniffer.frameReceived.connect(self._on_frame)
            self._frame_handler_connected = True

    def _disconnect_frame_handler(self):
        # Guarded by a flag — disconnecting twice triggers a libpyside
        # RuntimeWarning that try/except can't suppress.
        if self._frame_handler_connected:
            try:
                self._sniffer_tab._sniffer.frameReceived.disconnect(self._on_frame)
            except (RuntimeError, TypeError):
                pass
            self._frame_handler_connected = False

    def _start_animation(self, base: str):
        self._anim_base = base
        self._dot_count = 0
        self._anim_timer.start()
        self._tick_animation()

    def _stop_animation(self):
        self._anim_timer.stop()
        self.statusLabel.setText("")

    def _tick_animation(self):
        self._dot_count = (self._dot_count % 3) + 1
        self.statusLabel.setText(self._anim_base + "." * self._dot_count)

    def _update_detail(self, batch_no: int, valid_pairs: int,
                        searching: bool = False):
        if searching:
            self.detailLabel.setText(
                f"  Batch {batch_no}/2 — searching 36⁴ PIN candidates "
                f"against {valid_pairs} pair(s)…")
        else:
            self.detailLabel.setText(
                f"  Batch {batch_no}/2 — collected {valid_pairs} of "
                f"{self.PAIRS_PER_BATCH} valid pair(s).")

    def _update_detail_batch2_during_b1_work(self, extra_pairs: int):
        self.detailLabel.setText(
            f"  Batch 1/2 — searching…    "
            f"already accumulated {extra_pairs}/{self.PAIRS_PER_BATCH} "
            f"pairs for batch 2/2.")

    @Slot()
    def _copy_pin(self):
        if self._pin1 and self._pin1 == self._pin2:
            QGuiApplication.clipboard().setText(self._pin1)


# ── Dialog ─────────────────────────────────────────────────────────────────

class CanFrameSniffDialog(QDialog):
    """Two-tab dialog: PIN Extractor (with embedded sniffer) + PIN Calculator."""

    def __init__(self, serial_port: serial.Serial, log_callback=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("PIN Extractor")
        # Sized to fit on 1366×768 / 1920×1080 with taskbar — user can grow.
        self.setMinimumSize(820, 680)
        self.resize(900, 740)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.tabs = QTabWidget()

        self.snifferTab     = _SnifferTab(serial_port, log_callback, self)
        self.autoExtractTab = _AutoExtractorTab(self.snifferTab, self)
        self.calculatorTab  = _ExtractorTab(self.snifferTab, self)

        self.tabs.addTab(self.autoExtractTab, "PIN Extractor")
        self.tabs.addTab(self.calculatorTab,  "PIN Calculator")
        layout.addWidget(self.tabs)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.closeBtn = QPushButton("Close")
        self.closeBtn.clicked.connect(self.close)
        bottom.addWidget(self.closeBtn)
        layout.addLayout(bottom)

    def closeEvent(self, event):
        self.autoExtractTab.shutdown()
        self.snifferTab.shutdown()
        super().closeEvent(event)
