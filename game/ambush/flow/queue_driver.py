"""game/ambush/flow/queue_driver.py - Driver antrean duel (logika murni).

Tanpa pygame: dimainkan headless oleh tes dan autoplay, dipakai main.py
untuk BATTLE berurutan. Pemulihan antar-duel WAJIB lewat apply_rest()
(sama dengan simulator) agar angka game == angka simulasi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from game.ambush.chain_eval import apply_rest, carry_potions
from game.ambush.config import AmbushConfig
from game.ambush.enemy_queue import EnemyQueue


@dataclass
class DuelRecord:
    """Satu duel yang selesai: sisa HP/potion + menang atau tidak."""

    index: int
    role: str
    item: str
    hp_after: int
    pot_after: int
    cleared: bool


@dataclass
class QueueRun:
    """Satu pertemuan berurutan: antrean + HP/potion player yang terbawa."""

    queue: EnemyQueue
    buffs: list
    target: float
    pred_light: float
    pred_full: Optional[float]
    hp: int
    potions: int
    cap: int
    cfg: AmbushConfig
    idx: int = 0
    records: List[DuelRecord] = field(default_factory=list)
    failed_at: Optional[int] = None
    fled: bool = False

    @property
    def k(self) -> int:
        """Jumlah musuh."""
        return self.queue.k()

    def duel_label(self) -> str:
        """Judul duel aktif: 'DUEL n DARI k' (bahasa pemain, bukan jargon)."""
        return f"DUEL {self.idx + 1} DARI {self.k}"

    def current_slot(self):
        """Slot musuh aktif."""
        return self.queue.slots[self.idx]

    def current_buff(self):
        """Buff musuh aktif (satu sumber: slot_to_buff saat rakit)."""
        return self.buffs[self.idx]

    def record(self, hp_after: int, pot_after: int, cleared: bool,
               fled: bool = False) -> str:
        """Catat hasil satu duel. Kembali: 'next' | 'won_all' | 'failed'.

        'next' berarti pindah ke layar transisi (HP dipulihkan via
        apply_rest di sini, BUKAN di tempat lain).
        """
        slot = self.queue.slots[self.idx]
        self.records.append(DuelRecord(
            index=self.idx, role=slot.role, item=slot.item,
            hp_after=max(0, hp_after), pot_after=max(0, pot_after),
            cleared=bool(cleared and not fled)))
        if fled:
            self.fled = True
            self.failed_at = self.idx
            return "failed"
        if not cleared:
            self.failed_at = self.idx
            return "failed"
        if self.idx >= self.k - 1:
            return "won_all"
        self.idx += 1
        self.hp = apply_rest(max(0, hp_after), self.cap,
                             self.cfg.rest_heal_pct)
        self.potions = carry_potions(pot_after, self.cfg)
        if self.cfg.potion_bonus_per_duel > 0:
            from adversarial_ai import POTION_LIMIT
            self.potions = min(POTION_LIMIT,
                               self.potions + self.cfg.potion_bonus_per_duel)
        return "next"

    def progress(self) -> float:
        """Fraksi duel dimenangkan (objektif progres)."""
        if not self.records:
            return 0.0
        return sum(1 for r in self.records if r.cleared) / self.k

    def margin(self) -> float:
        """Rata-rata sisa HP fraksional duel yang dimenangkan."""
        won = [r.hp_after / self.cap for r in self.records if r.cleared]
        return sum(won) / len(won) if won else 0.0

    def result_row(self, run_id: int, result: str) -> dict:
        """Satu baris battle_result.csv."""
        return {
            "run_id": run_id,
            "k": self.k,
            "order": self.queue.order_str(),
            "target": round(self.target, 4),
            "pred_light": round(self.pred_light, 4),
            "pred_full": (round(self.pred_full, 4)
                           if self.pred_full is not None else ""),
            "actual_progress": round(self.progress(), 4),
            "duel_menang": sum(1 for r in self.records if r.cleared),
            "hp_sisa_per_duel": ";".join(str(r.hp_after)
                                         for r in self.records),
            "potion_sisa": (self.records[-1].pot_after if self.records
                            else self.potions),
            "hasil": result,
            "duel_gagal_ke": ("" if self.failed_at is None
                              else self.failed_at + 1),
        }
