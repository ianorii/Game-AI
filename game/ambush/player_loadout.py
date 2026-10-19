"""game/ambush/player_loadout.py - Loadout manual player (2 slot, minimal).

Player memilih 2 slot dari item yang SUDAH ada (ITEM_TABLE tahap 3).
Tidak ada atribut baru: efek = statistik item yang sama.
Dijumlahkan tanpa diminishing (player bukan squad), cap ikut config.
Satu-satunya mapping player->angka; dibaca battle, HUD, dan evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from game.ambush.buff import Buff
from game.ambush.config import AmbushConfig
from game.ambush.types import EMPTY, ITEM_TABLE

#: Jumlah slot loadout player (kecil agar layar pilihan cepat).
LOADOUT_SLOTS = 2

#: Item yang bisa dipilih player (semua non-NONE dari tabel yang ada).
AVAILABLE_ITEMS: Tuple[str, ...] = tuple(
    name for name in ITEM_TABLE if name != EMPTY
)


@dataclass(frozen=True)
class PlayerLoadout:
    """Pilihan item manual player sepanjang LOADOUT_SLOTS."""

    items: Tuple[str, ...] = (EMPTY, EMPTY)

    def __post_init__(self) -> None:
        if len(self.items) != LOADOUT_SLOTS:
            raise ValueError(f"loadout harus {LOADOUT_SLOTS} slot")
        for it in self.items:
            if it not in ITEM_TABLE:
                raise ValueError(f"item tak dikenal: {it!r}")

    def key(self) -> Tuple[str, ...]:
        """Kunci hashable untuk cache evaluator."""
        return self.items

    def filled(self) -> List[str]:
        """Item terisi (tanpa NONE)."""
        return [it for it in self.items if it != EMPTY]


def loadout_to_buff(loadout: PlayerLoadout, cfg: AmbushConfig) -> Buff:
    """Jumlahkan stat item player menjadi satu Buff (tanpa diminishing)."""
    hp = atk = spec = regen = chip = 0
    armor = weaken = 0.0
    for name in loadout.filled():
        spec_item = ITEM_TABLE[name]
        hp += spec_item.hp
        atk += spec_item.atk
        spec += spec_item.spec
        regen += spec_item.regen
        armor += spec_item.armor
        chip += spec_item.chip
        weaken += spec_item.weaken
    return Buff(
        hp=hp, atk=atk, spec=spec, regen=regen,
        armor=min(cfg.armor_max, armor),
        chip=chip, weaken=min(cfg.weaken_max, weaken),
    )


def loadout_power(loadout: PlayerLoadout) -> float:
    """Ringkasan kekuatan 0..~1 untuk panel pilihan (skala kasar).

    Bukan difficulty resmi; hanya agar layar loadout bisa menampilkan
    "kekuatan" dan memvalidasi pilihan. Difficulty resmi tetap di
    difficulty.py (yang memakai buff di atas, bukan angka ini).
    """
    buff = loadout_to_buff(loadout, AmbushConfig())
    return min(1.0, (buff.atk * 0.06 + buff.armor * 1.2 + buff.regen * 0.08
                     + buff.chip * 0.06 + buff.spec * 0.02 + buff.hp * 0.008))


def describe_item(name: str) -> str:
    """Satu baris efek item dalam kalimat pemain untuk layar pilihan/HUD.

    Kosakata SAMA dengan buff_lines_short/buff.py: "Serangan +2",
    "Tahan 10% damage", "Damage pasti 1/ronde" (bukan "ATK"/"dmg"/"chip").
    """
    if name == EMPTY:
        return "Kosong"
    spec = ITEM_TABLE[name]
    bits = []
    if spec.atk:
        bits.append(f"Serangan +{spec.atk}")
    if spec.spec:
        bits.append(f"Spesial +{spec.spec}")
    if spec.hp:
        bits.append(f"Darah maks +{spec.hp}")
    if spec.regen:
        bits.append(f"Pulih {spec.regen} HP/giliran")
    if spec.armor:
        bits.append(f"Tahan {spec.armor * 100:.0f}% damage")
    if spec.chip:
        bits.append(f"Damage pasti {spec.chip}/ronde")
    if spec.weaken:
        bits.append(f"Heal musuh -{spec.weaken * 100:.0f}%")
    return ", ".join(bits) if bits else "Kosong"
