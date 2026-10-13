"""game/ambush/governor.py - Target difficulty adaptif dari riwayat battle.

Naik bila player menang (apalagi telak/beruntun), turun bila sering kalah,
dijepit [gov_min, gov_max]. Memegang riwayat (outcome, margin) untuk overlay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from game.ambush.config import AmbushConfig


@dataclass
class DifficultyGovernor:
    """State adaptif kecil: target + riwayat + streak beruntun."""

    cfg: AmbushConfig
    target: float = 0.5
    history: List[Tuple[str, float]] = field(default_factory=list)
    win_streak: int = 0
    loss_streak: int = 0

    def __post_init__(self) -> None:
        if not self.history:
            self.target = self.cfg.gov_init
        self._clamp()

    def _clamp(self) -> None:
        self.target = min(self.cfg.gov_max,
                          max(self.cfg.gov_min, self.target))

    last_progress: float = 1.0  # progres antrean terakhir (Fase 5)
    last_failed_at: object = None  # duel gagal ke-berapa (1-based) / None

    def update(self, outcome: str, margin: float = 0.0,
               progress: Optional[float] = None,
               failed_at: Optional[int] = None) -> float:
        """Catat satu hasil duel; kembalikan target baru.

        outcome: 'player' | 'npc' | 'draw'. margin 0..1 = sisa HP fraksional
        pihak menang (0 = menang tipis, 1 = menang telak tanpa lecet).
        progress (Fase 5): fraksi duel antrean dimenangkan (None = 1 duel).
        failed_at: duel ke-berapa player gugur (1-based, None bila menang).
        """
        margin = min(1.0, max(0.0, margin))
        self.last_progress = 1.0 if progress is None else progress
        self.last_failed_at = failed_at
        if outcome == "player":
            self.win_streak += 1
            self.loss_streak = 0
            # Telak + beruntun menaikkan lebih agresif (anti-bosan).
            self.target += (self.cfg.gov_up * (1.0 + margin)
                            * (1.0 + 0.5 * (self.win_streak - 1)))
        elif outcome == "npc":
            # Kalah: besar penurunan diskala PROGRES (Fase 6) — kalah tipis
            # (progres tinggi) hanya sedikit menurunkan; sapuan (progres
            # rendah) menurunkan penuh. Hanya kekalahan dengan progres
            # < 0.5 yang memperpanjang loss_streak (kalah tipis memutus
            # streak: bukan bukti slump). Tanpa ini target hanyut ke batas
            # bawah dalam 2 pertemuan walau progres tipikal 0.5-0.67.
            prog = 0.0 if progress is None else min(1.0, max(0.0, progress))
            if prog < 0.5:
                self.loss_streak += 1
            else:
                self.loss_streak = 0
            self.win_streak = 0
            self.target -= (self.cfg.gov_down * (1.0 + margin)
                            * (1.0 + 0.5 * max(0, self.loss_streak - 1))
                            * (1.0 - prog))
        else:
            self.win_streak = 0
            self.loss_streak = 0
        self.history.append((outcome, margin))
        self._clamp()
        return self.target


def honest_gap_label(best_gap: float, tol: float) -> str:
    """Label jujur keterjangkauan target (jalur 3, opsi A bersyarat).

    Dipakai overlay Fase 7: bila gap akhir dalam toleransi ->target
    tercapai; bila di luar (mis. target 0.3 yang terbukti tak terjangkau)
    -> katakan terus terang beserta hasil terbaik, bukan sekadar angka.
    """
    if best_gap <= tol:
        return f"pas target (gap {best_gap:.3f})"
    return (f"target di luar jangkauan, hasil terbaik: gap {best_gap:.3f} "
            f"(tol {tol:.3f})")