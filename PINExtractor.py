"""
PINExtractor.py
"""
from __future__ import annotations

from typing import Iterable, List, Tuple

try:
    from PySide6.QtCore import QThread, Signal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    QThread = object  # type: ignore
    Signal = lambda *a, **kw: None  # type: ignore # noqa: E731


# ── Transform primitive (ludwig-v style) ───────────────────────────────────
SEC_1 = (0xB2, 0x3F, 0xAA)
SEC_2 = (0xB1, 0x02, 0xAB)
ALPHABET = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _transform(a: int, b: int, sec) -> int:
    """Inner cipher primitive: input (uint8, uint8, sec[3]) -> uint16."""
    data = ((a << 8) | b) & 0xFFFF
    data_s = data - 0x10000 if data & 0x8000 else data
    # C-truncated division (toward zero)
    sign = -1 if data_s < 0 else 1
    quot = sign * (abs(data_s) // sec[0])
    rem  = data_s - quot * sec[0]
    result = (rem * sec[2]) - (quot * sec[1])
    if result < 0:
        result += sec[0] * sec[2] + sec[1]
    return result & 0xFFFF


def compute_response(pin: bytes, challenge: int) -> int:
    """Compute the expected handshake response.
    """
    b0 = (challenge >> 24) & 0xFF
    b1 = (challenge >> 16) & 0xFF
    b2 = (challenge >>  8) & 0xFF
    b3 = challenge & 0xFF
    p0, p1, p2, p3 = pin[0], pin[1], pin[2], pin[3]

    t1 = _transform(b0, b2, SEC_1)
    t2 = _transform(p0, p3, SEC_2)
    res_msb = t1 | t2

    t3 = _transform(b1, b3, SEC_2)
    t4 = _transform(p1, p2, SEC_1)
    res_lsb = t3 | t4

    return ((res_msb << 16) | res_lsb) & 0xFFFFFFFF


# ── Multi-pair PIN extractor ────────────────────────────────────────────────

class PinExtractor:
    """Search the full 36^4 alphanumeric space for a PIN that satisfies
    every (challenge, response) pair given.
    """

    def __init__(self, pairs: Iterable[Tuple[int, int]]):
        self.pairs = [(int(c) & 0xFFFFFFFF, int(r) & 0xFFFFFFFF) for c, r in pairs]
        if not self.pairs:
            raise ValueError("need at least one (challenge, response) pair")

    def run(self, progress_cb=None, should_stop=None) -> List[str]:
        candidates: List[str] = []
        first_chal, first_resp = self.pairs[0]
        rest = self.pairs[1:]
        total = 36 ** 4
        i = 0
        # iterate alphabet^4
        for c0 in ALPHABET:
            for c1 in ALPHABET:
                if should_stop and should_stop():
                    return candidates
                if progress_cb:
                    progress_cb(i, total)
                for c2 in ALPHABET:
                    for c3 in ALPHABET:
                        i += 1
                        pin = bytes((c0, c1, c2, c3))
                        if compute_response(pin, first_chal) != first_resp:
                            continue
                        ok = True
                        for ch, rs in rest:
                            if compute_response(pin, ch) != rs:
                                ok = False; break
                        if ok:
                            candidates.append(pin.decode('ascii'))
        if progress_cb:
            progress_cb(total, total)
        return candidates


# ── Qt worker for GUI integration ──────────────────────────────────────────

class PinExtractorWorker(QThread):
    """QThread wrapper around PinExtractor for non-blocking GUI use."""
    logSignal      = Signal(str)
    progressSignal = Signal(int, int)
    foundSignal    = Signal(list)

    def __init__(self, pairs, parent=None):
        super().__init__(parent)
        self._pairs = pairs
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        self.logSignal.emit(
            f"[PinExtractor] searching {36**4:,} candidates against "
            f"{len(self._pairs)} pair(s)")
        try:
            extractor = PinExtractor(self._pairs)
        except ValueError as e:
            self.logSignal.emit(f"[PinExtractor] {e}")
            self.foundSignal.emit([])
            return
        cands = extractor.run(
            progress_cb=lambda d, t: self.progressSignal.emit(d, t),
            should_stop=lambda: self._stop)
        if not cands:
            self.logSignal.emit(
                "[PinExtractor] no PIN found — pairs may be from different "
                "ECUs, corrupted, or this isn't the right algorithm for "
                "that ECU.")
        elif len(cands) == 1:
            self.logSignal.emit(f"[PinExtractor] *** UNIQUE PIN: {cands[0]} ***")
        else:
            self.logSignal.emit(
                f"[PinExtractor] {len(cands)} candidates: " + ", ".join(cands))
        self.foundSignal.emit(cands)


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(
        description="Extract 4-char alphanumeric PIN from captured "
                    "(challenge, response) pairs.  Use multiple pairs for "
                    "unique disambiguation.")
    ap.add_argument("--pair", action="append", default=[], metavar="CHAL,RESP",
                    help="hex pair from CAN payloads, e.g. 9AFCF847,775749DB")
    args = ap.parse_args()

    if not args.pair:
        print("Usage: PINExtractor.py --pair CHAL,RESP [--pair CHAL,RESP ...]")
        print("  Challenge = 0x072 payload bytes [1..4] as 8 hex chars")
        print("  Response  = 0x0A8 payload bytes [1..4] as 8 hex chars")
        sys.exit(2)

    pairs = []
    for p in args.pair:
        c, r = p.split(",")
        pairs.append((int(c, 16), int(r, 16)))

    print(f"Extracting 4-char alphanumeric PIN from {len(pairs)} pair(s) "
          f"(search space = {36**4:,})...")
    extractor = PinExtractor(pairs)
    def show_progress(d, t):
        sys.stderr.write(f"\r {d*100//t:3d}%   ")
        sys.stderr.flush()
    cands = extractor.run(progress_cb=show_progress)
    sys.stderr.write("\n")
    if cands:
        for c in cands:
            print(f"PIN = {c}")
    else:
        print("No PIN found.")
