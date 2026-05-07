"""
EcuKeyBruteforce.py — PSA ECU key brute-forcer (embedded in PyPSADiag).

Equivalence-class set-pruning brute force for the 16-bit ECU key (PSA seed/key
algorithm).  The 65 536-key space partitions into equivalence classes by output
key for each given seed (the inner bitwise-OR step of `compute()` collapses
many distinct keys to the same output for any fixed seed).  Each ECU round-trip
therefore eliminates an entire equivalence class — typically hundreds of keys —
so we converge in ~50-200 rounds instead of brute-forcing 65 536 individually.

Self-contained — depends only on numpy (already in PyPSADiag's requirements)
and PySide6.  Plugs into PyPSADiag's `serialController` (DiagnosticAdapter)
which routes to the active transport (Serial / VCI / Bluetooth / WebSocket)
transparently.

Wiring:
    worker = BruteforceWorker(serialController, tx_id, rx_id, protocol)
    worker.logSignal.connect(textEdit.append)
    worker.progressSignal.connect(updateStatusBar)
    worker.doneSignal.connect(showResults)
    worker.start()           # runs on a QThread
    ...
    worker.stop()            # graceful shutdown
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, List, Tuple, Set

from PySide6.QtCore import QThread, Signal

try:
    import numpy as _np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── PSA seed/key algorithm (ludwig-v) ──────────────────────────────────────
def _i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _transform_scalar(data_msb: int, data_lsb: int, sec) -> int:
    data = _i32((data_msb << 8) | data_lsb)
    neg = False
    if data & 0x8000:
        data -= 0x10000
        data *= -1
        neg = True
    rem = data % sec[0]
    num = data // sec[0]
    if neg:
        rem = -rem
        num = -num
    dom1 = _i32(_i16(rem) * (sec[2] & 0xFF))
    dom2 = _i32(_i16(num) * (sec[1] & 0xFF))
    result = _i32(dom1 - dom2)
    if result < 0:
        result += (sec[0] * sec[2]) + sec[1]
    return result & 0xFFFF


SEC_1 = (0xB2, 0x3F, 0xAA)
SEC_2 = (0xB1, 0x02, 0xAB)


if HAS_NUMPY:
    def _transform_batch_np(data_msb, data_lsb, sec):
        np = _np
        data_msb = np.asarray(data_msb, dtype=np.int64)
        data_lsb = np.asarray(data_lsb, dtype=np.int64)
        data = (data_msb << 8) | data_lsb
        neg = (data & 0x8000) != 0
        data_abs = np.where(neg, 0x10000 - data, data)
        rem = data_abs % sec[0]
        num = data_abs // sec[0]
        rem = np.where(neg, -rem, rem)
        num = np.where(neg, -num, num)
        dom1 = rem * (sec[2] & 0xFF)
        dom2 = num * (sec[1] & 0xFF)
        result = dom1 - dom2
        result = ((result + 0x80000000) & 0xFFFFFFFF) - 0x80000000
        correction = sec[0] * sec[2] + sec[1]
        result = np.where(result < 0, result + correction, result)
        return (result & 0xFFFF).astype(np.int64)


class SeedKey:
    def compute(self, pin: int, chg: int) -> int:
        res_msb = _transform_scalar((pin >> 8) & 0xFF, pin & 0xFF, SEC_1) | \
                  _transform_scalar((chg >> 24) & 0xFF, chg & 0xFF, SEC_2)
        res_lsb = _transform_scalar((chg >> 16) & 0xFF, (chg >> 8) & 0xFF, SEC_1) | \
                  _transform_scalar((res_msb >> 8) & 0xFF, res_msb & 0xFF, SEC_2)
        return ((res_msb & 0xFFFF) << 16) | (res_lsb & 0xFFFF)

    if HAS_NUMPY:
        def keys_for_all_pins(self, chg: int):
            np = _np
            pins = np.arange(0x10000, dtype=np.int64)
            t1 = _transform_batch_np((pins >> 8) & 0xFF, pins & 0xFF, SEC_1)
            t2 = _transform_scalar((chg >> 24) & 0xFF, chg & 0xFF, SEC_2)
            res_msb = (t1 | t2).astype(np.int64)
            t3 = _transform_scalar((chg >> 16) & 0xFF, (chg >> 8) & 0xFF, SEC_1)
            t4 = _transform_batch_np((res_msb >> 8) & 0xFF, res_msb & 0xFF, SEC_2)
            res_lsb = (t3 | t4).astype(np.int64)
            return (((res_msb & 0xFFFF) << 16) | (res_lsb & 0xFFFF)).astype(np.uint32)


# ── NRC constants (UDS service 0x27) ───────────────────────────────────────
NRC_REQUIRED_TIME_DELAY     = "37"
NRC_INVALID_KEY             = "35"
NRC_EXCEED_NUMBER_ATTEMPT   = "36"


@dataclass
class BFConfig:
    tx_id: str = "752"
    rx_id: str = "652"
    protocol: str = "uds"                   # uds / kwp_is / kwp_hab
    sa_level: int = 2                       # 1 = 27 01/02, 2 = 27 03/04 (UDS only)
    pin_start: int = 0x0000
    pin_end: int   = 0xFFFF
    diag_session: str = "1003"
    keep_alive_cmd: str = "KU"
    stop_keep_alive_cmd: str = "S"
    stop_session_cmd: str = "1001"

    fresh_session_per_round: bool = True
    session_open_retries: int = 5
    session_open_backoff: float = 1.5

    # NRC 37 timer on PSA modules is typically 5-15 s; spacing retries out
    # gives that timer a chance to clear so the seed usually comes within
    # 4-7 retries instead of exhausting all of them.
    seed_retry_max: int = 14         # was 8
    seed_retry_delay: float = 1.5    # was 1.0  → max wait ≈ 21s per round
    # After a seed-exhaustion the ECU is in deep cooldown; if we try to
    # reopen the session immediately the first 1-2 attempts fail and we waste
    # ~4.5 s on the backoff dance.  Resting longer here lets the very next
    # session-open succeed on the first try, saving net wall time.
    post_seedfail_delay: float = 5.0 # was 1.5
    cooldown_after_36: float = 5.0

    converge_threshold: int = 4
    max_rounds: int = 1000

    verify_passes: int = 3
    verify_required: int = 2
    verify_inter_pass_delay: float = 1.5
    verify_pre_phase_cooldown: float = 5.0


@dataclass
class BFState:
    rounds: int = 0
    candidates_count: int = 65536
    confirmed: List[int] = field(default_factory=list)
    started_at: float = 0.0
    elapsed: float = 0.0


def _seed_subfunc(level: int, protocol: str) -> str:
    if protocol.startswith("kwp"):
        return "81" if level == 1 else "83"
    return "01" if level == 1 else "03"


def _key_subfunc(level: int, protocol: str) -> str:
    if protocol.startswith("kwp"):
        return "82" if level == 1 else "84"
    return "02" if level == 1 else "04"


def _get_nrc(reply: str, protocol: str) -> Optional[str]:
    """Extract the NRC byte from a 7F XX YY response.  Works for UDS (7F27)
    and KWP (7F27 too — same SA service id)."""
    if reply.startswith("7F27") and len(reply) >= 6:
        return reply[4:6].upper()
    return None


# ── Bruteforcer core (no Qt deps) ──────────────────────────────────────────
class Bruteforcer:
    def __init__(self, transport, cfg: BFConfig,
                 logger: Callable[[str], None] = print,
                 progress_cb: Callable = None,
                 hit_cb: Callable = None,
                 should_stop: Callable[[], bool] = None):
        self.t = transport
        self.cfg = cfg
        self.log = logger
        self.progress_cb = progress_cb or (lambda *a, **kw: None)
        self.hit_cb = hit_cb or (lambda *a, **kw: None)
        self._should_stop = should_stop or (lambda: False)
        self.algo = SeedKey()
        self._session_open = False
        self._session_open_total_fails = 0

        n = cfg.pin_end - cfg.pin_start + 1
        if HAS_NUMPY:
            self._mask = _np.zeros(0x10000, dtype=bool)
            self._mask[cfg.pin_start:cfg.pin_end + 1] = True
        else:
            self._set: Set[int] = set(range(cfg.pin_start, cfg.pin_end + 1))

        self.state = BFState(candidates_count=n, started_at=time.time())

    @property
    def candidates_count(self) -> int:
        if HAS_NUMPY:
            return int(self._mask.sum())
        return len(self._set)

    def _candidates_min(self) -> int:
        if HAS_NUMPY:
            return int(_np.argmax(self._mask))
        return min(self._set)

    def _candidates_sorted(self) -> List[int]:
        if HAS_NUMPY:
            return [int(p) for p in _np.where(self._mask)[0]]
        return sorted(self._set)

    def _intersect_class(self, p: int, seed: int) -> int:
        if HAS_NUMPY:
            keys = self.algo.keys_for_all_pins(seed)
            target = int(keys[p])
            cls_mask = (keys == target)
            cls_size = int((cls_mask & self._mask).sum())
            self._mask &= cls_mask
            return cls_size
        target = self.algo.compute(p, seed)
        cls = {q for q in self._set if self.algo.compute(q, seed) == target}
        sz = len(cls)
        self._set &= cls
        return sz

    def _subtract_class(self, p: int, seed: int) -> int:
        if HAS_NUMPY:
            keys = self.algo.keys_for_all_pins(seed)
            target = int(keys[p])
            cls_mask = (keys == target)
            cls_size = int((cls_mask & self._mask).sum())
            self._mask &= ~cls_mask
            return cls_size
        target = self.algo.compute(p, seed)
        cls = {q for q in self._set if self.algo.compute(q, seed) == target}
        sz = len(cls)
        self._set -= cls
        return sz

    # ── transport ──────────────────────────────────────────────────────────
    def _send(self, cmd: str) -> str:
        return self.t.send_receive(cmd)

    # ── session lifecycle ──────────────────────────────────────────────────
    def _open_session(self) -> bool:
        if self._send(f">{self.cfg.tx_id}:{self.cfg.rx_id}") != "OK":
            return False
        if self._send(self.cfg.keep_alive_cmd) != "OK":
            return False
        r = self._send(self.cfg.diag_session)
        ok = r.startswith("50") or (self.cfg.protocol.startswith("kwp") and r[:2] == "C1")
        self._session_open = ok
        return ok

    def _open_session_with_retry(self) -> bool:
        for i in range(self.cfg.session_open_retries):
            if self._open_session():
                if i >= 2:
                    self.log(f"  (session open recovered on attempt {i+1})")
                return True
            self._session_open_total_fails += 1
            wait = self.cfg.session_open_backoff * (i + 1)
            if i >= 2:
                self.log(f"  ! session open: attempt {i+1}/{self.cfg.session_open_retries} "
                         f"failed (lifetime fails: {self._session_open_total_fails}); "
                         f"retry in {wait:.1f}s")
            time.sleep(wait)
        self.log(f"  ! session open: exhausted {self.cfg.session_open_retries} retries "
                 f"(lifetime fails: {self._session_open_total_fails})")
        return False

    def _close_session(self) -> None:
        if not self._session_open:
            return
        try:
            self._send(self.cfg.stop_keep_alive_cmd)
            self._send(self.cfg.stop_session_cmd)
        except Exception:
            pass
        self._session_open = False

    # ── seed / key ─────────────────────────────────────────────────────────
    def _request_seed(self, *, label: str = "") -> Optional[int]:
        seed_sub = _seed_subfunc(self.cfg.sa_level, self.cfg.protocol)
        seed_cmd = "27" + seed_sub
        positive_prefix = "67" + seed_sub
        last_reply = None
        nrc_counts: dict = {}

        for _ in range(self.cfg.seed_retry_max):
            if self._should_stop():
                return None
            r = self._send(seed_cmd)
            last_reply = r
            if r.startswith(positive_prefix) and len(r) >= 12:
                try:
                    return int(r[4:12], 16)
                except ValueError:
                    return None
            nrc = _get_nrc(r, self.cfg.protocol)
            nrc_counts[nrc or "?"] = nrc_counts.get(nrc or "?", 0) + 1
            if nrc == NRC_REQUIRED_TIME_DELAY:
                if self.cfg.seed_retry_delay > 0:
                    time.sleep(self.cfg.seed_retry_delay)
                continue
            if nrc == NRC_EXCEED_NUMBER_ATTEMPT:
                self.log(f"  ! NRC 36 — reset session in {self.cfg.cooldown_after_36}s")
                self._close_session()
                time.sleep(self.cfg.cooldown_after_36)
                if not self._open_session_with_retry():
                    return None
                continue
            self.log(f"  ! unexpected reply to {seed_cmd}: {r}{f' [{label}]' if label else ''}")
            return None
        self.log(f"  ! seed retry exhausted ({self.cfg.seed_retry_max}) "
                 f"{f'[{label}] ' if label else ''}"
                 f"NRC={nrc_counts}, last={last_reply}")
        return None

    def _send_key(self, pin: int, seed: int) -> bool:
        key_sub = _key_subfunc(self.cfg.sa_level, self.cfg.protocol)
        computed = self.algo.compute(pin, seed)
        cmd = "27" + key_sub + f"{computed:08X}"
        positive = "67" + key_sub
        r = self._send(cmd)
        return r.upper() == positive

    # ── auto-detection of the right (session, SA level) combo ──────────────
    def _request_seed_once_for_detect(self) -> Optional[int]:
        """Single-shot seed for combo detection: tolerate NRC 37 only, no other retries."""
        seed_sub = _seed_subfunc(self.cfg.sa_level, self.cfg.protocol)
        seed_cmd = "27" + seed_sub
        positive_prefix = "67" + seed_sub
        for _ in range(3):
            if self._should_stop():
                return None
            r = self._send(seed_cmd)
            if r.startswith(positive_prefix) and len(r) >= 12:
                try:
                    return int(r[4:12], 16)
                except ValueError:
                    return None
            nrc = _get_nrc(r, self.cfg.protocol)
            if nrc == NRC_REQUIRED_TIME_DELAY:
                time.sleep(0.5)
                continue
            # Any other reply (NRC 22, 12, 11, 33...) — combo doesn't fit
            return None
        return None

    def _detect_combo(self) -> bool:
        """Try (session, SA-level) combos until one returns a seed.

        Order: configured default first, then most common alternatives.
        Engine ECUs often need SA L1; some flash-locked modules need 1002
        (Programming) instead of 1003 (Extended).  Each probe adds ~1-2 s.
        """
        candidates: List[Tuple[str, int]] = []
        candidates.append((self.cfg.diag_session, self.cfg.sa_level))
        if self.cfg.protocol == "uds":
            for sess in ("1003", "1002"):
                for lvl in (1, 2, 3):
                    if (sess, lvl) not in candidates:
                        candidates.append((sess, lvl))
        else:
            # KWP: only vary the SA level; session is protocol-defined
            for lvl in (1, 2, 3):
                if (self.cfg.diag_session, lvl) not in candidates:
                    candidates.append((self.cfg.diag_session, lvl))

        self.log("== Auto-detecting working session / SA-level combo ==")
        for sess, lvl in candidates:
            if self._should_stop():
                return False
            self.cfg.diag_session = sess
            self.cfg.sa_level = lvl
            sub = _seed_subfunc(lvl, self.cfg.protocol)
            self.log(f"   trying session={sess}, SA L{lvl}  (27 {sub})")
            if not self._open_session():
                self._close_session()
                self.log(f"     session-open failed, next combo")
                continue
            seed = self._request_seed_once_for_detect()
            self._close_session()
            if seed is not None:
                self.log(f"   * working combo found: session={sess}, "
                         f"SA L{lvl} (27 {sub}/27 {_key_subfunc(lvl, self.cfg.protocol)}); "
                         f"sample seed={seed:08X}")
                return True
            time.sleep(0.3)
        self.log("   ! no working SA combo found — aborting")
        return False

    # ── verification ───────────────────────────────────────────────────────
    def _verify_pin(self, pin: int) -> bool:
        ok = 0
        fail = 0
        attempts = 0
        max_attempts = self.cfg.verify_passes * 4
        max_fail = self.cfg.verify_passes - self.cfg.verify_required + 1

        while (ok < self.cfg.verify_required
               and fail < max_fail
               and attempts < max_attempts
               and not self._should_stop()):
            attempts += 1
            self.log(f"     verify attempt {attempts}/{max_attempts} for KEY {pin:04X}  "
                     f"(ok={ok}/{self.cfg.verify_required}, fail={fail}/{max_fail})")
            self._close_session()
            time.sleep(self.cfg.verify_inter_pass_delay)
            if not self._open_session_with_retry():
                self.log(f"     -- comm: session-open failed, retrying")
                continue
            seed = self._request_seed(label=f"verify KEY {pin:04X}")
            if seed is None:
                self.log(f"     -- comm: no seed, retrying")
                continue
            if self._send_key(pin, seed):
                ok += 1
                self.log(f"     OK    (seed={seed:08X})  ok={ok}/{self.cfg.verify_required}")
            else:
                fail += 1
                self.log(f"     FAIL  (seed={seed:08X})  fail={fail}/{max_fail}")

        return ok >= self.cfg.verify_required

    # ── main loop ──────────────────────────────────────────────────────────
    def run(self):
        backend = "numpy-batch" if HAS_NUMPY else "pure-python"
        self.log(f"== Brute force starting (set-pruning, {backend}) ==")
        self.log(f"   target {self.cfg.tx_id}:{self.cfg.rx_id}, "
                 f"protocol={self.cfg.protocol}, "
                 f"range {self.cfg.pin_start:04X}-{self.cfg.pin_end:04X}")
        self.log(f"   |candidates| = {self.candidates_count} initially")
        self.state.started_at = time.time()

        if not self._detect_combo():
            return
        self.log(f"== Pruning with session={self.cfg.diag_session}, "
                 f"SA L{self.cfg.sa_level} ==\n")

        round_idx = 0
        try:
            while (self.candidates_count > self.cfg.converge_threshold
                   and round_idx < self.cfg.max_rounds
                   and not self._should_stop()):
                if not self._session_open:
                    if not self._open_session_with_retry():
                        self.log("  ! session open exhausted retries — abort")
                        break

                seed = self._request_seed()
                if seed is None:
                    self._close_session()
                    time.sleep(self.cfg.post_seedfail_delay)
                    continue

                p = self._candidates_min()
                hit = self._send_key(p, seed)

                if hit:
                    cls_size = self._intersect_class(p, seed)
                    self.log(f"  *** HIT  key={p:04X} seed={seed:08X}  "
                             f"class_in_set={cls_size}  "
                             f"|candidates|: {self.state.candidates_count} -> {self.candidates_count}")
                    self.hit_cb(p, f"{seed:08X}", False)
                else:
                    self._subtract_class(p, seed)

                if self.cfg.fresh_session_per_round:
                    self._close_session()

                round_idx += 1
                self.state.rounds = round_idx
                self.state.candidates_count = self.candidates_count
                self.state.elapsed = time.time() - self.state.started_at

                rate = round_idx / max(self.state.elapsed, 1e-3)
                self.log(f"   round {round_idx:4d} | "
                         f"|candidates|={self.candidates_count:6d} | "
                         f"{rate:.1f} rnd/s | "
                         f"{self.state.elapsed:.0f}s")
                self.progress_cb(self.state.rounds, self.candidates_count,
                                 rate, self.state.elapsed,
                                 0, len(self.state.confirmed))
        except Exception as e:
            self.log(f"  !! exception in main loop: {e!r}")

        self._close_session()

        self.log(f"\n== Pruning done in {round_idx} rounds, "
                 f"{self.state.elapsed:.0f}s elapsed ==")
        cands = self._candidates_sorted()
        self.log(f"   {len(cands)} candidate KEY(s) remain: "
                 f"{[f'{p:04X}' for p in cands]}")

        if self._should_stop():
            return

        if cands and self.cfg.verify_pre_phase_cooldown > 0:
            self.log(f"   ... cooling down {self.cfg.verify_pre_phase_cooldown:.0f}s "
                     f"before verification ...")
            self._close_session()
            time.sleep(self.cfg.verify_pre_phase_cooldown)

        for cand in cands:
            if self._should_stop():
                break
            self.log(f"\n   Verifying KEY {cand:04X}:")
            if self._verify_pin(cand):
                self.log(f"   ###### CONFIRMED KEY: {cand:04X} ######")
                self.state.confirmed.append(cand)
                self.hit_cb(cand, "", True)
            else:
                self.log(f"   [REJECTED] KEY {cand:04X} fails repeated tests")

        self._close_session()
        self.log(f"\n== Done ==")
        self.log(f"   total rounds: {round_idx}, "
                 f"elapsed: {self.state.elapsed:.0f}s, "
                 f"confirmed: {len(self.state.confirmed)}")
        for p in self.state.confirmed:
            self.log(f"   [CONFIRMED] KEY: {p:04X}")


# ── Adapter: wrap PyPSADiag's serialController.sendReceive → send_receive ─
class _PyPSAAdapter:
    def __init__(self, serial_controller):
        self._sc = serial_controller

    def send_receive(self, cmd: str) -> str:
        return self._sc.sendReceive(cmd)


# ── QThread worker ─────────────────────────────────────────────────────────
class BruteforceWorker(QThread):
    """Runs Bruteforcer.run() on a background thread; emits Qt signals."""
    logSignal = Signal(str)
    progressSignal = Signal(int, int, float, float, int, int)
    # rounds, candidates, rate, elapsed_sec, hits, confirmed
    doneSignal = Signal(list)
    # confirmed: list[int]

    def __init__(self, serial_controller, tx_id, rx_id, protocol, parent=None):
        super().__init__(parent)
        self._adapter = _PyPSAAdapter(serial_controller)
        self._stop = False

        cfg = BFConfig(tx_id=tx_id, rx_id=rx_id, protocol=protocol)
        if protocol.startswith("kwp"):
            cfg.diag_session = "10C0" if protocol == "kwp_hab" else "1003"
            cfg.keep_alive_cmd = "KK"
        else:
            cfg.diag_session = "1003"
            cfg.keep_alive_cmd = "KU"
        self.cfg = cfg

    def stop(self):
        self._stop = True

    def run(self):
        bf = Bruteforcer(
            self._adapter, self.cfg,
            logger=lambda s: self.logSignal.emit(s),
            progress_cb=lambda r, c, rate, el, h, cf:
                self.progressSignal.emit(r, c, rate, el, h, cf),
            hit_cb=lambda p, s, conf: None,
            should_stop=lambda: self._stop,
        )
        try:
            bf.run()
        except Exception as e:
            self.logSignal.emit(f"!! worker exception: {e!r}")
        self.doneSignal.emit(list(bf.state.confirmed))
