"""game/ambush/types.py - Data Tahap 3: role NPC, item, konfigurasi squad.

ASUMSI EKSPLISIT: tahap 1-2 tidak punya tipe NPC maupun item (satu-satunya
"item" adalah potion di duel 1v1). Tabel di bawah adalah data BARU khusus
Tahap 3 agar CSP punya domain konkret, sesuai jawaban "Ya, definisikan".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

EMPTY = "NONE"    # nilai slot kosong (squad boleh berisi < kmax anggota)
BOSS = "Boss"
MINION = "Minion"  # peran lemah KHUSUS SEQUENTIAL (tak ada di domain BUFF)
HEALER = "Healer"
FANG = "Dragon Fang"  # satu-satunya item legendary (AllDifferent global)


@dataclass(frozen=True)
class RoleSpec:
    """Satu archetype NPC: kontribusi buff + biaya power untuk constraint."""

    name: str
    hp: int = 0       # bonus max-HP NPC lead
    atk: int = 0      # bonus damage ATTACK
    spec: int = 0     # bonus damage SPECIAL
    regen: int = 0    # HP pulih tiap giliran NPC
    armor: float = 0.0  # fraksi damage masuk yang diabaikan
    chip: int = 0     # damage pasti tiap ronde ke player (efek Archer)
    weaken: float = 0.0  # fraksi heal potion player yang digagalkan (Mage)
    cost: int = 0     # biaya power untuk global constraint budget


@dataclass(frozen=True)
class ItemSpec:
    """Satu item: stat sama seperti role agar buff bisa dijumlahkan seragam."""

    name: str
    hp: int = 0
    atk: int = 0
    spec: int = 0
    regen: int = 0
    armor: float = 0.0
    chip: int = 0
    weaken: float = 0.0
    cost: int = 0
    legendary: bool = False
    # Matriks kompatibilitas BINAL (pengganti daftar larangan): role di luar
    # daftar ini tidak boleh memakai item tersebut. NONE selalu cocok.
    allowed_roles: Tuple[str, ...] = ()


# Role yang boleh memakai tiap item. Disengaja longgar tapi bermakna:
# pedang untuk petarung garis depan, perisai untuk yang bertahan,
# sepatu untuk yang lincah, charm untuk penyembuh/pendukung,
# Fang legendaris cocok untuk semua.
ITEM_ALLOWED: Dict[str, Tuple[str, ...]] = {
    "Iron Sword": ("Warrior", "Archer", "Boss", MINION),
    "Heavy Shield": ("Warrior", "Tank", "Boss", MINION),
    "Swift Boots": ("Warrior", "Archer", "Mage", MINION),
    "Healing Charm": ("Healer", "Mage", "Tank", MINION),
    "Dragon Fang": ("Warrior", "Archer", "Mage", "Healer", "Tank", "Boss"),
}


ROLE_TABLE: Dict[str, RoleSpec] = {
    # Minion: peran lemah KHUSUS SEQUENTIAL (FINAL M3, dari data Fase 3-ulang:
    # jangkauan terbaik tanpa duel trivial).
    # Arti angka = DELTA dari stat dasar duel (musuh 100 HP, damage 15-20
    # rata2 17.5): hp-50 -> 50 HP (-50%), atk-9 -> damage ~8.5 (-50%,
    # roll min 15-9=6>0). Rata-rata -29 HP player per duel (min -24):
    # TETAP berbahaya. Cost 1, non-defensif, item bebas kecuali Fang.
    MINION: RoleSpec(MINION, hp=-50, atk=-9, cost=1),
    "Warrior": RoleSpec("Warrior", hp=10, atk=2, cost=3),  # Tahap-A R3
    "Archer": RoleSpec("Archer", hp=6, atk=3, chip=1, cost=3),  # Tahap-A R3
    "Mage": RoleSpec("Mage", hp=2, atk=1, spec=7, weaken=0.10,  # Tahap-A R3
                     cost=4),
    "Healer": RoleSpec("Healer", hp=-15, atk=1, regen=2,  # Tahap-A R3
                       cost=3),
    "Tank": RoleSpec("Tank", hp=4, atk=2, armor=0.05,  # Tahap-A R3
                     cost=4),
    "Boss": RoleSpec("Boss", hp=6, atk=2, spec=4, armor=0.05,  # rantai-Boss
                     cost=7),
    EMPTY: RoleSpec(EMPTY),
}

ITEM_TABLE: Dict[str, ItemSpec] = {
    EMPTY: ItemSpec(EMPTY),
    "Iron Sword": ItemSpec("Iron Sword", atk=2, cost=1,
                           allowed_roles=ITEM_ALLOWED["Iron Sword"]),
    "Heavy Shield": ItemSpec("Heavy Shield", armor=0.10, cost=1,
                             allowed_roles=ITEM_ALLOWED["Heavy Shield"]),
    "Swift Boots": ItemSpec("Swift Boots", chip=1, cost=1,
                            allowed_roles=ITEM_ALLOWED["Swift Boots"]),
    "Healing Charm": ItemSpec("Healing Charm", regen=1, cost=1,  # Tahap-A R3
                              allowed_roles=ITEM_ALLOWED["Healing Charm"]),
    FANG: ItemSpec(FANG, atk=1, spec=1, cost=3, legendary=True,  # Tahap-A R3
                   allowed_roles=ITEM_ALLOWED[FANG]),
}


def stat_fingerprint() -> str:
    """Hash stabil lintas-proses atas seluruh tabel stat peran+item.

    Dipakai kunci cache evaluator + pendeteksi bobot basi: bila tabel
    berubah (mis. stat Minion), sidik berubah sehingga cache lama dan
    bobot lama otomatis tidak terpakai.
    """
    import hashlib
    parts = []
    for name in sorted(ROLE_TABLE):
        s = ROLE_TABLE[name]
        parts.append(f"R:{name}:{s.hp},{s.atk},{s.spec},{s.regen},"
                     f"{s.armor},{s.chip},{s.weaken},{s.cost}")
    for name in sorted(ITEM_TABLE):
        s = ITEM_TABLE[name]
        parts.append(f"I:{name}:{s.hp},{s.atk},{s.spec},{s.regen},"
                     f"{s.armor},{s.chip},{s.weaken},{s.cost},"
                     f"{s.legendary},{','.join(s.allowed_roles)}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class SquadConfig:
    """Satu konfigurasi squad: tuple role + item per slot (panjang = kmax).

    Slot NONE berarti kosong. Bentuk canonical: tidak ada slot terisi
    setelah slot kosong (ditegakkan constraint, bukan di sini).
    """

    roles: Tuple[str, ...] = field(default_factory=tuple)
    items: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if len(self.roles) != len(self.items):
            raise ValueError("roles dan items harus sama panjang")

    def size(self) -> int:
        """Jumlah anggota non-kosong."""
        return sum(1 for r in self.roles if r != EMPTY)

    def leader(self) -> str:
        """Role slot 1 (lead duel 1v1)."""
        return self.roles[0] if self.roles else EMPTY

    def key(self) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """Kunci hashable untuk cache evaluator."""
        return (self.roles, self.items)
