"""game/ambush/trace.py - Trace buffer: satu-satunya jalur angka solver ke luar.

Solver (CSP/LS) TIDAK menggambar apa pun; ia memanggil tracer.emit() per
langkah. Overlay (fase 5) membaca snapshot untuk digambar, exporter CSV
membaca events mentah. Satu sumber, tiga konsumen.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class TraceBuffer:
    """Buffer event berurutan dengan stempel langkah + waktu relatif."""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._t0 = time.perf_counter()

    def emit(self, kind: str, **data: Any) -> Dict[str, Any]:
        """Catat satu event; kembalikan dict event (untuk step-mode)."""
        event = {
            "step": len(self.events),
            "t": time.perf_counter() - self._t0,
            "kind": kind,
            **data,
        }
        self.events.append(event)
        return event

    def clear(self) -> None:
        """Kosongkan buffer (antar run agar CSV tidak tercampur)."""
        self.events.clear()
        self._t0 = time.perf_counter()

    def of_kind(self, kind: str) -> List[Dict[str, Any]]:
        """Semua event satu jenis (untuk exporter CSV)."""
        return [e for e in self.events if e["kind"] == kind]

    def latest(self, kind: str) -> Optional[Dict[str, Any]]:
        """Event terakhir satu jenis (untuk snapshot overlay)."""
        for event in reversed(self.events):
            if event["kind"] == kind:
                return event
        return None
