"""game/ambush/enemy_queue.py - Model duel berurutan Tahap 3 (Fase 1).

EnemySlot = satu musuh (peran + item + stat turunan mentah, faktor 1.0).
EnemyQueue = antrean 2..kmax musuh yang dilawan satu per satu, HP player
terbawa. NONE hanya alat CSP (lihat constraints.py); di sini antrean hanya
berisi slot AKTIF yang dipadatkan dari kiri.

slot_to_buff() adalah SATU-SATUNYA sumber angka untuk HUD, battle,
heuristik, dan sim (keputusan §6): tidak ada perhitungan paralel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from game.ambush.buff import Buff
from game.ambush.config import AmbushConfig
from game.ambush.types import BOSS, EMPTY, HEALER, ITEM_TABLE, ROLE_TABLE

#: HP dasar musuh (player tetap 100 milik tahap 2). Semua HP maks musuh =
#: ENEMY_BASE_HP + buff.hp (mis. Warrior 70+10=80). Satu-satunya angka dasar
#: sisi musuh; sim, battle nyata, dan HUD wajib lewat enemy_max_hp().
ENEMY_BASE_HP = 70

#: Peran defensif: dua berurutan dilarang (aturan adjacency, Fase 2 CSP).
#: Alasan: dua duel defensif berturut-turut membuat antrean membosankan
#: (regen + armor menumpuk) dan mematikan urgensi urutan sebagai variabel
#: strategi. Lihat constraints.py + README.
DEFENSIVE_ROLES = ("Healer", "Tank")


@dataclass(frozen=True)
class EnemySlot:
    """Satu musuh dalam antrean: peran + item (stat via slot_to_buff)."""

    role: str
    item: str = EMPTY

    def __post_init__(self) -> None:
        if self.role not in ROLE_TABLE or self.role == EMPTY:
            raise ValueError(f"role musuh tak valid: {self.role!r}")
        if self.item not in ITEM_TABLE:
            raise ValueError(f"item musuh tak valid: {self.item!r}")

    def cost(self) -> int:
        """Biaya power slot ini untuk global constraint budget."""
        return ROLE_TABLE[self.role].cost + ITEM_TABLE[self.item].cost


@dataclass(frozen=True)
class EnemyQueue:
    """Antrean duel berurutan: tepat k slot aktif (2..kmax)."""

    slots: Tuple[EnemySlot, ...] = ()

    def __post_init__(self) -> None:
        for s in self.slots:
            if not isinstance(s, EnemySlot):
                raise ValueError("slots harus EnemySlot")

    def k(self) -> int:
        """Jumlah musuh aktif."""
        return len(self.slots)

    def key(self) -> Tuple[Tuple[str, str], ...]:
        """Kunci hashable berurutan untuk cache evaluator."""
        return tuple((s.role, s.item) for s in self.slots)

    @property
    def roles(self) -> Tuple[str, ...]:
        """Tuple peran berurutan (seragam SquadConfig untuk tampil)."""
        return tuple(s.role for s in self.slots)

    @property
    def items(self) -> Tuple[str, ...]:
        """Tuple item berurutan (seragam SquadConfig untuk tampil)."""
        return tuple(s.item for s in self.slots)

    def order_str(self) -> str:
        """Serialisasi ringkas untuk CSV (mis. 'Tank>Healer>Warrior')."""
        return ">".join(s.role for s in self.slots)

    def total_cost(self) -> int:
        """Total biaya power antrean untuk global constraint budget."""
        return sum(s.cost() for s in self.slots)


def slot_to_buff(slot: EnemySlot, cfg: AmbushConfig) -> Buff:
    """Stat mentah satu musuh (faktor 1.0, tanpa diminishing).

    Diminishing returns hanya milik mode BUFF gabungan; tiap musuh di sini
    berdiri sendiri. Caps ikut config seperti squad_to_buff.
    """
    role_spec = ROLE_TABLE[slot.role]
    item_spec = ITEM_TABLE[slot.item]
    return Buff(
        hp=role_spec.hp + item_spec.hp,
        atk=role_spec.atk + item_spec.atk,
        spec=role_spec.spec + item_spec.spec,
        regen=role_spec.regen + item_spec.regen,
        armor=min(cfg.armor_max, role_spec.armor + item_spec.armor),
        chip=role_spec.chip + item_spec.chip,
        weaken=min(cfg.weaken_max, role_spec.weaken + item_spec.weaken),
    )


def queue_to_buffs(queue: EnemyQueue, cfg: AmbushConfig) -> List[Buff]:
    """Satu buff per musuh, berurutan (isi SequentialDuelPlan.rounds)."""
    return [slot_to_buff(s, cfg) for s in queue.slots]


def enemy_max_hp(buff: Buff, base: int = ENEMY_BASE_HP) -> int:
    """HP maks satu musuh = base + buff.hp (min 1 agar selalu bisa dilawan).

    Satu-satunya jalur sim/battle/HUD menentukan HP musuh. Player TIDAK lewat
    sini (dasar player 100 milik tahap 2, tak tersentuh).
    """
    return max(1, base + buff.hp)


def queue_from_assign(assign: dict, cfg: AmbushConfig) -> EnemyQueue:
    """Assignment CSP lengkap -> antrean (slot aktif dipadatkan dari kiri).

    Dipakai menjadikan solusi CSP sebagai seed local search / antrean final.
    NONE adalah alat CSP saja dan hilang di sini (k = jumlah non-NONE).
    """
    slots = []
    for i in range(1, cfg.kmax + 1):
        role = assign.get(f"ROLE_{i}", EMPTY)
        if role == EMPTY:
            continue
        slots.append(EnemySlot(role, assign.get(f"ITEM_{i}", EMPTY)))
    return EnemyQueue(slots=tuple(slots))


def check_queue(queue: EnemyQueue, wins: int, budget: int,
                cfg: AmbushConfig) -> List[str]:
    """Daftar pelanggaran antrean. Kosong = valid (cerminan constraints.py).

    Aturan: k dalam [min_enemies, kmax]; Boss perlu wins + hanya slot
    aktif terakhir; maks 1 Healer; Healer/Tank tak boleh berturutan;
    Fang ≤ 1; kompatibilitas peran-item per slot; total cost ≤ budget.
    """
    bad: List[str] = []
    slots = list(queue.slots)
    k = len(slots)
    if not (cfg.min_enemies <= k <= cfg.kmax):
        bad.append(f"jumlah musuh {k} di luar {cfg.min_enemies}..{cfg.kmax}")
        return bad  # aturan lain butuh indeks valid
    for i, s in enumerate(slots):
        if s.role == BOSS and wins < cfg.boss_min_wins:
            bad.append(f"slot {i + 1}=Boss butuh wins>={cfg.boss_min_wins}")
        if s.role == BOSS and i != k - 1:
            bad.append(f"Boss harus slot aktif terakhir (ada di {i + 1})")
        if s.item != EMPTY and s.role not in ITEM_TABLE[s.item].allowed_roles:
            bad.append(f"{s.role} tidak kompatibel dengan {s.item}")
    if sum(1 for s in slots if s.role == HEALER) > 1:
        bad.append("dua Healer dalam satu antrean")
    for a, b in zip(slots, slots[1:]):
        if a.role in DEFENSIVE_ROLES and b.role in DEFENSIVE_ROLES:
            bad.append(f"{a.role}-{b.role} berturutan (defensif ganda)")
            break
    fangs = sum(1 for s in slots if s.item == "Dragon Fang")
    if fangs > 1:
        bad.append("Dragon Fang ganda (item langka unik)")
    seen = [s.item for s in slots if s.item != EMPTY]
    if len(set(seen)) != len(seen):
        bad.append("item non-NONE harus saling berbeda")
    cost = queue.total_cost()
    if cost > budget:
        bad.append(f"total power {cost} melebihi budget {budget}")
    return bad


def is_queue_valid(queue: EnemyQueue, wins: int, budget: int,
                   cfg: AmbushConfig) -> bool:
    """True jika antrean valid (lengkap dan konsisten)."""
    return not check_queue(queue, wins, budget, cfg)
