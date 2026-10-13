"""game/ambush/buff_ai.py - Buff-aware wrapper di atas mesin tahap 2.

adversarial_ai.py TIDAK disentuh. Dua wrapper di sini hanya dipakai untuk
duel ber-buff (hasil Ambush Director); duel polos memakai kelas asli.

1. BuffBattleState(BattleState): transisi buff-aware. Karena minimax/
   alpha-beta memanggil state.apply_action secara polimorfik, SELURUH pohon
   pencarian otomatis memakai aturan ber-buff tanpa mengubah satu baris
   mesin tahap 2 (bonus atk/spec, cap potion ter-buff, regen di awal
   giliran NPC, armor via prescale, weaken heal player).
2. BuffAwareAI(AdversarialAI): evaluasi buff-aware. ancestry eval
   (balanced/dll, tetap dari sudut pandang NPC) dijalankan di atas state
   yang disesuaikan K ronde ke depan: regen+armor menaikkan HP efektif NPC,
   chip+weaken menurunkan HP efektif player. Guard: state terminal tidak
   disesuaikan (skor terminal ±WIN_SCORE harus murni).
"""
from __future__ import annotations

import math
from typing import Optional

from adversarial_ai import (
    ATTACK_DAMAGE,
    MAX_HP,
    POTION_HEAL,
    SPECIAL_DAMAGE,
    AdversarialAI,
    BattleState,
)
from game.ambush.buff import Buff
from game.ambush.enemy_queue import ENEMY_BASE_HP, enemy_max_hp


