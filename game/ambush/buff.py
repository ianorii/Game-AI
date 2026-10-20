"""game/ambush/buff.py - Squad (CSP/LS) -> buff untuk 1 NPC lead duel 1v1.

Keputusan desain (sesuai arahan): tiap peran memberi efek berbeda, slot lead
berkontribusi penuh dan slot pendukung kena diminishing returns
``1 / (1 + diminish*i)`` supaya squad besar tidak linear overpower.
``SequentialDuelPlan`` adalah interface untuk pengembangan duel berurutan:
versi sekarang selalu satu ronde (satu buff gabungan).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from game.ambush.config import AmbushConfig
from game.ambush.types import EMPTY, ITEM_TABLE, ROLE_TABLE, SquadConfig, display_role


@dataclass(frozen=True)
class Buff:
    """Efek tempur gabungan satu squad untuk NPC lead."""

    hp: int = 0
    atk: int = 0
    spec: int = 0
    regen: int = 0
    armor: float = 0.0
    chip: int = 0
    weaken: float = 0.0  # fraksi heal potion player yang digagalkan


@dataclass(frozen=True)
class MemberContrib:
    """Kontribusi satu slot (sudah termasuk diminishing returns)."""

    slot: int
    role: str
    item: str
    factor: float
    hp: float = 0.0
    atk: float = 0.0
    spec: float = 0.0
    regen: float = 0.0
    armor: float = 0.0
    chip: float = 0.0
    weaken: float = 0.0


@dataclass(frozen=True)
class BuffSummary:
    """SATU sumber kebenaran SquadConfig -> buff.

    Dipakai oleh overlay (tampilan), evaluator difficulty (angka), dan
    battle (efek). Semua konsumen membaca objek ini sehingga tidak ada
    tiga versi pemetaan yang bisa divergen.
    """

    buff: Buff
    members: Tuple[MemberContrib, ...]

    def lines(self) -> List[str]:
        """Baris human-readable buff AKTIF (non-nol) untuk HUD/overlay.

        Kalimat pemain: "Tahan 10% damage", "Damage pasti 1 tiap ronde",
        dst. (bukan singkatan teknis seperti "dmg diterima"/"chip").
        """
        buff = self.buff
        out = []
        if buff.hp:
            out.append(f"Darah maks musuh {buff.hp:+d}")
        # Hanya tampilkan stat yang benar-benar aktif (hindari "+0").
        if buff.atk and buff.spec:
            out.append(f"Serangan {buff.atk:+d} / spesial {buff.spec:+d} musuh")
        elif buff.atk:
            out.append(f"Serangan {buff.atk:+d} musuh")
        elif buff.spec:
            out.append(f"Spesial {buff.spec:+d} musuh")
        for stat, fmt in (
            ("armor", lambda m: f"{display_role(m.role)}: tahan "
                               f"{m.armor * 100:.0f}% damage"),
            ("regen", lambda m: f"{display_role(m.role)}: "
                               f"pulih {m.regen:.0f} HP tiap giliran"),
            ("chip", lambda m: f"{display_role(m.role)}: "
                              f"damage pasti {m.chip:.0f} tiap ronde"),
            ("weaken", lambda m: f"{display_role(m.role)}: "
                                f"heal pemain -{m.weaken * 100:.0f}%"),
        ):
            top = self._top(stat)
            if top is not None and getattr(top, stat) > 0:
                out.append(fmt(top))
        if not out:
            out.append("tanpa buff (squad kosong)")
        return out

    def _top(self, stat: str) -> Optional[MemberContrib]:
        best = None
        for m in self.members:
            if best is None or getattr(m, stat) > getattr(best, stat):
                best = m
        return best


def contributions(squad: SquadConfig,
                  cfg: AmbushConfig) -> Tuple[MemberContrib, ...]:
    """Kontribusi per slot dengan diminishing returns 1/(1+diminish*i)."""
    out = []
    for i, (role, item) in enumerate(zip(squad.roles, squad.items)):
        if role == EMPTY:
            continue
        factor = 1.0 / (1.0 + cfg.diminish * i)
        spec_role = ROLE_TABLE[role]
        spec_item = ITEM_TABLE[item]
        out.append(MemberContrib(
            slot=i + 1, role=role, item=item, factor=factor,
            hp=(spec_role.hp + spec_item.hp) * factor,
            atk=(spec_role.atk + spec_item.atk) * factor,
            spec=(spec_role.spec + spec_item.spec) * factor,
            regen=(spec_role.regen + spec_item.regen) * factor,
            armor=(spec_role.armor + spec_item.armor) * factor,
            chip=(spec_role.chip + spec_item.chip) * factor,
            weaken=(spec_role.weaken + spec_item.weaken) * factor,
        ))
    return tuple(out)


def summarize_squad(squad: SquadConfig, cfg: AmbushConfig) -> BuffSummary:
    """Ringkas squad menjadi buff + atribusi per anggota."""
    members = contributions(squad, cfg)
    return BuffSummary(
        buff=Buff(
            hp=int(round(sum(m.hp for m in members))),
            atk=int(round(sum(m.atk for m in members))),
            spec=int(round(sum(m.spec for m in members))),
            regen=int(round(sum(m.regen for m in members))),
            armor=min(cfg.armor_max, sum(m.armor for m in members)),
            chip=int(round(sum(m.chip for m in members))),
            weaken=min(cfg.weaken_max, sum(m.weaken for m in members)),
        ),
        members=members,
    )


def squad_to_buff(squad: SquadConfig, cfg: AmbushConfig) -> Buff:
    """Ringkas squad menjadi satu buff (diminishing returns per slot)."""
    return summarize_squad(squad, cfg).buff


@dataclass(frozen=True)
class SequentialDuelPlan:
    """Rencana duel berurutan: satu buff per ronde, dipakai berurutan.

    Versi sekarang: selalu tepat 1 ronde (duel 1v1 yang sudah ada).
    Pengembangan nanti: satu ronde per anggota squad, dipanggil dari
    director tanpa mengubah signature (cukup isi rounds > 1).
    """

    rounds: List[Buff]

    @classmethod
    def single(cls, buff: Buff) -> "SequentialDuelPlan":
        """Bungkus satu buff menjadi rencana satu ronde."""
        return cls(rounds=[buff])


def plan_duels(squad: SquadConfig, cfg: AmbushConfig) -> SequentialDuelPlan:
    """Titik ekstensi duel berurutan: sekarang selalu satu ronde gabungan."""
    return SequentialDuelPlan.single(squad_to_buff(squad, cfg))