class BuffBattleState(BattleState):
    """BattleState dengan buff squad menempel (khusus duel ber-buff)."""

    def __init__(self, *args, buff: Optional[Buff] = None,
                 player_buff: Optional[Buff] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.buff = buff
        self.player_buff = player_buff

    def clone(self) -> "BuffBattleState":
        # dataclasses.replace memanggil type(self) tapi tak membawa buff
        # (bukan field) -> tempel ulang agar tak hilang di tengah search.
        cloned = super().clone()
        cloned.buff = self.buff
        cloned.player_buff = self.player_buff
        return cloned

    def npc_max_hp(self) -> int:
        """Cap HP NPC (dasar musuh + buff, bukan 100 tahap 2)."""
        return enemy_max_hp(self.buff if self.buff else Buff())

    def player_max_hp(self) -> int:
        """Cap HP player (ter-buff loadout bila ada)."""
        return MAX_HP + (self.player_buff.hp if self.player_buff else 0)

    def apply_action(
        self,
        is_npc: bool,
        action: str,
        attack_damage: int = ATTACK_DAMAGE,
        special_damage: int = SPECIAL_DAMAGE,
    ) -> "BuffBattleState":
        """Aturan tahap 2 + parameter buff (dipakai search DAN resolusi).

        Regen jalan di awal giliran NPC; bonus atk/spec ditambahkan ke
        damage; armor di-prescale ke damage SEBELUM aturan defend (ekuivalen
        dengan armor-dulu-lalu-defend karena parent hanya ceil di cabang
        defend); cap potion NPC memakai max ter-buff; weaken memotong heal
        potion player (anti-regen/debuff).
        """
        buff = self.buff
        pbuff = self.player_buff
        s = self.clone()
        if buff is not None and is_npc and buff.regen > 0 and s.npc_hp > 0:
            s.npc_hp = min(s.npc_max_hp(), s.npc_hp + buff.regen)
        if pbuff is not None and not is_npc and pbuff.regen > 0 \
                and s.player_hp > 0:
            s.player_hp = min(s.player_max_hp(),
                              s.player_hp + pbuff.regen)

        pre_npc, pre_player = s.npc_hp, s.player_hp
        atk = attack_damage + (buff.atk if (buff and is_npc) else 0) \
            + (pbuff.atk if (pbuff and not is_npc) else 0)
        spc = special_damage + (buff.spec if (buff and is_npc) else 0) \
            + (pbuff.spec if (pbuff and not is_npc) else 0)
        if buff is not None and not is_npc and action in ("ATTACK", "SPECIAL"):
            # Prescale armor: damage player ke NPC dipotong duluan.
            base = atk if action == "ATTACK" else spc
            scaled = int(math.ceil(base * (1.0 - buff.armor)))
            if action == "ATTACK":
                atk = scaled
            else:
                spc = scaled
        if pbuff is not None and is_npc and action in ("ATTACK", "SPECIAL"):
            # Armor loadout player memotong damage NPC ke player.
            base = atk if action == "ATTACK" else spc
            scaled = int(math.ceil(base * (1.0 - pbuff.armor)))
            if action == "ATTACK":
                atk = scaled
            else:
                spc = scaled

        # Aturan inti tetap milik parent (defend/cd/ganti giliran).
        res = BattleState.apply_action(
            s, is_npc, action, attack_damage=atk, special_damage=spc)
        res.buff = buff
        res.player_buff = pbuff

        if action == "POTION":
            if is_npc and buff is not None:
                res.npc_hp = min(res.npc_max_hp(), pre_npc + POTION_HEAL)
            elif not is_npc and buff is not None and buff.weaken > 0:
                healed = int(round(POTION_HEAL * (1.0 - buff.weaken)))
                res.player_hp = min(MAX_HP, pre_player + healed)
            if not is_npc and pbuff is not None and pbuff.chip:
                pass  # chip player diterapkan via hook di bawah (simetris)
        return res


def apply_chip_hook(state: BattleState, buff: Optional[Buff]) -> BattleState:
    """Hook akhir giliran NPC: chip damage pasti ke player.

    Satu implementasi dipakai loop simulasi DAN battle nyata (in-place).
    """
    if buff is not None and buff.chip > 0 and not state.is_terminal():
        state.player_hp = max(0, state.player_hp - buff.chip)
    pbuff = getattr(state, "player_buff", None)
    if pbuff is not None and pbuff.chip > 0 and not state.is_terminal():
        # Chip loadout player dibalas di akhir giliran player (simetris,
        # agar angka simulasi == angka battle nyata).
        state.npc_hp = max(0, state.npc_hp - pbuff.chip)
    return state


class BuffAwareAI(AdversarialAI):
    """AdversarialAI yang menilai regen/armor/chip/weaken (duel ber-buff).

    Caranya: sesuaikan HP kedua pihak seolah K ronde (lookahead) sudah
    berjalan, lalu jalankan fungsi evaluasi tahap 2 apa adanya di atasnya.
    Bobot/strategi evaluasi tak diubah - hanya "kacamata" HP-nya.
    """

    def __init__(self, *args, buff: Optional[Buff] = None,
                 player_buff: Optional[Buff] = None,
                 lookahead: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.buff = buff
        self.player_buff = player_buff
        self.lookahead = lookahead

    def evaluate_state(self, state: BattleState) -> int:
        buff = self.buff
        pbuff = self.player_buff or getattr(state, "player_buff", None)
        if state.is_terminal() or (buff is None and pbuff is None):
            return super().evaluate_state(state)
        rounds = self.lookahead
        npc_eff = state.npc_hp
        player_eff = state.player_hp
        if buff is not None:
            npc_eff = min(
                ENEMY_BASE_HP + buff.hp,
                state.npc_hp + buff.regen * rounds
                + buff.armor * state.npc_hp * rounds * 0.5,
            )
            player_eff = max(
                1,  # jangan ciptakan terminal palsu (skor WIN_SCORE murni)
                player_eff - buff.chip * rounds
                - buff.weaken * POTION_HEAL * state.player_potions,
            )
        if pbuff is not None:
            # Kacamata simetris: buff player menaikkan HP efektif player
            # dan menggerus HP efektif NPC (atk/armor/chip disederhanakan
            # ke HP agar eval tahap 2 tak berubah bentuk).
            player_eff = min(
                MAX_HP + pbuff.hp,
                player_eff + pbuff.regen * rounds
                + pbuff.armor * player_eff * rounds * 0.5
                + pbuff.hp * 0.5,
            )
            npc_eff = max(
                1, npc_eff - pbuff.chip * rounds
                - pbuff.atk * rounds * 0.5,
            )
        view = state.clone()
        view.npc_hp = int(round(npc_eff))
        view.player_hp = int(round(player_eff))
        return super().evaluate_state(view)
